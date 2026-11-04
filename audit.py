# audit.py (v1.0)
"""
Журнал действий пользователей (аудит).

Каждое изменяющее действие записывается в таблицу ``AuditLog``: кто, когда,
откуда (IP и User-Agent), что сделал и над каким объектом, а для изменений
дополнительно «было и стало» по каждому полю.

Правила:

1. Запись добавляется в ту же сессию, что и само изменение, и сохраняется
   одним commit вместе с ним. Если изменение откатилось, записи тоже нет.
   Для событий без изменений данных (неудачный вход) используйте
   ``commit=True``.
2. Пароли, хеши и токены в журнал не пишутся никогда: поля с такими
   именами вырезаются из ``changes`` автоматически.
"""
import json
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import AuditLog

# Действия
ACTION_CREATE = "create"
ACTION_UPDATE = "update"
ACTION_DELETE = "delete"
ACTION_IMPORT = "import"
ACTION_LOGIN_SUCCESS = "login_success"
ACTION_LOGIN_FAILED = "login_failed"
ACTION_PASSWORD_CHANGE = "password_change"
ACTION_PASSWORD_RESET = "password_reset"
ACTION_BLOCK = "block"
ACTION_UNBLOCK = "unblock"
ACTION_RECALCULATE = "recalculate"
ACTION_EXPORT = "export"

ACTION_LABELS = {
    ACTION_CREATE: "Создание",
    ACTION_UPDATE: "Изменение",
    ACTION_DELETE: "Удаление",
    ACTION_IMPORT: "Импорт",
    ACTION_LOGIN_SUCCESS: "Вход",
    ACTION_LOGIN_FAILED: "Неудачный вход",
    ACTION_PASSWORD_CHANGE: "Смена пароля",
    ACTION_PASSWORD_RESET: "Сброс пароля",
    ACTION_BLOCK: "Блокировка",
    ACTION_UNBLOCK: "Разблокировка",
    ACTION_RECALCULATE: "Пересчет статусов",
    ACTION_EXPORT: "Выгрузка",
}

ENTITY_LABELS = {
    "extinguisher": "Огнетушитель",
    "inspection": "Проверка",
    "location": "Место",
    "employee": "Сотрудник",
    "status": "Статус",
    "user": "Пользователь",
    "settings": "Настройки",
    "audit": "Журнал действий",
    "report": "Отчет",
}

_SECRET_MARKERS = ("password", "hash", "token", "secret")
_MAX_UA = 300


def _jsonable(value: Any) -> Any:
    """Приводит значение к виду, пригодному для JSON."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_secret(field: str) -> bool:
    """Поле с паролем, хешем или токеном."""
    name = field.lower()
    return any(marker in name for marker in _SECRET_MARKERS)


def snapshot(obj: Any, fields: Iterable[str]) -> Dict[str, Any]:
    """
    Снимок значений полей объекта (для сравнения до и после).

    Args:
        obj (Any): ORM-объект.
        fields (Iterable[str]): Имена полей.

    Returns:
        Dict[str, Any]: Значения полей, приведенные к JSON-виду.
    """
    return {f: _jsonable(getattr(obj, f, None)) for f in fields if not _is_secret(f)}


def diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Разница двух снимков: только изменившиеся поля.

    Args:
        before (Dict[str, Any]): Снимок до изменения.
        after (Dict[str, Any]): Снимок после изменения.

    Returns:
        Dict[str, Dict[str, Any]]: ``{поле: {"old": ..., "new": ...}}``.
    """
    result = {}
    for key in sorted(set(before) | set(after)):
        if _is_secret(key):
            continue
        old, new = _jsonable(before.get(key)), _jsonable(after.get(key))
        if old != new:
            result[key] = {"old": old, "new": new}
    return result


def client_ip(request: Optional[Request]) -> Optional[str]:
    """
    IP клиента. Заголовок X-Forwarded-For добавляется в скобках, потому что
    его может подделать сам клиент, и для расследования важно видеть оба.
    """
    if request is None:
        return None
    ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return f"{ip} (XFF: {forwarded[:100]})"
    return ip


def log(
    db: Session,
    request: Optional[Request],
    user: Any,
    action: str,
    summary: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    changes: Optional[Dict[str, Any]] = None,
    username: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    """
    Добавляет запись в журнал действий.

    Args:
        db (Session): Сессия базы данных.
        request (Optional[Request]): Запрос (для IP и User-Agent).
        user (Any): Пользователь, выполнивший действие, или None.
        action (str): Действие (константы ``ACTION_*``).
        summary (str): Понятное человеку описание.
        entity_type (Optional[str]): Тип объекта (ключи ``ENTITY_LABELS``).
        entity_id (Optional[int]): ID объекта.
        changes (Optional[Dict[str, Any]]): Подробности (для update: было и стало).
        username (Optional[str]): Логин, если пользователя нет (неудачный вход).
        commit (bool): Сразу сохранить запись.

    Returns:
        AuditLog: Добавленная запись.
    """
    if changes:
        changes = {k: v for k, v in changes.items() if not _is_secret(k)}
    entry = AuditLog(
        created_at=datetime.now(timezone.utc),
        user_id=getattr(user, "id", None),
        username=getattr(user, "username", None) or username,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary[:500],
        changes=json.dumps(changes, ensure_ascii=False, default=str) if changes else None,
        ip=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:_MAX_UA] if request else None,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
