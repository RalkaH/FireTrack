# routers/audit_log.py (v1.1)
"""
Просмотр журнала действий (только для администратора).

Фильтры: период (по дате, UTC), пользователь, действие, тип объекта,
ID объекта и поиск по тексту описания или IP. Результат отдается
страницами, а также целиком в CSV для разбора в Excel или SIEM.
Выгрузка журнала сама попадает в журнал.
"""
import csv
import json
from datetime import date, datetime, time, timedelta, timezone
from io import StringIO
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Query as OrmQuery, Session

import audit
from auth import ROLE_ADMIN, get_current_active_user, require_role
from db import get_db
from export_utils import safe_cell
from models import AuditLog, User
from schemas import AuditPage

router = APIRouter(
    prefix="/audit",
    tags=["Audit"],
    dependencies=[Depends(get_current_active_user)],
)

_admin_only = require_role([ROLE_ADMIN])
CSV_EXPORT_LIMIT = 100_000


def _utc_iso(value: Optional[datetime]) -> Optional[str]:
    """Время из базы (UTC без зоны) в ISO с явной зоной UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def _to_dict(entry: AuditLog) -> dict:
    """Запись журнала в виде словаря для API."""
    try:
        changes = json.loads(entry.changes) if entry.changes else None
    except ValueError:
        changes = {"raw": entry.changes}
    return {
        "id": entry.id,
        "created_at": _utc_iso(entry.created_at),
        "user_id": entry.user_id,
        "username": entry.username,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "summary": entry.summary,
        "changes": changes,
        "ip": entry.ip,
        "user_agent": entry.user_agent,
    }


def _filtered(
    db: Session,
    date_from: Optional[date],
    date_to: Optional[date],
    username: Optional[str],
    action: Optional[str],
    entity_type: Optional[str],
    entity_id: Optional[int],
    q: Optional[str],
) -> OrmQuery:
    """Общий запрос журнала с фильтрами."""
    query = db.query(AuditLog)
    if date_from:
        query = query.filter(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        query = query.filter(AuditLog.created_at < datetime.combine(date_to + timedelta(days=1), time.min))
    if username:
        query = query.filter(AuditLog.username == username)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AuditLog.entity_id == entity_id)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(AuditLog.summary.ilike(pattern), AuditLog.ip.ilike(pattern)))
    return query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())


@router.get("/", response_model=AuditPage)
def list_audit(
    date_from: Optional[date] = Query(None, description="С даты (UTC), включительно"),
    date_to: Optional[date] = Query(None, description="По дату (UTC), включительно"),
    username: Optional[str] = Query(None, description="Логин"),
    action: Optional[str] = Query(None, description="Действие"),
    entity_type: Optional[str] = Query(None, description="Тип объекта"),
    entity_id: Optional[int] = Query(None, description="ID объекта"),
    q: Optional[str] = Query(None, description="Поиск по описанию и IP"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(_admin_only),
):
    """
    Страница журнала действий, новые записи сверху.

    Returns:
        dict: ``items``, ``total``, ``page``, ``page_size``.
    """
    query = _filtered(db, date_from, date_to, username, action, entity_type, entity_id, q)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_to_dict(e) for e in items], "total": total,
            "page": page, "page_size": page_size}


@router.get("/meta")
def audit_meta(db: Session = Depends(get_db), _: User = Depends(_admin_only)):
    """
    Справочники для фильтров: действия, типы объектов и логины из журнала.

    Returns:
        dict: ``actions``, ``entity_types`` (ключ и подпись) и ``usernames``.
    """
    usernames = [u for (u,) in db.query(AuditLog.username).distinct().order_by(AuditLog.username) if u]
    return {
        "actions": [{"key": k, "label": v} for k, v in audit.ACTION_LABELS.items()],
        "entity_types": [{"key": k, "label": v} for k, v in audit.ENTITY_LABELS.items()],
        "usernames": usernames,
    }


@router.get("/export.csv")
def export_audit_csv(
    request: Request,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(_admin_only),
):
    """
    Выгрузка журнала действий в CSV (UTF-8 с BOM, разделитель «;»).

    Время в файле в UTC (ISO 8601), изменения в колонке «Изменения» в JSON.

    Returns:
        StreamingResponse: Файл CSV.
    """
    rows = _filtered(db, date_from, date_to, username, action, entity_type,
                     entity_id, q).limit(CSV_EXPORT_LIMIT).all()

    output = StringIO()
    output.write("﻿")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Время (UTC)", "Пользователь", "ID пользователя", "Действие",
                     "Тип объекта", "ID объекта", "Описание", "Изменения", "IP", "User-Agent"])
    for e in rows:
        writer.writerow([safe_cell(value) for value in (
            e.id, _utc_iso(e.created_at), e.username, e.user_id,
            audit.ACTION_LABELS.get(e.action, e.action),
            audit.ENTITY_LABELS.get(e.entity_type, e.entity_type), e.entity_id,
            e.summary, e.changes or "", e.ip, e.user_agent,
        )])

    audit.log(db, request, current_user, audit.ACTION_EXPORT,
              f"Выгрузка журнала действий в CSV ({len(rows)} записей)",
              entity_type="audit", commit=True)

    output.seek(0)
    filename = f"audit_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
