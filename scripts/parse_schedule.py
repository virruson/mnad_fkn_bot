#!/usr/bin/env python
"""
Разбор вкладки модуля из xlsx-расписания программы в JSONL для scripts/import_schedule.py.

    python scripts/parse_schedule.py расписание.xlsx --sheet "6 модуль (предварительно)" \
        --links-from scripts/schedule_5module_parsed.jsonl --out scripts/schedule_6module_parsed.jsonl

Вкладка — два месячных блока (A–G и I–O): строка с числами дней, под ней строка с занятиями.
Ячейка — одно или несколько занятий через пустую строку:
    Предмет (Маголего)
    Преподаватель[, экзамен]
    Лекция
    18:10-19:30
    Семинар
    19:40-21:00
    ссылка
Ссылка на встречу: гиперссылка ячейки вида …/j/… (не запись), иначе — ссылка этого предмета
из --links-from (прошлые модули, первым — самый новый). Записи без времени («Сессия», экзамен без часа)
пропускаются. Два занятия в одной ячейке, а гиперссылка одна — см. fix_shared_links.

Уже разобранный JSONL можно поправить без xlsx:
    python scripts/parse_schedule.py --fix-links scripts/schedule_6module_parsed.jsonl \
        --links-from scripts/schedule_5module_parsed.jsonl --out scripts/schedule_6module_parsed.jsonl
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import openpyxl

MONTHS = {'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4, 'май': 5, 'июнь': 6, 'июль': 7,
          'август': 8, 'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12}
BLOCKS = (('A', 'G'), ('I', 'O'))
ELECTIVE = "(Маголего)"
TIME_RE = re.compile(r'^(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?$')
LESSON_TYPES = ('Лекция', 'Семинар', 'Экзамен', 'Консультация')
SKIP_LINES = ('ссылка', 'запись')


def col_range(first, last):
    return [chr(c) for c in range(ord(first), ord(last) + 1)]


def month_of(ws, first_col):
    """«Ноябрь 2026» в строке 4 над блоком → (год, месяц)."""
    for row in range(1, 6):
        value = str(ws[f"{first_col}{row}"].value or '').strip().lower()
        parts = value.split()
        if len(parts) == 2 and parts[0] in MONTHS and parts[1].isdigit():
            return int(parts[1]), MONTHS[parts[0]]
    return None


def day_rows(ws, cols):
    """Строки, где в блоке стоят числа дней (5.0, 12.0 …)."""
    rows = []
    for r in range(1, ws.max_row + 1):
        nums = [ws[f"{c}{r}"].value for c in cols]
        if any(isinstance(v, (int, float)) for v in nums):
            rows.append(r)
    return rows


def parse_block(text):
    """Одно занятие-блок → [(subject, stream, teacher, lesson_type, start, end)]."""
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    if not lines:
        return []
    subject = lines[0]
    stream = None
    if ELECTIVE in subject:
        subject, stream = subject.replace(ELECTIVE, '').strip(), "Маголего"
    teacher, kind_hint = None, None
    rest = lines[1:]
    if rest and not TIME_RE.match(rest[0]) and rest[0].split()[0] not in LESSON_TYPES:
        teacher = rest.pop(0)
        if ',' in teacher:                          # «Мария Горденко, экзамен»
            teacher, hint = [p.strip() for p in teacher.split(',', 1)]
            kind_hint = 'Экзамен' if 'экзамен' in hint.lower() else None
    if kind_hint is None and subject.startswith('Встреча'):   # «Встреча по ВКР» — не предмет
        kind_hint = 'Встреча'
    out, pending = [], kind_hint
    for line in rest:
        m = TIME_RE.match(line)
        if m:
            out.append((subject, stream, teacher, pending or 'Семинар', m.group(1).zfill(5),
                        m.group(2).zfill(5) if m.group(2) else None))
            pending = kind_hint
        elif line.split()[0] in LESSON_TYPES:
            pending = line.split()[0]
        elif line.lower() in SKIP_LINES:
            continue
    return out


def load_links(paths):
    """{предмет: ссылка}. Внутри файла побеждает последняя (свежая) ссылка, между файлами — первый файл:
    первым передавать самый новый модуль."""
    links = {}
    for p in paths or []:
        own = {}
        for line in open(p, encoding='utf-8'):
            if line.strip():
                r = json.loads(line)
                if r.get('meeting_link'):
                    own[r['subject']] = r['meeting_link']
        for subject, link in own.items():
            links.setdefault(subject, link)
    return links


def fix_shared_links(rows, links):
    """В таблице одна гиперссылка на ячейку, а занятий в ячейке бывает два («Семинар наставника» +
    «Разработка ИИ-агентов»). Ссылка ячейки достаётся занятию, в блоке которого написано «ссылка»
    (если таких несколько — первому по времени). Остальным — их собственная ссылка: самая частая
    у этого предмета и типа в ячейках с одним занятием, потом у предмета, потом из прошлых модулей.
    Возвращает список занятий, которым ссылка подставлена так (для проверки глазами)."""
    from collections import Counter, defaultdict

    cells = defaultdict(list)
    for r in rows:
        cells[(r['date'], r['cell'])].append(r)
    single = [g[0] for g in cells.values() if len(g) == 1 and g[0]['meeting_link']]
    by_kind = defaultdict(Counter)
    by_subject = defaultdict(Counter)
    for r in single:
        by_kind[(r['subject'], r['lesson_type'])][r['meeting_link']] += 1
        by_subject[r['subject']][r['meeting_link']] += 1

    def own_link(r):
        for counter in (by_kind.get((r['subject'], r['lesson_type'])), by_subject.get(r['subject'])):
            if counter:
                return counter.most_common(1)[0][0]
        return links.get(r['subject'])

    guessed = []
    for group in cells.values():
        if len(group) < 2 or len({r['meeting_link'] for r in group}) > 1:
            continue
        group.sort(key=lambda r: r['time_start'])
        holders = [r for r in group if 'ссылка' in r['raw_line'].lower()] or group[:1]
        owner = holders[0]
        for r in group:
            if r is owner or r['subject'] == owner['subject']:
                continue                           # лекция и семинар одного предмета — одна встреча
            link = own_link(r)
            if link != r['meeting_link']:
                r['meeting_link'] = link
                guessed.append(r)
    return guessed


def parse_sheet(ws, links):
    rows = []
    for first, last in BLOCKS:
        cols = col_range(first, last)
        ym = month_of(ws, first)
        if not ym:
            continue
        for r in day_rows(ws, cols):
            year, month = ym
            prev = 0
            for c in cols:
                num = ws[f"{c}{r}"].value
                if not isinstance(num, (int, float)):
                    continue
                day = int(num)
                if day < prev:                      # 30, 1, 2 … — перешли в следующий месяц
                    month, year = (1, year + 1) if month == 12 else (month + 1, year)
                prev = day
                cell = ws[f"{c}{r + 1}"]
                if not cell.value:
                    continue
                cell_link = cell.hyperlink.target if cell.hyperlink else None
                if cell_link and '/j/' not in cell_link:
                    cell_link = None                # запись прошедшего занятия — не ссылка на встречу
                text = str(cell.value).replace('\r', '')
                for block in re.split(r'\n\s*\n', text):
                    for subject, stream, teacher, kind, start, end in parse_block(block):
                        rows.append({
                            "subject": subject, "stream": stream, "teacher": teacher,
                            "lesson_type": kind, "time_start": start, "time_end": end,
                            "meeting_link": cell_link or links.get(subject),
                            "raw_line": " | ".join(ln.strip() for ln in block.split('\n') if ln.strip()),
                            "date": date(year, month, day).isoformat(),
                            "cell": f"{c}{r + 1}", "sheet": ws.title,
                        })
    rows.sort(key=lambda x: (x['date'], x['time_start'], x['subject']))
    return rows, fix_shared_links(rows, links)


def main():
    ap = argparse.ArgumentParser(description="xlsx-вкладка модуля → JSONL для import_schedule")
    ap.add_argument('xlsx', nargs='?', help="xlsx-расписание (без него — --fix-links для готового JSONL)")
    ap.add_argument('--sheet')
    ap.add_argument('--fix-links', help="готовый JSONL: только разнести ссылки в ячейках с двумя занятиями")
    ap.add_argument('--links-from', action='append', help="JSONL прошлых модулей — ссылки по предмету")
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    links = load_links(args.links_from)
    if args.fix_links:
        rows = [json.loads(line) for line in open(args.fix_links, encoding='utf-8') if line.strip()]
        guessed = fix_shared_links(rows, links)
    else:
        if not (args.xlsx and args.sheet):
            ap.error("нужны xlsx и --sheet (или --fix-links)")
        rows, guessed = parse_sheet(openpyxl.load_workbook(args.xlsx)[args.sheet], links)
    with open(args.out, 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    no_link = sorted({r['subject'] for r in rows if not r['meeting_link']})
    print(f"Занятий: {len(rows)} → {args.out}")
    if no_link:
        print("Без ссылки: " + ", ".join(no_link))
    if guessed:
        print("Две пары в одной ячейке — ссылка взята у предмета, проверьте:")
        for r in guessed:
            print(f"  {r['date']} {r['time_start']} {r['subject']} → {r['meeting_link']}")


if __name__ == '__main__':
    main()
