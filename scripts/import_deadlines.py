#!/usr/bin/env python
"""
Загрузка дедлайнов, формул оценивания и модулей в БД.

Источник по умолчанию — scripts/deadlines.json (лежит в git, на сервер попадает
вместе с коммитом; deploy.sh сам запускает импорт, если файл изменился).

Использование:
    python -m scripts.import_deadlines --dry-run        # показать, что будет загружено
    python -m scripts.import_deadlines                  # загрузить scripts/deadlines.json
    python -m scripts.import_deadlines --prune          # + удалить дедлайны, которых нет в json
    python -m scripts.import_deadlines --prune --force-prune   # + даже те, где есть отметки студентов
    python -m scripts.import_deadlines --json other.json
    python -m scripts.import_deadlines --sheet-id <ID>  # то же из Google Sheet (вкладки
        «Дедлайны», «Формулы», «Модули»; ключ — --credentials или GOOGLE_CREDENTIALS)

Формат deadlines.json:
    {
      "modules":   [{"name": "5 модуль", "start": "05.09.2026", "end": "26.10.2026"}],
      "subjects":  [{"name": "Продвинутое машинное обучение", "short_name": "Продвинутое МО",
                     "formula": "0.3·ДЗ + 0.2·Квизы + 0.5·КР",
                     "weights": {"hw": 0.3, "quiz": 0.2, "exam": 0.5}}],
      "deadlines": [{"subject": "Продвинутое машинное обучение", "type": "ДЗ",
                     "title": "№1", "date": "03.10.2026", "time": "18:00"},
                    {"subject": "…", "type": "ДЗ", "title": "№1 жёсткий (…)", "date": "…",
                     "progress": "hidden"}]
    }
type — ДЗ / Квиз / КВИЗ/КР / КР / Экзамен / Этап / Проект (у экзамена title можно не писать). Даты — ДД.ММ.ГГГГ или ГГГГ-ММ-ДД, time можно не
указывать (= 23:59). Предмет ищется по точному названию из расписания; не найден —
WARNING, запись пропускается. Предмета нет в расписании (ВКР) — в "subjects"
указать "create": true, тогда он будет создан.

weights — веса для накопа в «📈 Мой прогресс»: ключи — типы hw | quiz | test | project | exam
или одна активность «<тип>:<название>» ("hw:№1"); сумма 1.0. В Google Sheet — колонка «Веса»
вкладки «Формулы»: hw=0.5; quiz=0.2; exam=0.3. Пусто — веса в БД не меняются.
progress — роль строки в прогрессе: пусто (обычная активность), bonus (вне накопа), hidden
(не показывать: жёсткие сроки, пересдачи). В Google Sheet — колонка «Прогресс» вкладки «Дедлайны».
Карточка дедлайнов, утренняя рассылка и график это поле не учитывают.

ВАЖНО: дедлайн, по которому у студентов есть отметки, не переименовывать — у него ключ
upsert, переименование = удаление старого + новый (отметки пропадут). Править дату и время.

Скрипт:
  - upsert дедлайнов по ключу предмет + тип + название (меняются дата, время и роль)
  - upsert формул и коротких названий предметов, модулей по названию
  - НЕ удаляет ничего из БД, кроме режима --prune: тогда дедлайны, которых нет
    в источнике, удаляются (если в дедлайнах нет WARNING). Дедлайн с отметками студентов
    --prune не удаляет (WARNING «есть отметки у N студентов»), только с --force-prune.
  - оценки студентов не выводит — только количество отметок
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Запуск как модуль из корня проекта: python -m scripts.import_deadlines ...
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from bot.utils.database import SessionLocal
from bot.models import Subject, Deadline, Module, UserProgress
from bot.services.progress import parse_weights, weights_sum_ok

KINDS = {'дз': 'hw', 'квиз': 'quiz', 'квиз/кр': 'quiz', 'кр': 'test', 'экзамен': 'exam', 'экз': 'exam',
         'этап': 'milestone', 'проект': 'project'}
ROLES = {'': 'item', 'item': 'item', 'bonus': 'bonus', 'hidden': 'hidden'}
ROLE_HINTS = ('жёсткий', 'жесткий', 'пересдача', 'бонус')  # у обычной активности такого быть не должно
TAB_DEADLINES, TAB_FORMULAS, TAB_MODULES = "Дедлайны", "Формулы", "Модули"
DEFAULT_CREDENTIALS = Path(__file__).resolve().parent / "credentials.json"
DEFAULT_JSON = Path(__file__).resolve().parent / "deadlines.json"


def fetch_tabs(sheet_id, credentials):
    """{название вкладки: строки без заголовка}. Отсутствующая вкладка → None."""
    import gspread
    spreadsheet = gspread.service_account(filename=credentials).open_by_key(sheet_id)
    tabs = {}
    for title in (TAB_DEADLINES, TAB_FORMULAS, TAB_MODULES):
        try:
            tabs[title] = spreadsheet.worksheet(title).get_all_values()[1:]
        except gspread.WorksheetNotFound:
            tabs[title] = None
    return tabs


def fetch_json(path):
    """deadlines.json → те же строки, что и вкладки Google Sheet."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return {
        TAB_MODULES: [[m.get('name') or '', m.get('start') or '', m.get('end') or '']
                      for m in data.get('modules', [])],
        TAB_FORMULAS: [[s.get('name') or '', s.get('formula') or '', s.get('short_name') or '',
                        'create' if s.get('create') else '', _weights_cell(s.get('weights'))]
                       for s in data.get('subjects', [])],
        TAB_DEADLINES: [[d.get('subject') or '', d.get('type') or '', d.get('title') or '',
                         d.get('date') or '', d.get('time') or '', d.get('progress') or '']
                        for d in data.get('deadlines', [])],
    }


def _weights_cell(weights):
    """{"hw": 0.5, …} из json → «hw=0.5; …», как в колонке «Веса» Google Sheet."""
    if isinstance(weights, dict):
        return "; ".join(f"{k}={v}" for k, v in weights.items())
    return weights or ''


def parse_date(value):
    value = value.strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"дата «{value}» не в формате ДД.ММ.ГГГГ")


def parse_time(value):
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%H:%M').time()
    except ValueError:
        raise ValueError(f"время «{value}» не в формате ЧЧ:ММ")


def cells(row, count):
    """Строка таблицы → ровно count обрезанных ячеек (хвостовые пустые gspread не отдаёт)."""
    row = [str(c).strip() for c in row[:count]]
    return row + [''] * (count - len(row))


class Importer:
    def __init__(self, session):
        self.session = session
        self.subjects = {s.name.strip(): s for s in session.query(Subject).all()}
        self.stats = {'created': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0, 'deleted': 0, 'kept': 0}
        self.seen_deadline_ids = set()
        self.deadline_warnings = 0
        self.log = []

    def _record(self, action, text):
        self.stats[action] += 1
        if action != 'unchanged':
            mark = {'created': '+', 'updated': '~', 'skipped': 'WARNING', 'deleted': '-'}[action]
            self.log.append(f"  {mark} {text}")

    def _warn(self, where, message):
        self._record('skipped', f"{where}: {message} — пропущено")

    def _note(self, where, message):
        """WARNING-подсказка: запись загружена, удаление (--prune) не блокирует."""
        self.log.append(f"  WARNING {where}: {message}")

    def _subject(self, where, name):
        subject = self.subjects.get(name)
        if subject is None:
            self._warn(where, f"предмет «{name}» не найден")
        return subject

    @staticmethod
    def _apply(obj, values):
        """Записывает изменившиеся поля. Возвращает список «поле: было → стало»."""
        changes = []
        for field, value in values.items():
            old = getattr(obj, field)
            if old != value:
                changes.append(f"{field}: {old} → {value}")
                setattr(obj, field, value)
        return changes

    def import_modules(self, rows):
        for i, row in enumerate(rows, start=2):
            name, start, end = cells(row, 3)
            if not any((name, start, end)):
                continue
            where = f"{TAB_MODULES}!{i}"
            try:
                start_date, end_date = parse_date(start), parse_date(end)
            except ValueError as e:
                self._warn(where, e)
                continue
            if not name or start_date > end_date:
                self._warn(where, "нет названия или начало позже конца")
                continue
            module = self.session.query(Module).filter_by(name=name).first()
            if module is None:
                self.session.add(Module(name=name, start_date=start_date, end_date=end_date))
                self._record('created', f"модуль {name}: {start_date:%d.%m.%Y}–{end_date:%d.%m.%Y}")
            elif changes := self._apply(module, {'start_date': start_date, 'end_date': end_date}):
                self._record('updated', f"модуль {name}: {'; '.join(changes)}")
            else:
                self._record('unchanged', name)
            self.session.flush()

    def import_formulas(self, rows):
        for i, row in enumerate(rows, start=2):
            name, formula, short_name, create, weights_raw = cells(row, 5)
            if not name:
                continue
            if create and name not in self.subjects:   # предмет не из расписания (ВКР)
                self.subjects[name] = Subject(name=name)
                self.session.add(self.subjects[name])
                self.session.flush()
                self._record('created', f"предмет {name}")
            subject = self._subject(f"{TAB_FORMULAS}!{i}", name)
            if subject is None:
                continue
            if formula.lower().startswith('итог'):   # «Итог = …» → только правая часть
                formula = formula.split('=', 1)[-1].strip()
            values = {'grading_formula': formula or subject.grading_formula,
                      'short_name': short_name or subject.short_name}
            if weights_raw:
                try:
                    weights = parse_weights(weights_raw)
                except ValueError as e:
                    self._note(f"{TAB_FORMULAS}!{i}", f"{name}: веса не загружены — {e}")
                else:
                    if not weights_sum_ok(weights):
                        self._note(f"{TAB_FORMULAS}!{i}",
                                   f"{name}: сумма весов {sum(weights.values()):g}, а не 1.0 — веса не загружены")
                    else:
                        values['grading_weights'] = weights
            if changes := self._apply(subject, values):
                self._record('updated', f"{name}: {'; '.join(changes)}")
            else:
                self._record('unchanged', name)

    def import_deadlines(self, rows):
        skipped_before = self.stats['skipped']
        self._import_deadline_rows(rows)
        self.deadline_warnings = self.stats['skipped'] - skipped_before

    def prune_deadlines(self, force=False):
        """Удаляет дедлайны, которых больше нет в источнике (переименованные, отменённые).

        Дедлайн с отметками студентов («Мой прогресс») без force не удаляется.
        """
        if self.deadline_warnings:
            print("  удаление пропущено: в дедлайнах есть WARNING — сначала исправьте их")
            return
        stale = self.session.query(Deadline).filter(Deadline.id.notin_(self.seen_deadline_ids)).all()
        marks = dict(self.session.query(UserProgress.deadline_id, func.count(UserProgress.user_id))
                     .filter(UserProgress.deadline_id.in_([d.id for d in stale]))
                     .group_by(UserProgress.deadline_id).all()) if stale else {}
        for d in stale:
            label = f"{d.subject.name} · {d.kind} {d.title} · {d.due_date:%d.%m.%Y}"
            if marks.get(d.id) and not force:
                self.stats['kept'] += 1
                self.log.append(f"  WARNING {label}: есть отметки у {marks[d.id]} студентов — не удалено "
                                f"(удалить вместе с отметками: --force-prune)")
                continue
            suffix = f" (с отметками у {marks[d.id]} студентов)" if marks.get(d.id) else ""
            self._record('deleted', label + suffix)
            self.session.delete(d)

    def _import_deadline_rows(self, rows):
        for i, row in enumerate(rows, start=2):
            name, kind_raw, title, date_raw, time_raw, role_raw = cells(row, 6)
            if not any((name, kind_raw, title, date_raw)):
                continue
            where = f"{TAB_DEADLINES}!{i}"
            subject = self._subject(where, name)
            if subject is None:
                continue
            kind = KINDS.get(kind_raw.lower().replace(' ', ''))
            if kind is None:
                self._warn(where, f"тип «{kind_raw}» — ожидается ДЗ, Квиз, КВИЗ/КР, КР, Экзамен, Этап или Проект")
                continue
            role = ROLES.get(role_raw.lower())
            if role is None:
                self._warn(where, f"progress «{role_raw}» — ожидается пусто, bonus или hidden")
                continue
            if role == 'item' and any(h in title.lower() for h in ROLE_HINTS):
                self._note(where, f"«{title}» — обычная активность? Возможно, забыли progress: hidden / bonus")
            if not title and kind != 'exam':   # у экзамена название необязательно
                self._warn(where, "нет названия")
                continue
            try:
                due_date, due_time = parse_date(date_raw), parse_time(time_raw)
            except ValueError as e:
                self._warn(where, e)
                continue

            label = f"{name} · {kind_raw} {title} · {due_date:%d.%m.%Y}{f' {due_time:%H:%M}' if due_time else ''}"
            deadline = self.session.query(Deadline).filter_by(
                subject_id=subject.id, kind=kind, title=title).first()
            if deadline is None:
                deadline = Deadline(subject_id=subject.id, kind=kind, title=title,
                                    due_date=due_date, due_time=due_time, progress_role=role)
                self.session.add(deadline)
                self._record('created', label)
            elif changes := self._apply(deadline, {'due_date': due_date, 'due_time': due_time,
                                                   'progress_role': role}):
                self._record('updated', f"{label} ({'; '.join(changes)})")
            else:
                self._record('unchanged', label)
            self.session.flush()  # чтобы повтор той же строки ниже нашёл уже добавленную запись
            self.seen_deadline_ids.add(deadline.id)


def run(tabs, dry_run=False, prune=False, force_prune=False):
    session = SessionLocal()
    importer = Importer(session)
    try:
        for title, method in ((TAB_MODULES, importer.import_modules),
                              (TAB_FORMULAS, importer.import_formulas),
                              (TAB_DEADLINES, importer.import_deadlines)):
            rows = tabs.get(title)
            if rows is None:
                print(f"[{title}] вкладка не найдена — пропускаю")
                continue
            before = len(importer.log)
            method(rows)
            print(f"[{title}] строк: {len(rows)}")
            print("\n".join(importer.log[before:]) or "  без изменений")

        if prune and tabs.get(TAB_DEADLINES) is not None:
            before = len(importer.log)
            print("[Удаление] дедлайны, которых нет в источнике")
            importer.prune_deadlines(force=force_prune)
            print("\n".join(importer.log[before:]) or "  нечего удалять")

        if dry_run:
            session.rollback()
            print("[dry-run] изменения НЕ сохранены в БД")
        else:
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return importer.stats


def main():
    parser = argparse.ArgumentParser(description="Загрузка дедлайнов, формул и модулей в БД")
    parser.add_argument('--json', default=str(DEFAULT_JSON), help="файл JSON (по умолчанию scripts/deadlines.json)")
    parser.add_argument('--sheet-id', help="взять данные из Google Sheet вместо JSON")
    parser.add_argument('--credentials', default=os.getenv('GOOGLE_CREDENTIALS', str(DEFAULT_CREDENTIALS)),
                        help="JSON-ключ сервисного аккаунта Google")
    parser.add_argument('--dry-run', action='store_true', help="не сохранять изменения в БД")
    parser.add_argument('--prune', action='store_true',
                        help="удалить из БД дедлайны, которых нет в источнике (переименованные/отменённые)")
    parser.add_argument('--force-prune', action='store_true',
                        help="вместе с --prune: удалять и дедлайны с отметками студентов (отметки пропадут)")
    args = parser.parse_args()

    if args.sheet_id:
        tabs = fetch_tabs(args.sheet_id, args.credentials)
    else:
        print(f"Источник: {args.json}")
        tabs = fetch_json(args.json)

    stats = run(tabs, dry_run=args.dry_run, prune=args.prune or args.force_prune, force_prune=args.force_prune)
    kept = f", оставлено из-за отметок: {stats['kept']}" if stats['kept'] else ""
    print(f"Создано: {stats['created']}, обновлено: {stats['updated']}, удалено: {stats['deleted']}, "
          f"без изменений: {stats['unchanged']}, пропущено: {stats['skipped']}{kept}")

if __name__ == '__main__':
    main()
