# app_settings.py (v1.1)
"""
Настройки приложения, которые админ меняет из интерфейса.

Значения хранятся в таблице ``Settings`` строками. Если ключа в базе нет,
используется значение по умолчанию из :data:`DEFAULTS`. Типы значений
описаны в :data:`TYPES` и приводятся при чтении и проверяются при записи.

Значения по умолчанию взяты из ГОСТ Р 59641-2021 (с Изменением № 1):

* перезарядка: таблица 1 («не реже»), вода и пена 1 раз в год, порошок,
  углекислота и хладон 1 раз в 5 лет;
* проверка: п. 5.1.1, ежегодная;
* испытания: п. 5.1.9 и 5.1.11.2, один раз в пять лет.

Срок службы 10 лет взят из п. 5.53 ГОСТ Р 51057-2001 («не менее 10 лет»
для перезаряжаемого огнетушителя с металлическим корпусом). Если в паспорте
огнетушителя указан другой срок, его задают в карточке огнетушителя.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy.orm import Session

from models import AppSetting

DEFAULTS: Dict[str, Any] = {
    "organization_name": "",
    "responsible_position": "",
    "responsible_name": "",
    "recharge_months_water": 12,
    "recharge_months_foam": 12,
    "recharge_months_powder": 60,
    "recharge_months_co2": 60,
    "recharge_months_halon": 60,
    "service_life_years": 10,
    "inspection_interval_months": 12,
    "test_interval_months": 60,
    "recharge_warning_days": 60,
    "recharge_overdue_needs_service": True,
    "backup_keep_count": 14,
}

TYPES: Dict[str, type] = {key: type(value) for key, value in DEFAULTS.items()}

LABELS: Dict[str, str] = {
    "organization_name": "Название организации (для шапки отчетов)",
    "responsible_position": "Должность ответственного (для подписи)",
    "responsible_name": "ФИО ответственного (для подписи)",
    "recharge_months_water": "Перезарядка водных (ОВ, ОВЭ), месяцев",
    "recharge_months_foam": "Перезарядка пенных (ОВП), месяцев",
    "recharge_months_powder": "Перезарядка порошковых (ОП), месяцев",
    "recharge_months_co2": "Перезарядка углекислотных (ОУ), месяцев",
    "recharge_months_halon": "Перезарядка хладоновых (ОХ), месяцев",
    "service_life_years": "Срок службы по умолчанию, лет",
    "inspection_interval_months": "Следующая проверка через, месяцев",
    "test_interval_months": "Испытания через, месяцев",
    "backup_keep_count": "Хранить автокопий базы, штук",
    "recharge_warning_days": "Предупреждать о перезарядке за, дней",
    "recharge_overdue_needs_service": "Просроченная перезарядка ставит «Требует обслуживания»",
}

# Допустимые диапазоны числовых настроек
LIMITS: Dict[str, tuple] = {
    "recharge_months_water": (1, 240),
    "recharge_months_foam": (1, 240),
    "recharge_months_powder": (1, 240),
    "recharge_months_co2": (1, 240),
    "recharge_months_halon": (1, 240),
    "service_life_years": (1, 50),
    "inspection_interval_months": (1, 60),
    "test_interval_months": (1, 240),
    "backup_keep_count": (1, 365),
    "recharge_warning_days": (1, 365),
}


def _parse(key: str, raw: Any) -> Any:
    """Приводит значение к типу настройки или выбрасывает ValueError."""
    kind = TYPES[key]
    if kind is bool:
        if isinstance(raw, bool):
            return raw
        text = str(raw).strip().lower()
        if text in ("1", "true", "yes", "да", "on"):
            return True
        if text in ("0", "false", "no", "нет", "off", ""):
            return False
        raise ValueError(f"'{key}': ожидается да или нет")
    if kind is int:
        if isinstance(raw, bool):
            raise ValueError(f"'{key}': ожидается целое число")
        try:
            value = int(str(raw).strip())
        except ValueError:
            raise ValueError(f"'{key}': ожидается целое число")
        low, high = LIMITS.get(key, (None, None))
        if low is not None and not (low <= value <= high):
            raise ValueError(f"'{key}': значение должно быть от {low} до {high}")
        return value
    return "" if raw is None else str(raw).strip()


def get_settings(db: Session) -> Dict[str, Any]:
    """
    Возвращает все настройки с учетом значений по умолчанию.

    Args:
        db (Session): Сессия базы данных.

    Returns:
        Dict[str, Any]: Настройки, приведенные к своим типам.
    """
    result = dict(DEFAULTS)
    for row in db.query(AppSetting).all():
        if row.key in DEFAULTS:
            try:
                result[row.key] = _parse(row.key, row.value)
            except ValueError:
                pass  # испорченное значение в базе: остается значение по умолчанию
    return result


def update_settings(db: Session, values: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Проверяет и сохраняет настройки (без commit).

    Args:
        db (Session): Сессия базы данных.
        values (Dict[str, Any]): Новые значения. Неизвестные ключи запрещены.

    Returns:
        Dict[str, Dict[str, Any]]: Изменения в виде {ключ: {"old": ..., "new": ...}}.

    Raises:
        ValueError: Если ключ неизвестен или значение не проходит проверку.
    """
    unknown = [k for k in values if k not in DEFAULTS]
    if unknown:
        raise ValueError("Неизвестные настройки: " + ", ".join(unknown))

    current = get_settings(db)
    parsed = {key: _parse(key, raw) for key, raw in values.items()}
    now = datetime.now(timezone.utc)
    changes = {}
    for key, value in parsed.items():
        if current[key] == value:
            continue
        stored = ("1" if value else "0") if isinstance(value, bool) else str(value)
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=stored, updated_at=now))
        else:
            row.value = stored
            row.updated_at = now
        changes[key] = {"old": current[key], "new": value}
    return changes
