# export_utils.py (v1.0)
"""
Защита выгрузок от инъекции формул.

Excel выполняет ячейку CSV как формулу, если она начинается с ``=``, ``+``,
``-`` или ``@``. В выгрузки попадают данные, которые мог ввести кто угодно:
например, логин неудачного входа и User-Agent в журнале действий. Такие
значения экранируются апострофом.
"""
from typing import Any

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: Any) -> Any:
    """
    Делает значение безопасным для ячейки CSV или XLSX.

    Args:
        value (Any): Значение. Числа и даты возвращаются без изменений.

    Returns:
        Any: Исходное значение или строка с апострофом в начале.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value
