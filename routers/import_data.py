# import_data.py (v1.2)
"""
Модуль для импорта данных в систему из CSV-файлов.
Предоставляет эндпоинты для массовой загрузки местоположений,
сотрудников, огнетушителей и истории проверок, а также для скачивания шаблонов.

Особенности:

* Файл читается в UTF-8 (с BOM или без) или в Windows-1251 (так сохраняет Excel).
* Разделитель «;», при его отсутствии в заголовке используется «,».
* Ошибочные строки пропускаются, а причина попадает в список ошибок;
  остальные строки импортируются.
* Дубликаты внутри одного файла тоже отлавливаются.
"""
import csv
from datetime import date, datetime, timezone
from io import StringIO
from typing import Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import EDITOR_ROLES, require_role
from db import get_db
from models import Location, Employee, FireExtinguisher, Inspection, Status, User
from status_logic import STATUS_ACTUAL, STATUS_DECOMMISSIONED, recalculate_statuses


router = APIRouter(
    prefix="/import",
    tags=["Import"],
)


class RowError(Exception):
    """Ошибка в конкретной строке CSV, текст попадает в отчет об импорте."""


async def _read_csv(file: UploadFile, required_columns: Iterable[str]) -> csv.DictReader:
    """
    Читает загруженный CSV-файл и проверяет наличие обязательных колонок.

    Args:
        file (UploadFile): Загруженный файл.
        required_columns (Iterable[str]): Колонки, без которых импорт невозможен.

    Returns:
        csv.DictReader: Читатель строк файла.

    Raises:
        HTTPException: Если файл не CSV, не читается или в нем нет нужных колонок.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть в формате CSV",
        )

    content = await file.read()
    try:
        csv_text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            csv_text = content.decode("cp1251")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось определить кодировку файла (ожидается UTF-8 или Windows-1251)",
            )

    first_line = csv_text.split("\n", 1)[0]
    delimiter = ";" if ";" in first_line or "," not in first_line else ","

    reader = csv.DictReader(StringIO(csv_text), delimiter=delimiter)
    headers = [h.strip() for h in (reader.fieldnames or [])]
    reader.fieldnames = headers

    missing = [col for col in required_columns if col not in headers]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="В файле нет обязательных колонок: " + ", ".join(missing),
        )
    return reader


def _cell(row: Dict[str, Optional[str]], column: str) -> str:
    """Возвращает значение ячейки без пробелов по краям (пустая строка, если нет)."""
    return (row.get(column) or "").strip()


def _required(row: Dict[str, Optional[str]], column: str) -> str:
    """Возвращает обязательное значение ячейки или выбрасывает RowError."""
    value = _cell(row, column)
    if not value:
        raise RowError(f"не заполнено поле '{column}'")
    return value


def _parse_date(value: str, column: str) -> Optional[date]:
    """
    Разбирает дату в формате ГГГГ-ММ-ДД или ДД.ММ.ГГГГ.

    Args:
        value (str): Строка с датой (может быть пустой).
        column (str): Название колонки для текста ошибки.

    Returns:
        Optional[date]: Дата или None для пустой строки.

    Raises:
        RowError: Если дата указана в неизвестном формате.
    """
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise RowError(f"неверная дата в поле '{column}': '{value}' (ожидается ГГГГ-ММ-ДД или ДД.ММ.ГГГГ)")


def _parse_float(value: str, column: str) -> Optional[float]:
    """Разбирает число (допускается запятая как разделитель дробной части)."""
    if not value:
        return None
    try:
        return float(value.replace(",", "."))
    except ValueError:
        raise RowError(f"неверное число в поле '{column}': '{value}'")


def _commit(db: Session) -> None:
    """Сохраняет изменения, превращая конфликт уникальности в ошибку 400."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ошибка сохранения, импорт отменен: {exc.orig}",
        )


def _result(created: List[str], errors: List[str]) -> dict:
    """Формирует ответ с итогами импорта."""
    return {"success": len(created), "created": created, "errors": errors}


@router.post("/locations")
async def import_locations(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES))
):
    """
    Импорт мест (локаций) из загружаемого CSV-файла.

    Args:
        file (UploadFile): Файл формата CSV. Требуемый формат колонок: name;description
        db (Session): Сессия базы данных.
        current_user (User): Текущий авторизованный пользователь (проверка прав).

    Returns:
        dict: Статистика импорта (количество успешно созданных записей, список созданных, список ошибок).
    """
    reader = await _read_csv(file, ["name"])

    existing_names = {name for (name,) in db.query(Location.name).all()}
    created: List[str] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            name = _required(row, "name")
            if name in existing_names:
                raise RowError(f"место '{name}' уже существует")

            db.add(Location(
                name=name,
                description=_cell(row, "description") or None,
                created_at=datetime.now(timezone.utc),
            ))
            existing_names.add(name)
            created.append(name)
        except RowError as e:
            errors.append(f"Строка {row_num}: {e}")

    _commit(db)
    return _result(created, errors)


@router.post("/employees")
async def import_employees(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES))
):
    """
    Импорт списка сотрудников из загружаемого CSV-файла.
    Сотрудник с тем же ФИО и должностью повторно не создается.

    Args:
        file (UploadFile): Файл формата CSV. Требуемый формат колонок: full_name;position
        db (Session): Сессия базы данных.
        current_user (User): Текущий авторизованный пользователь.

    Returns:
        dict: Статистика импорта.
    """
    reader = await _read_csv(file, ["full_name", "position"])

    existing = {(e.full_name, e.position) for e in db.query(Employee).all()}
    created: List[str] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            full_name = _required(row, "full_name")
            position = _required(row, "position")
            if (full_name, position) in existing:
                raise RowError(f"сотрудник '{full_name}' уже существует")

            db.add(Employee(
                full_name=full_name,
                position=position,
                created_at=datetime.now(timezone.utc),
            ))
            existing.add((full_name, position))
            created.append(full_name)
        except RowError as e:
            errors.append(f"Строка {row_num}: {e}")

    _commit(db)
    return _result(created, errors)


@router.post("/extinguishers")
async def import_extinguishers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES))
):
    """
    Импорт реестра огнетушителей из загружаемого CSV-файла.

    Связывает огнетушители с существующими локациями и статусами по их названиям.
    Формат колонок: inventory_number;type;capacity;manufacturer;manufacture_date;commissioning_date;location_name;status_name

    Args:
        file (UploadFile): Файл формата CSV.
        db (Session): Сессия базы данных.
        current_user (User): Текущий авторизованный пользователь.

    Returns:
        dict: Статистика импорта.
    """
    reader = await _read_csv(
        file, ["inventory_number", "type", "capacity", "location_name"])

    existing_numbers = {n for (n,) in db.query(FireExtinguisher.inventory_number).all()}
    locations = {loc.name: loc.id for loc in db.query(Location).all()}
    statuses = {st.name: st.id for st in db.query(Status).all()}
    today = date.today()

    created: List[str] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            number = _required(row, "inventory_number")
            if number in existing_numbers:
                raise RowError(f"огнетушитель '{number}' уже существует")

            location_name = _required(row, "location_name")
            if location_name not in locations:
                raise RowError(f"место '{location_name}' не найдено")

            status_name = _cell(row, "status_name") or STATUS_ACTUAL
            if status_name not in statuses:
                raise RowError(f"статус '{status_name}' не найден")

            capacity = _parse_float(_required(row, "capacity"), "capacity")
            if capacity is None or capacity <= 0:
                raise RowError("вместимость должна быть больше нуля")

            manufacture_date = _parse_date(_cell(row, "manufacture_date"), "manufacture_date")
            commissioning_date = _parse_date(_cell(row, "commissioning_date"), "commissioning_date")
            for value, column in ((manufacture_date, "manufacture_date"),
                                  (commissioning_date, "commissioning_date")):
                if value and value > today:
                    raise RowError(f"дата в поле '{column}' не может быть из будущего")

            now = datetime.now(timezone.utc)
            db.add(FireExtinguisher(
                inventory_number=number,
                type=_required(row, "type"),
                capacity=capacity,
                manufacturer=_cell(row, "manufacturer") or None,
                manufacture_date=manufacture_date,
                commissioning_date=commissioning_date,
                location_id=locations[location_name],
                status_id=statuses[status_name],
                created_at=now,
                updated_at=now,
            ))
            existing_numbers.add(number)
            created.append(number)
        except RowError as e:
            errors.append(f"Строка {row_num}: {e}")

    _commit(db)
    return _result(created, errors)


@router.post("/inspections")
async def import_inspections(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(EDITOR_ROLES))
):
    """
    Импорт истории проверок из загружаемого CSV-файла.

    Связывает проверки с огнетушителями (по инвентарному номеру) и сотрудниками (по ФИО).
    После импорта статусы затронутых огнетушителей пересчитываются.

    Args:
        file (UploadFile): Файл формата CSV. Формат совпадает с экспортируемым журналом.
        db (Session): Сессия базы данных.
        current_user (User): Текущий авторизованный пользователь.

    Returns:
        dict: Статистика импорта.
    """
    reader = await _read_csv(file, [
        "Дата проверки", "Инвентарный номер", "ФИО проверяющего",
        "Дата следующей проверки",
    ])

    extinguishers = {fe.inventory_number: fe for fe in db.query(FireExtinguisher).all()}
    employees: Dict[str, Employee] = {}
    for emp in db.query(Employee).order_by(Employee.id).all():
        employees.setdefault(emp.full_name, emp)
    today = date.today()

    created: List[str] = []
    errors: List[str] = []
    touched_ids = set()

    for row_num, row in enumerate(reader, start=2):
        try:
            number = _required(row, "Инвентарный номер")
            extinguisher = extinguishers.get(number)
            if extinguisher is None:
                raise RowError(f"огнетушитель '{number}' не найден")

            employee_name = _required(row, "ФИО проверяющего")
            employee = employees.get(employee_name)
            if employee is None:
                raise RowError(f"сотрудник '{employee_name}' не найден")

            inspection_date = _parse_date(_required(row, "Дата проверки"), "Дата проверки")
            next_inspection_date = _parse_date(
                _required(row, "Дата следующей проверки"), "Дата следующей проверки")
            if inspection_date > today:
                raise RowError("дата проверки не может быть из будущего")
            if next_inspection_date < inspection_date:
                raise RowError("дата следующей проверки раньше даты проверки")

            now = datetime.now(timezone.utc)
            db.add(Inspection(
                fire_extinguisher_id=extinguisher.id,
                inspection_date=inspection_date,
                employee_id=employee.id,
                pressure=_parse_float(_cell(row, "Давление"), "Давление"),
                weight=_parse_float(_cell(row, "Вес"), "Вес"),
                visual_inspection=_cell(row, "Визуальный осмотр") or None,
                seal_condition=_cell(row, "Состояние пломбы") or None,
                safety_pin_condition=_cell(row, "Состояние чеки") or None,
                hose_condition=_cell(row, "Состояние шланга") or None,
                comments=_cell(row, "Комментарии") or None,
                next_inspection_date=next_inspection_date,
                created_at=now,
            ))
            extinguisher.updated_at = now
            touched_ids.add(extinguisher.id)
            created.append(f"{number} - {inspection_date.isoformat()}")
        except RowError as e:
            errors.append(f"Строка {row_num}: {e}")

    _commit(db)
    recalculate_statuses(db, extinguisher_ids=touched_ids,
                         keep_manual=[STATUS_DECOMMISSIONED])
    return _result(created, errors)


def _csv_response(csv_content: str, filename: str) -> StreamingResponse:
    """Отдает CSV-строку как файл (UTF-8 с BOM для корректного открытия в Excel)."""
    return StreamingResponse(
        iter(["﻿" + csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/templates/locations")
def download_locations_template():
    """
    Отдает шаблон CSV-файла для импорта местоположений.

    Returns:
        StreamingResponse: Файл CSV с заголовками и примером данных.
    """
    csv_content = "name;description\n"
    csv_content += "Кабинет 101;Первый этаж административного корпуса\n"
    csv_content += "Коридор 2 этаж;Второй этаж возле лестницы\n"

    return _csv_response(csv_content, "locations_template.csv")


@router.get("/templates/employees")
def download_employees_template():
    """
    Отдает шаблон CSV-файла для импорта сотрудников.

    Returns:
        StreamingResponse: Файл CSV с заголовками и примером данных.
    """
    csv_content = "full_name;position\n"
    csv_content += (
        "Иванов Иван Иванович;Инженер по технике безопасности\n"
    )
    csv_content += "Петров Петр Петрович;Инспектор\n"

    return _csv_response(csv_content, "employees_template.csv")


@router.get("/templates/extinguishers")
def download_extinguishers_template():
    """
    Отдает шаблон CSV-файла для импорта огнетушителей.

    Returns:
        StreamingResponse: Файл CSV с заголовками и примером данных.
    """
    csv_content = (
        "inventory_number;type;capacity;manufacturer;manufacture_date;"
        "commissioning_date;location_name;status_name\n"
    )
    csv_content += (
        "ОУ-001;ОУ-8;8.0;ПожТехника;2023-05-15;2023-06-01;"
        "Кабинет 101;Актуально\n"
    )
    csv_content += (
        "ОП-002;ОП-5;5.0;ТПКН;2024-01-10;2024-02-01;"
        "Коридор 2 этаж;Актуально\n"
    )

    return _csv_response(csv_content, "extinguishers_template.csv")


@router.get("/templates/inspections")
def download_inspections_template():
    """
    Отдает шаблон CSV-файла для импорта проверок оборудования.

    Returns:
        StreamingResponse: Файл CSV с заголовками и примером данных.
    """
    csv_content = (
        "Дата проверки;Инвентарный номер;Тип;Место расположения;"
        "Статус;ФИО проверяющего;Должность;Давление;Вес;Визуальный осмотр;"
        "Состояние пломбы;Состояние чеки;Состояние шланга;Комментарии;"
        "Дата следующей проверки\n"
    )
    csv_content += (
        "15.11.2023;ОУ-001;ОУ-8;Кабинет 101;Актуально;Иванов Иван Иванович;"
        "Инженер по ТБ;1.6;7.9;Исправен;Цела;Исправна;Исправен;"
        "Замечаний нет;15.05.2024\n"
    )

    return _csv_response(csv_content, "inspections_template.csv")
