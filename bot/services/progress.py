"""
«📈 Мой прогресс»: накоп по формуле и тексты экранов (Telegram HTML).

Макет — docs/ui_progress.md, задача — docs/progress_developer.md.
Чистые функции: на вход дедлайны предмета и отметки студента {deadline_id: отметка
с полями done_at, grade}, без БД и Telegram — всё проверяется тестами.

Расчёт (особые правила курса — автомат, min(ДЗ, 10), бонусы, округление — не считаем):
  компонент = Σ оценок / число активностей (неоценённое = 0)
  накоп     = Σ вес × компонент по всем, кроме экзамена; максимум = Σ этих весов × 10
  итог      = накоп + вес экзамена × экзамен — только когда экзамен оценён
В расчёт и счётчики идут только активности с progress_role = 'item'.
"""
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html import escape

from bot.services.deadlines import END_OF_DAY, KIND_BLOCKS, NO_INFO, display_name, due_at

WEIGHT_KINDS = ('hw', 'quiz', 'test', 'project', 'exam')
SHORT_KIND = {'hw': 'ДЗ', 'quiz': 'Квиз', 'test': 'КР', 'project': 'Проект', 'exam': 'Экзамен'}
BLOCK_LABEL = {kind: label for kind, _, label in KIND_BLOCKS}
KIND_ORDER = {kind: i for i, (kind, _, _) in enumerate(KIND_BLOCKS)}
GRADE_BUTTONS = ((4, 5, 6, 7), (8, 9, 10))
BUTTON_LIMIT = 14
MILESTONE_BUTTON_LIMIT = 28
TEN = Decimal(10)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


# ---------------------------------------------------------------------------
# Веса формулы: {"hw": 0.5, "quiz": 0.2, "exam": 0.3}, {"hw:№1": 0.29, …}
# ---------------------------------------------------------------------------

def parse_weights(raw) -> dict:
    """dict из json или строка «hw=0.5; quiz=0.2» из Google Sheet → {ключ: float}.
    ValueError с понятным текстом, если ключ не распознан или вес не число."""
    if isinstance(raw, dict):
        pairs = list(raw.items())
    else:
        pairs = []
        for part in filter(None, (p.strip() for p in str(raw or '').split(';'))):
            if '=' not in part:
                raise ValueError(f"«{part}» — ожидается ключ=вес")
            key, value = part.split('=', 1)
            pairs.append((key, value))
    weights = {}
    for key, value in pairs:
        key = str(key).strip()
        kind, _, title = key.partition(':')
        if kind not in WEIGHT_KINDS or (_ and not title.strip()):
            raise ValueError(f"ключ «{key}» — ожидается {' | '.join(WEIGHT_KINDS)} или <тип>:<название>")
        try:
            weights[f"{kind}:{title.strip()}" if title else kind] = float(str(value).strip().replace(',', '.'))
        except ValueError:
            raise ValueError(f"вес «{value}» у «{key}» — не число")
    return weights


def weights_sum_ok(weights: dict) -> bool:
    return abs(sum(weights.values()) - 1.0) <= 0.01


@dataclass
class Component:
    key: str
    label: str
    weight: Decimal
    is_exam: bool
    whole_kind: bool       # ключ на весь тип («hw»), а не на одну активность («hw:№1»)
    total: int             # активностей в компоненте
    graded: list           # оценки оценённых

    @property
    def value(self) -> Decimal:
        """Оценка компонента: неоценённое = 0."""
        return sum(self.graded, Decimal(0)) / self.total if self.total else Decimal(0)

    @property
    def average(self):
        """Средняя по оценённым или None."""
        return sum(self.graded, Decimal(0)) / len(self.graded) if self.graded else None


@dataclass
class Score:
    components: list
    accum: Decimal
    max_accum: Decimal
    total: Decimal | None  # итог, если экзамен оценён


def _sort_weight_key(key: str):
    kind, _, title = key.partition(':')
    return KIND_ORDER.get(kind, 99), title


def compute(weights: dict, deadlines: list, marks: dict) -> Score | None:
    """Накоп по весам. None — у предмета нет весов."""
    if not weights:
        return None
    items = [d for d in deadlines if d.progress_role == 'item']
    components = []
    for key in sorted(weights, key=_sort_weight_key):
        kind, _, title = key.partition(':')
        own = [d for d in items if d.kind == kind and (not title or d.title.strip() == title)]
        graded = [Decimal(marks[d.id].grade) for d in own
                  if d.id in marks and marks[d.id].grade is not None]
        label = BLOCK_LABEL.get(kind, kind) if not title else short_label_parts(kind, title)
        components.append(Component(key, label, Decimal(str(weights[key])), kind == 'exam',
                                    not title, len(own), graded))

    regular = [c for c in components if not c.is_exam]
    exams = [c for c in components if c.is_exam]
    accum = sum((c.weight * c.value for c in regular), Decimal(0))
    max_accum = sum((c.weight for c in regular), Decimal(0)) * TEN
    exam_graded = bool(exams) and all(c.total and len(c.graded) == c.total for c in exams)
    total = accum + sum((c.weight * c.value for c in exams), Decimal(0)) if exam_graded else None
    return Score(components, accum, max_accum, total)


# ---------------------------------------------------------------------------
# Форматирование чисел и подписей
# ---------------------------------------------------------------------------

def _q(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def fmt_grade(grade) -> str:
    """Оценка как введена: 8, 7.5 (без .0)."""
    g = _q(Decimal(grade), '0.1')
    return str(int(g)) if g == g.to_integral_value() else str(g)


def fmt_avg(value: Decimal) -> str:
    return str(_q(value, '0.1'))


def fmt_accum(value: Decimal) -> str:
    return str(_q(value, '0.01'))


def parse_grade(text: str):
    """«7,5» / «7.5» / «8» → Decimal с одним знаком в диапазоне 0–10, иначе None."""
    try:
        value = Decimal(text.strip().replace(',', '.'))
    except (InvalidOperation, AttributeError):
        return None
    if not value.is_finite() or not (0 <= value <= 10):
        return None
    return _q(value, '0.1')


def subject_label(subject) -> str:
    """Короткое имя без эмодзи («📜 ВКР» → «ВКР») — для списка и кнопок прогресса."""
    return EMOJI.sub("", display_name(subject)).strip()


def _cut(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def short_label_parts(kind: str, title: str) -> str:
    title = title.strip()
    if not title:
        return SHORT_KIND.get(kind, kind)
    if title.startswith('№'):
        return f"{SHORT_KIND.get(kind, kind)} {title}"
    return re.sub(r"\s*\([^)]*\)", "", title).strip() or title


def short_label(d) -> str:
    """«ДЗ №1», «Квиз №1–4», «Тест №2», «Practice 3», «Экзамен» — для кнопок и подсказок."""
    return _cut(short_label_parts(d.kind, d.title), BUTTON_LIMIT)


def _due(d) -> str:
    s = d.due_date.strftime('%d.%m')
    if d.due_time and d.due_time != END_OF_DAY:
        s += f", {d.due_time.strftime('%H:%M')}"
    return s


def is_done(marks: dict, d) -> bool:
    m = marks.get(d.id)
    return m is not None and m.done_at is not None


def grade_of(marks: dict, d):
    m = marks.get(d.id)
    return m.grade if m is not None else None


def visible(deadlines: list) -> list:
    return sorted((d for d in deadlines if d.progress_role != 'hidden'), key=due_at)


def only_milestones(deadlines: list) -> bool:
    return bool(deadlines) and all(d.kind == 'milestone' for d in deadlines)


# ---------------------------------------------------------------------------
# Экран «📈 Мой прогресс»
# ---------------------------------------------------------------------------

def render_list_line(subject, deadlines: list, marks: dict) -> str:
    shown = visible(deadlines)
    name = escape(subject_label(subject))
    if not shown:
        return f"{name} — {NO_INFO}"
    items = [d for d in shown if d.progress_role == 'item']
    line = f"{name} — ✅ {sum(is_done(marks, d) for d in items)}/{len(items)}"
    if only_milestones(shown):
        return line
    score = compute(subject.grading_weights, deadlines, marks)
    if score is None:
        return f"{line} · формула не задана"
    return f"{line} · <b>{fmt_accum(score.accum)}</b> из {fmt_avg(score.max_accum)}"


def render_list_screen(lines: list) -> str:
    if not lines:
        return f"📈 <b>Мой прогресс</b>\n{NO_INFO}"
    return "📈 <b>Мой прогресс</b>\nСдано и накоп по формуле\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Экран предмета
# ---------------------------------------------------------------------------

def _status(marks: dict, d) -> str:
    if not is_done(marks, d):
        return "☐"
    grade = grade_of(marks, d)
    return f"✅ <b>{fmt_grade(grade)}</b> ·" if grade is not None else "✅"


def format_activity_line(d, marks: dict) -> str:
    if d.kind == 'milestone':
        mark = "✅" if is_done(marks, d) else "☐"
        return f"{mark} {d.due_date:%d.%m} · {escape(d.title)}"
    title = d.title.strip() or SHORT_KIND['exam']
    if d.progress_role == 'bonus':
        title = re.sub(r"\s*\(бонус\)", "", title, flags=re.IGNORECASE)  # слово «бонус» и так в строке
    title = escape(title)
    tail = "<i>бонус</i>" if d.progress_role == 'bonus' else _due(d)
    return f"{_status(marks, d)} {title} · {tail}"


def _render_table(score: Score) -> str:
    rows = []
    for c in score.components:
        if not c.total:
            value, suffix = "—", " · нет в списке"
        else:
            avg = c.average
            value = fmt_avg(avg) if avg is not None else "—"
            suffix = f" · {len(c.graded)} из {c.total}" if c.whole_kind else ""
        rows.append((c.label, value, suffix))
    label_w = max(10, max(len(r[0]) for r in rows) + 2)
    value_w = max(3, max(len(r[1]) for r in rows))
    lines = [f"{label:<{label_w}}{value:>{value_w}}{suffix}" for label, value, suffix in rows]
    return f"<pre>{escape(chr(10).join(lines))}</pre>"


def _render_accum(subject, deadlines: list, marks: dict) -> str:
    parts = ["🧮 <b>Накоп</b>"]
    if subject.grading_formula:
        parts.append(f"<code>Итог = {escape(subject.grading_formula.strip())}</code>")
    score = compute(subject.grading_weights, deadlines, marks)
    if score is None:
        parts.append("<i>формула не задана — накоп не считается</i>")
        return "\n".join(parts)
    parts.append(_render_table(score))
    parts.append(f"<b>Накоп: {fmt_accum(score.accum)}</b> из {fmt_avg(score.max_accum)}")
    if score.total is not None:
        parts.append(f"<b>Итог: {fmt_accum(score.total)}</b>")
        parts.append("<i>особые правила и округление — по правилам курса</i>")
    else:
        parts.append("<i>неоценённое = 0, особые правила не учтены</i>")
    return "\n".join(parts)


def render_subject_screen(subject, deadlines: list, marks: dict, notice: str = "") -> str:
    head = f"<i>{escape(notice)}</i>\n\n" if notice else ""
    title = f"📈 <b>{escape(subject.name)}</b>"
    shown = visible(deadlines)
    if not shown:
        return f"{head}{title}\n\n{NO_INFO}"

    if only_milestones(shown):
        done = sum(is_done(marks, d) for d in shown)
        lines = [format_activity_line(d, marks) for d in shown]
        return f"{head}{title}\nОтмечено {done} из {len(shown)} этапов\n\n" + "\n".join(lines)

    by_kind = defaultdict(list)
    for d in ordered_activities(deadlines):
        by_kind[d.kind].append(d)
    parts = [title]
    for kind, icon, label in KIND_BLOCKS:
        if by_kind[kind]:
            parts.append("\n".join([f"{icon} <b>{label}</b>",
                                    *(format_activity_line(d, marks) for d in by_kind[kind])]))
    parts.append(_render_accum(subject, deadlines, marks))
    return head + "\n\n".join(parts)


def ordered_activities(deadlines: list) -> list:
    """Активности в порядке строк экрана предмета: по блокам, внутри — по сроку, бонусы в конце блока."""
    shown = visible(deadlines)
    if only_milestones(shown):
        return shown
    return sorted(shown, key=lambda d: (KIND_ORDER.get(d.kind, 99), d.progress_role == 'bonus'))


def activity_buttons(deadlines: list, marks: dict) -> list:
    """Строки кнопок [(текст, deadline_id), …]: по две в ряд, этапы — по одной.

    Если у предмета когда-нибудь станет больше 20 активностей — оставить в тексте все
    строки, а кнопки только для незакрытых и последних 6 сданных (сейчас максимум 13 у ВКР).
    """
    rows, pair = [], []
    for d in ordered_activities(deadlines):
        mark = "✅" if is_done(marks, d) else "☐"
        if d.kind == 'milestone':
            if pair:
                rows.append(pair)
                pair = []
            text = _cut(f"{d.due_date:%d.%m} · {d.title.strip()}", MILESTONE_BUTTON_LIMIT)
            rows.append([(f"{mark} {text}", d.id)])
            continue
        pair.append((f"{mark} {short_label(d)}", d.id))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    return rows


# ---------------------------------------------------------------------------
# Экраны оценки и активности
# ---------------------------------------------------------------------------

def _context_line(d) -> str:
    name = escape(subject_label(d.subject))
    if d.progress_role == 'bonus':
        return f"{name} · бонус, в накоп не входит"
    return f"{name} · срок {_due(d)}"


def render_grade_screen(d, current=None, edit: bool = False) -> str:
    """Выбор оценки: сразу после отметки «сдано» или «Изменить / Поставить оценку»."""
    label = escape(short_label(d))
    if not edit:
        return f"✅ <b>{label}</b> отмечено сданным\n{_context_line(d)}\n\nОценка известна?"
    if current is not None:
        return f"<b>{label}</b> · сейчас <b>{fmt_grade(current)}</b>\n{_context_line(d)}\n\nНовая оценка?"
    return f"<b>{label}</b> · оценки нет\n{_context_line(d)}\n\nОценка известна?"


def render_activity_screen(d, grade) -> str:
    label = escape(short_label(d))
    state = f"оценка <b>{fmt_grade(grade)}</b>" if grade is not None else "оценки нет"
    return f"✅ <b>{label}</b> · {state}\n{_context_line(d)}"


def render_input_prompt(d, error: bool = False) -> str:
    hint = "Нужно число" if error else "Отправьте число"
    return (f"✏️ Оценка за <b>{escape(short_label(d))}</b>\n"
            f"{hint} от 0 до 10, например <code>7.5</code>\n/cancel — отмена")
