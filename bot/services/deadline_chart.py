"""
График дедлайнов на 2 недели: PNG для кнопки «📊 Все на графике» и подпись к фото.
Макет и правила — docs/deadline_chart_design.md, docs/deadline_chart_mock.png.

Рисуем matplotlib в пиксельных координатах (холст 1080 × H, оси = весь холст),
шрифт DejaVu Sans идёт в комплекте с matplotlib — ставить шрифты в образ не нужно.
"""
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams["hatch.linewidth"] = 2 * 72 / 100
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from bot.models import Deadline  # noqa: E402
from bot.services.deadlines import (  # noqa: E402
    END_OF_DAY, KIND_IN_DIGEST, WEEKDAYS, _digest_title, display_name, due_at,
)

WINDOW_DAYS = 14
MAX_ROWS = 11
LATER_MAX = 3

# --- оформление (docs/deadline_chart_design.md) ---
W, PAD = 1080, 48
BG, WEEKEND, AXIS = "#1a1a19", "#232321", "#383835"
TEXT, TEXT_2, MUTED, TODAY_LINE = "#ffffff", "#c3c2b7", "#898781", "#d03b3b"
BLUE, YELLOW, TEAL = "#3987e5", "#c98500", "#199e70"
STYLE = {  # kind → (цвет, маркер, размер маркера px, подпись в легенде)
    'hw':        (BLUE,   'o', 16, "ДЗ"),
    'quiz':      (YELLOW, 'D', 16, "Квиз/КР"),
    'test':      (YELLOW, 's', 16, "КР"),
    'exam':      (YELLOW, '*', 24, "Экзамен"),
    'milestone': (TEAL,   '^', 20, "Этап ВКР"),
}
LEGEND_ORDER = ('hw', 'quiz', 'test', 'exam', 'milestone')
HARD_SUFFIX = " жёсткий"
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")


def pt(px: float) -> float:
    """px → pt при dpi=100 (matplotlib меряет шрифты и маркеры в пунктах)."""
    return px * 72 / 100


@dataclass
class Item:
    deadline: Deadline          # основной срок
    hard: Deadline | None       # жёсткий срок (штраф), если есть пара «… жёсткий»

    @property
    def actual(self) -> Deadline:
        return self.hard or self.deadline

    @property
    def kind(self) -> str:
        return self.deadline.kind


# ---------------------------------------------------------------------------
# Данные
# ---------------------------------------------------------------------------

def merge_penalty_pairs(deadlines: list) -> list:
    """Пары «№1» + «№1 жёсткий (…)» одного предмета и типа → одна строка со штрафом."""
    by_key = {(d.subject_id, d.kind, d.title): d for d in deadlines}
    hard_of, hard_ids = {}, set()
    for d in deadlines:
        if HARD_SUFFIX in d.title:
            base = by_key.get((d.subject_id, d.kind, d.title.split(HARD_SUFFIX, 1)[0].strip()))
            if base is not None:
                hard_of[id(base)] = d
                hard_ids.add(id(d))
    return [Item(d, hard_of.get(id(d))) for d in deadlines if id(d) not in hard_ids]


def split_items(deadlines: list, now: datetime):
    """(в окне, позже) — оба списка отсортированы по актуальному сроку, затем по предмету."""
    today = now.date()
    window_end = today + timedelta(days=WINDOW_DAYS)
    in_window, later = [], []
    for it in merge_penalty_pairs(deadlines):
        if due_at(it.actual) < now:
            continue
        (in_window if it.deadline.due_date <= window_end else later).append(it)
    key = lambda it: (due_at(it.actual), display_name(it.deadline.subject))  # noqa: E731
    return sorted(in_window, key=key), sorted(later, key=key)


def subject_label(it: Item) -> str:
    return EMOJI.sub("", display_name(it.deadline.subject)).strip()


def what_label(it: Item) -> str:
    return " ".join(filter(None, [KIND_IN_DIGEST[it.kind], _digest_title(it.deadline)]))


def _date(d: Deadline) -> str:
    s = d.due_date.strftime('%d.%m')
    if d.due_time and d.due_time != END_OF_DAY:
        s += f", {d.due_time.strftime('%H:%M')}"
    return s


def date_label(it: Item, today: date) -> tuple[str, bool]:
    """Текст правой колонки и флаг «срочно» (сегодня/завтра — жирным)."""
    if it.hard:
        return f"{_date(it.deadline)} → {_date(it.hard)}", False
    left = (it.deadline.due_date - today).days
    if left in (0, 1):
        return ("сегодня" if left == 0 else "завтра"), True
    return _date(it.deadline), False


def cache_key(items: list, today: date) -> str:
    raw = "|".join(f"{it.deadline.id}:{due_at(it.deadline)}:{it.hard and due_at(it.hard)}:"
                   f"{it.deadline.title}:{display_name(it.deadline.subject)}" for it in items)
    return f"{today}:{hashlib.sha1(raw.encode()).hexdigest()[:16]}"


# ---------------------------------------------------------------------------
# Подпись к фото и текст для пустого окна
# ---------------------------------------------------------------------------

def _digest_line(it: Item) -> str:
    return f"{escape(display_name(it.deadline.subject))} — {escape(what_label(it))}"


def _later_block(later: list) -> list:
    if not later:
        return []
    lines = ["<b>Позже:</b>"]
    for it in later[:LATER_MAX]:
        when = f"{_date(it.deadline)} → {_date(it.hard)}" if it.hard else _date(it.deadline)
        lines.append(f"{_digest_line(it)} · {when}")
    if len(later) > LATER_MAX:
        lines.append(f"<i>и ещё {len(later) - LATER_MAX} — в карточках предметов</i>")
    return lines


def render_caption(in_window: list, later: list, today: date) -> str:
    first = in_window[0]
    left = (first.actual.due_date - today).days
    when = {0: "сегодня", 1: "завтра"}.get(left, f"осталось {left} дн")
    lines = [f"{'❗ ' if left < 2 else ''}<b>Ближайший:</b> {_digest_line(first)}, {when}"]
    if len(in_window) > MAX_ROWS:
        end = (today + timedelta(days=WINDOW_DAYS)).strftime('%d.%m')
        lines.append(f"<i>и ещё {len(in_window) - MAX_ROWS} до {end} — не поместились на график</i>")
    return "\n".join(lines + _later_block(later))


def render_empty(later: list) -> str:
    text = "⏳ <b>Дедлайны на 2 недели</b>\n<i>нет информации</i>"
    block = _later_block(later)
    return text + ("\n\n" + "\n".join(block) if block else "")


# ---------------------------------------------------------------------------
# Картинка
# ---------------------------------------------------------------------------

def _fit(ax, renderer, text: str, max_w: float, size: float) -> str:
    """Обрезать подпись по слову с «…», чтобы она не заходила на колонку дат."""
    def width(s):
        t = ax.text(0, 0, s, fontsize=pt(size))
        w = t.get_window_extent(renderer).width
        t.remove()
        return w
    if width(text) <= max_w:
        return text
    words = text.split(" ")
    while len(words) > 1:
        words.pop()
        cand = " ".join(words).rstrip(" ·,") + "…"
        if width(cand) <= max_w:
            return cand
    return text


def render(items: list, today: date) -> bytes:
    rows = items[:MAX_ROWS]
    H = min(1350, max(720, 240 + 92 * len(rows) + 48))
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    renderer = fig.canvas.get_renderer()

    x0, x1 = PAD, W - PAD
    day_w = (x1 - x0) / WINDOW_DAYS
    X = lambda n: x0 + n * day_w  # noqa: E731  (n — дней от сегодня)
    first_row, step = 240, 92
    grid_top, grid_bottom = 216, H - PAD + 14

    # заголовок и диапазон
    end = today + timedelta(days=WINDOW_DAYS)
    ax.text(PAD, PAD, "Дедлайны на 2 недели", fontsize=pt(44), fontweight="bold", color=TEXT, va="top")
    ax.text(W - PAD, PAD + 10, f"{today:%d.%m} – {end:%d.%m}", fontsize=pt(28), color=TEXT_2, va="top", ha="right")

    # легенда: только то, что есть на картинке
    kinds = {it.kind for it in rows}
    legend = [(k, *STYLE[k]) for k in LEGEND_ORDER if k in kinds]
    lx, ly = PAD, 130
    for _k, color, marker, msize, label in legend:
        ax.plot(lx + 10, ly, marker=marker, color=color, markersize=pt(msize + 4), markeredgewidth=0)
        t = ax.text(lx + 28, ly, label, fontsize=pt(28), color=TEXT_2, va="center")
        lx = t.get_window_extent(renderer).x1 + 34
    if any(it.hard for it in rows):
        ax.add_patch(Rectangle((lx, ly - 9), 36, 18, facecolor=BG, edgecolor=TEXT_2, hatch="////", linewidth=0))
        ax.text(lx + 46, ly, "штраф", fontsize=pt(28), color=TEXT_2, va="center")

    # выходные, шкала, засечки
    for n in range(WINDOW_DAYS + 1):
        day = today + timedelta(days=n)
        if day.weekday() == 5:  # сб..пн
            ax.add_patch(Rectangle((X(n), grid_top), min(2, WINDOW_DAYS - n) * day_w, grid_bottom - grid_top,
                                   facecolor=WEEKEND, edgecolor="none", zorder=0))
        elif day.weekday() == 6 and n == 0:
            ax.add_patch(Rectangle((X(0), grid_top), day_w, grid_bottom - grid_top,
                                   facecolor=WEEKEND, edgecolor="none", zorder=0))
        ax.plot([X(n), X(n)], [grid_top, grid_top + 10], color=AXIS, linewidth=pt(2))
        if n == 0:
            ax.text(X(0), 198, "сегодня", fontsize=pt(28), fontweight="bold", color=TEXT, va="center", ha="left")
        elif day.weekday() == 0:
            ha = "right" if n >= WINDOW_DAYS - 1 else "center"
            ax.text(X(n), 198, f"{WEEKDAYS[0]} {day:%d.%m}", fontsize=pt(28), color=MUTED, va="center", ha=ha)
    ax.plot([x0, x1], [grid_top, grid_top], color=AXIS, linewidth=pt(2))

    # строки
    date_col_w = {}
    for i, it in enumerate(rows):
        top = first_row + step * i
        cy = top + 50
        color, marker, msize, _ = STYLE[it.kind]
        text, urgent = date_label(it, today)
        dt = ax.text(x1, top, text, fontsize=pt(32), va="top", ha="right",
                     color=TEXT if urgent else TEXT_2, fontweight="bold" if urgent else "normal")
        date_col_w[i] = dt.get_window_extent(renderer).width
        label = _fit(ax, renderer, f"{subject_label(it)} · {what_label(it)}", x1 - x0 - date_col_w[i] - 24, 32)
        ax.text(x0, top, label, fontsize=pt(32), color=TEXT, va="top", ha="left")

        soft_n = (it.deadline.due_date - today).days
        start = X(0) + 6
        if it.hard:
            hard_n = (it.hard.due_date - today).days
            hatch_from = X(max(soft_n, 0))
            hatch_to = X(min(hard_n, WINDOW_DAYS))
            if soft_n > 0:
                ax.add_patch(FancyBboxPatch((start, cy - 9), hatch_from - start, 18,
                                            boxstyle="round,pad=0,rounding_size=4",
                                            facecolor=color, edgecolor="none", zorder=2))
            hs = max(hatch_from, start)
            if hatch_to > hs:
                ax.add_patch(Rectangle((hs, cy - 9), hatch_to - hs, 18, facecolor=BG, edgecolor=color,
                                       hatch="////", linewidth=0, zorder=2))
                ax.plot([hs, hatch_to], [cy - 9, cy - 9], color=color, linewidth=pt(2), zorder=3)
                ax.plot([hs, hatch_to], [cy + 9, cy + 9], color=color, linewidth=pt(2), zorder=3)
            mark_x = X(hard_n) if hard_n <= WINDOW_DAYS else X(soft_n)
        else:
            mark_x = X(soft_n)
            ax.add_patch(FancyBboxPatch((start, cy - 9), max(mark_x - start, 4), 18,
                                        boxstyle="round,pad=0,rounding_size=4",
                                        facecolor=color, edgecolor="none", zorder=2))
        ax.plot(mark_x, cy, marker=marker, color=color, markersize=pt(msize),
                markeredgecolor=BG, markeredgewidth=pt(3), zorder=4)

    # «сегодня»
    ax.plot([X(0), X(0)], [grid_top, grid_bottom], color=TODAY_LINE, linewidth=pt(3), zorder=5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=BG, dpi=100)
    plt.close(fig)
    return buf.getvalue()
