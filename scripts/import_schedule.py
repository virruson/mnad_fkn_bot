#!/usr/bin/env python
"""
Загрузка расписания в БД из файла schedule_parsed.jsonl
(см. scripts/parse_schedule.py — он генерирует этот файл из xlsx-расписания).

Использование:
    python -m scripts.import_schedule schedule_parsed.jsonl
    python -m scripts.import_schedule schedule_parsed.jsonl --dry-run
    python -m scripts.import_schedule schedule_parsed.jsonl --review-out review.txt

По умолчанию скрипт:
  - создаёт недостающие справочники (потоки, предметы, преподаватели, типы занятий)
  - вставляет/обновляет записи в Schedule (upsert по дате+времени+потоку+предмету)
  - НЕ удаляет ничего из БД

--dry-run     — ничего не пишет в БД, только показывает, что было бы сделано
--review-out  — сохраняет список "подозрительных" записей (без времени, без
                ссылки на Zoom, из ячеек с несколькими занятиями) в текстовый
                файл для ручной проверки
"""
import argparse
import json
import sys
from datetime import datetime, time as dt_time
from pathlib import Path

# Запуск как модуль из корня проекта: python -m scripts.import_schedule ...
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.utils.database import SessionLocal
from bot.models import Stream, Subject, Teacher, LessonType, Schedule

DEFAULT_LESSON_TYPE = "Занятие"
DEFAULT_STREAM = "Общий поток"


def get_or_create(session, model, defaults=None, **kwargs):
    """Найти запись по kwargs или создать новую. Возвращает (объект, создан_ли)."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    session.add(instance)
    session.flush()  # чтобы сразу получить id для использования в FK
    return instance, True


def split_teacher_name(raw_name):
    """
    В расписании имена записаны в формате 'Имя Фамилия' (например, 'Юрий Саночкин').
    Возвращает (first_name, last_name, middle_name).
    """
    if not raw_name:
        return None, "Не указан", None
    parts = raw_name.strip().split()
    if len(parts) == 1:
        return None, parts[0], None
    if len(parts) == 2:
        return parts[0], parts[1], None
    # на случай ФИО из трёх слов — считаем последнее отчеством
    return parts[0], parts[1], parts[2]


def parse_time(value):
    if not value:
        return None
    h, m = value.split(':')
    return dt_time(int(h), int(m))


def load_rows(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def is_for_review(row):
    """Записи, которые стоит проверить руками после загрузки."""
    return (
        row.get('time_start') is None
        or row.get('zoom_link') is None
        or row.get('lesson_type') is None
    )


def import_rows(rows, dry_run=False):
    session = SessionLocal()
    stats = {'created': 0, 'updated': 0, 'skipped': 0}
    review = []

    try:
        for row in rows:
            if is_for_review(row):
                review.append(row)

            time_start = parse_time(row.get('time_start'))
            if time_start is None:
                stats['skipped'] += 1
                continue  # без времени занятие в расписание не положить

            lesson_date = datetime.strptime(row['date'], '%Y-%m-%d').date()

            stream_name = f"{row['stream']} поток" if row.get('stream') else DEFAULT_STREAM
            lesson_type_name = row.get('lesson_type') or DEFAULT_LESSON_TYPE
            first_name, last_name, middle_name = split_teacher_name(row.get('teacher'))

            stream, _ = get_or_create(session, Stream, name=stream_name)
            subject, _ = get_or_create(session, Subject, name=row['subject'])
            lesson_type, _ = get_or_create(session, LessonType, name=lesson_type_name)
            teacher, _ = get_or_create(
                session, Teacher,
                last_name=last_name,
                first_name=first_name,
                defaults={'middle_name': middle_name},
            )

            # Естественный ключ занятия — дата+время+поток+предмет.
            existing = session.query(Schedule).filter_by(
                lesson_date=lesson_date,
                lesson_time=time_start,
                stream_id=stream.id,
                subject_id=subject.id,
            ).first()

            if existing:
                changed = False
                for field, value in (
                    ('teacher_id', teacher.id),
                    ('lesson_type_id', lesson_type.id),
                    ('zoom_link', row.get('zoom_link')),
                ):
                    if getattr(existing, field) != value:
                        setattr(existing, field, value)
                        changed = True
                if changed:
                    stats['updated'] += 1
            else:
                session.add(Schedule(
                    stream_id=stream.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                    lesson_type_id=lesson_type.id,
                    lesson_date=lesson_date,
                    lesson_time=time_start,
                    zoom_link=row.get('zoom_link'),
                ))
                stats['created'] += 1

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

    return stats, review


def write_review(review, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"Записей для ручной проверки: {len(review)}\n")
        f.write("(нет времени, и/или нет ссылки на Zoom, и/или не определён тип занятия)\n\n")
        for row in review:
            f.write(
                f"{row['date']} | ячейка {row['cell']} | "
                f"{row.get('time_start') or '??:??'}-{row.get('time_end') or '??:??'} | "
                f"{row['subject']} | преп.: {row.get('teacher')} | "
                f"тип: {row.get('lesson_type')} | поток: {row.get('stream')} | "
                f"zoom: {row.get('zoom_link')}\n"
                f"    исходная строка: {row.get('raw_line')}\n"
            )


def main():
    parser = argparse.ArgumentParser(description="Загрузка расписания в БД из JSONL")
    parser.add_argument('jsonl_path', help="путь к schedule_parsed.jsonl")
    parser.add_argument('--dry-run', action='store_true', help="не сохранять изменения в БД")
    parser.add_argument('--review-out', help="сохранить список записей для ручной проверки в файл")
    args = parser.parse_args()

    rows = load_rows(args.jsonl_path)
    print(f"Прочитано записей: {len(rows)}")

    stats, review = import_rows(rows, dry_run=args.dry_run)
    print(f"Создано: {stats['created']}, обновлено: {stats['updated']}, "
          f"пропущено (нет времени): {stats['skipped']}")
    print(f"Помечено для ручной проверки: {len(review)}")

    if args.review_out:
        write_review(review, args.review_out)
        print(f"Список для проверки сохранён в {args.review_out}")


if __name__ == '__main__':
    main()
