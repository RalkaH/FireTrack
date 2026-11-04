# deadlines.py (v1.0)
"""
Сроки перезарядки и срок службы огнетушителей.

Плановые осмотры считаются по журналу проверок (``status_logic``), а здесь
считаются два других срока:

1. **Перезарядка.** Интервал зависит от вида огнетушащего вещества (ОТВ),
   который определяется по префиксу типа: ОВ и ОВЭ (вода), ОВП (пена),
   ОП (порошок), ОУ (углекислота), ОХ (хладон). Интервалы по умолчанию
   берутся из настроек (таблица 1 СП 9.13130.2009) и могут быть
   переопределены в карточке огнетушителя. Отсчет ведется от даты
   последней перезарядки, а если ее нет, от даты изготовления
   (новый огнетушитель заряжен на заводе) или ввода в эксплуатацию.
2. **Срок службы.** По умолчанию 10 лет (п. 5.53 ГОСТ Р 51057-2001),
   отсчитывается от даты изготовления. После него огнетушитель списывают
   или продлевают срок по решению организации, проводящей ТО.
"""
import calendar
from datetime import date
from typing import Any, Dict, Optional

# Состояния срока
STATE_OK = "ok"
STATE_SOON = "soon"
STATE_OVERDUE = "overdue"
STATE_UNKNOWN = "unknown"

# Вид ОТВ: (ключ настройки, подпись). Порядок важен: длинные префиксы раньше.
AGENT_KINDS = [
    ("ОВП", "foam", "Пена"),
    ("ОВЭ", "water", "Вода с добавками"),
    ("ОВ", "water", "Вода"),
    ("ОП", "powder", "Порошок"),
    ("ОУ", "co2", "Углекислота"),
    ("ОХ", "halon", "Хладон"),
]

# Латинские буквы, которые вводят вместо кириллических в маркировке
# (OP-5 вместо ОП-5, OY вместо ОУ и т.п.)
_LATIN_TO_CYR = str.maketrans({"O": "О", "P": "П", "B": "В", "X": "Х", "Y": "У", "E": "Э"})

_BASIS_LABELS = {
    "last_recharge_date": "последняя перезарядка",
    "manufacture_date": "дата изготовления",
    "commissioning_date": "ввод в эксплуатацию",
}


def agent_kind(extinguisher_type: Optional[str]) -> Optional[Dict[str, str]]:
    """
    Определяет вид огнетушащего вещества по типу огнетушителя.

    Args:
        extinguisher_type (Optional[str]): Тип, например «ОП-5» или «ОУ-3».

    Returns:
        Optional[Dict[str, str]]: ``{"kind": ..., "label": ...}`` или None,
        если вид определить не удалось.
    """
    text = (extinguisher_type or "").strip().upper().translate(_LATIN_TO_CYR)
    for prefix, kind, label in AGENT_KINDS:
        if text.startswith(prefix):
            return {"kind": kind, "label": label}
    return None


def add_months(value: date, months: int) -> date:
    """
    Прибавляет к дате месяцы. Если такого дня в месяце нет, берется последний.

    Args:
        value (date): Исходная дата.
        months (int): Число месяцев.

    Returns:
        date: Новая дата.
    """
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _state(deadline: Optional[date], today: date, warning_days: int) -> str:
    """Состояние срока относительно сегодняшней даты."""
    if deadline is None:
        return STATE_UNKNOWN
    if deadline < today:
        return STATE_OVERDUE
    if (deadline - today).days <= warning_days:
        return STATE_SOON
    return STATE_OK


def compute_deadlines(fe, settings: Dict[str, Any], today: Optional[date] = None) -> Dict[str, Any]:
    """
    Считает сроки перезарядки и службы одного огнетушителя.

    Args:
        fe (FireExtinguisher): Огнетушитель.
        settings (Dict[str, Any]): Настройки из ``app_settings.get_settings``.
        today (Optional[date]): Текущая дата (для тестов).

    Returns:
        Dict[str, Any]: Вид ОТВ, интервал, база отсчета, дата следующей
        перезарядки, конец срока службы, их состояния и остаток в днях.
    """
    today = today or date.today()
    warning_days = int(settings.get("recharge_warning_days", 60))
    kind = agent_kind(fe.type)

    interval = fe.recharge_interval_months
    interval_source = "карточка" if interval else None
    if not interval and kind is not None:
        interval = settings.get(f"recharge_months_{kind['kind']}")
        interval_source = "настройки" if interval else None

    basis_field = next(
        (f for f in ("last_recharge_date", "manufacture_date", "commissioning_date")
         if getattr(fe, f, None)),
        None,
    )
    basis_date = getattr(fe, basis_field) if basis_field else None
    next_recharge = add_months(basis_date, int(interval)) if basis_date and interval else None

    life_years = fe.service_life_years or settings.get("service_life_years")
    life_basis = fe.manufacture_date or fe.commissioning_date
    service_end = add_months(life_basis, int(life_years) * 12) if life_basis and life_years else None

    return {
        "agent_kind": kind["kind"] if kind else None,
        "agent_label": kind["label"] if kind else None,
        "recharge_interval_months": int(interval) if interval else None,
        "recharge_interval_source": interval_source,
        "recharge_basis": _BASIS_LABELS.get(basis_field) if basis_field else None,
        "recharge_basis_date": basis_date,
        "next_recharge_date": next_recharge,
        "recharge_days_left": (next_recharge - today).days if next_recharge else None,
        "recharge_state": _state(next_recharge, today, warning_days),
        "service_life_years": int(life_years) if life_years else None,
        "service_end_date": service_end,
        "service_days_left": (service_end - today).days if service_end else None,
        "service_state": _state(service_end, today, warning_days),
    }
