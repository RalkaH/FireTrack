import csv
from io import StringIO
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db import get_db
from models import Location, Employee, FireExtinguisher, Inspection, Status, User
from auth import require_role


router = APIRouter(
    prefix="/import",
    tags=["Import"],
)


@router.post("/locations")
async def import_locations(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Импорт мест из CSV.
    Формат: name;description
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть в формате CSV",
        )

    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_text), delimiter=";")

    created: List[str] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            existing = (
                db.query(Location)
                .filter(Location.name == row["name"])
                .first()
            )
            if existing is not None:
                errors.append(
                    f"Строка {row_num}: место '{row['name']}' уже существует"
                )
                continue

            location = Location(
                name=row["name"],
                description=row.get("description", ""),
                created_at=datetime.now(timezone.utc),
            )
            db.add(location)
            created.append(row["name"])
        except Exception as e:
            errors.append(f"Строка {row_num}: {str(e)}")

    db.commit()

    return {
        "success": len(created),
        "created": created,
        "errors": errors,
    }


@router.post("/employees")
async def import_employees(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Импорт сотрудников из CSV.
    Формат: full_name;position
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть в формате CSV",
        )

    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_text), delimiter=";")

    created: List[str] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            employee = Employee(
                full_name=row["full_name"],
                position=row["position"],
                created_at=datetime.now(timezone.utc),
            )
            db.add(employee)
            created.append(row["full_name"])
        except Exception as e:
            errors.append(f"Строка {row_num}: {str(e)}")

    db.commit()

    return {
        "success": len(created),
        "created": created,
        "errors": errors,
    }


@router.post("/extinguishers")
async def import_extinguishers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Импорт огнетушителей из CSV.
    Формат: inventory_number;type;capacity;manufacturer;manufacture_date;
            commissioning_date;location_name;status_name
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть в формате CSV",
        )

    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_text), delimiter=";")

    created: List[str] = []
    errors: List[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            # Проверка дубликата по инвентарному номеру
            existing = (
                db.query(FireExtinguisher)
                .filter(FireExtinguisher.inventory_number == row["inventory_number"])
                .first()
            )
            if existing is not None:
                errors.append(
                    f"Строка {row_num}: огнетушитель '{row['inventory_number']}' уже существует"
                )
                continue

            # Найти место по имени
            location = (
                db.query(Location)
                .filter(Location.name == row["location_name"])
                .first()
            )
            if location is None:
                errors.append(
                    f"Строка {row_num}: место '{row['location_name']}' не найдено"
                )
                continue

            # Найти статус по имени (или 'Актуально' по умолчанию)
            status_name = row.get("status_name") or "Актуально"
            status_obj = (
                db.query(Status)
                .filter(Status.name == status_name)
                .first()
            )
            if status_obj is None:
                errors.append(
                    f"Строка {row_num}: статус '{status_name}' не найден"
                )
                continue

            # Парсинг дат
            manufacture_date = None
            if row.get("manufacture_date"):
                try:
                    manufacture_date = datetime.strptime(
                        row["manufacture_date"], "%Y-%m-%d"
                    ).date()
                except Exception:
                    pass

            commissioning_date = None
            if row.get("commissioning_date"):
                try:
                    commissioning_date = datetime.strptime(
                        row["commissioning_date"], "%Y-%m-%d"
                    ).date()
                except Exception:
                    pass

            now = datetime.now(timezone.utc)
            extinguisher = FireExtinguisher(
                inventory_number=row["inventory_number"],
                type=row["type"],
                capacity=float(row["capacity"]),
                manufacturer=row.get("manufacturer", ""),
                manufacture_date=manufacture_date,
                commissioning_date=commissioning_date,
                location_id=location.id,
                status_id=status_obj.id,
                created_at=now,
                updated_at=now,
            )
            db.add(extinguisher)
            created.append(row["inventory_number"])
        except Exception as e:
            errors.append(f"Строка {row_num}: {str(e)}")

    db.commit()

    return {
        "success": len(created),
        "created": created,
        "errors": errors,
    }


@router.post("/inspections")
async def import_inspections(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "engineer"]))
):
    """
    Импорт проверок из CSV.
    Формат совпадает с экспортируемым журналом.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть в формате CSV",
        )

    content = await file.read()
    csv_text = content.decode("utf-8-sig")

    reader = csv.DictReader(StringIO(csv_text), delimiter=";")

    created: list[str] = []
    errors: list[str] = []

    for row_num, row in enumerate(reader, start=2):
        try:
            # Найти огнетушитель по инвентарному номеру
            extinguisher = (
                db.query(FireExtinguisher)
                .filter(FireExtinguisher.inventory_number == row["Инвентарный номер"])
                .first()
            )
            if extinguisher is None:
                errors.append(
                    f"Строка {row_num}: огнетушитель '{row['Инвентарный номер']}' не найден"
                )
                continue

            # Найти сотрудника по ФИО
            employee = (
                db.query(Employee)
                .filter(Employee.full_name == row["ФИО проверяющего"])
                .first()
            )
            if employee is None:
                errors.append(
                    f"Строка {row_num}: сотрудник '{row['ФИО проверяющего']}' не найден"
                )
                continue

            # Парсинг дат - поддержка двух форматов
            try:
                inspection_date_str = row["Дата проверки"].strip()
                next_inspection_str = row["Дата следующей проверки"].strip()
                
                # Попробуем формат дд.мм.гггг
                if "." in inspection_date_str:
                    inspection_date = datetime.strptime(
                        inspection_date_str, "%d.%m.%Y"
                    ).date()
                    next_inspection_date = datetime.strptime(
                        next_inspection_str, "%d.%m.%Y"
                    ).date()
                else:
                    # Формат гггг-мм-дд
                    inspection_date = datetime.strptime(
                        inspection_date_str, "%Y-%m-%d"
                    ).date()
                    next_inspection_date = datetime.strptime(
                        next_inspection_str, "%Y-%m-%d"
                    ).date()
            except Exception as e:
                errors.append(
                    f"Строка {row_num}: ошибка парсинга даты - {str(e)}"
                )
                continue

            # Парсинг числовых значений
            pressure = None
            if row.get("Давление"):
                try:
                    pressure = float(row["Давление"])
                except Exception:
                    pass

            weight = None
            if row.get("Вес"):
                try:
                    weight = float(row["Вес"])
                except Exception:
                    pass

            inspection = Inspection(
                fire_extinguisher_id=extinguisher.id,
                inspection_date=inspection_date,
                employee_id=employee.id,
                pressure=pressure,
                weight=weight,
                visual_inspection=row.get("Визуальный осмотр", ""),
                seal_condition=row.get("Состояние пломбы", ""),
                safety_pin_condition=row.get("Состояние чеки", ""),
                hose_condition=row.get("Состояние шланга", ""),
                comments=row.get("Комментарии", ""),
                next_inspection_date=next_inspection_date,
                created_at=datetime.now(timezone.utc),
            )
            db.add(inspection)
            created.append(
                f"{row['Инвентарный номер']} - {inspection_date}"
            )

            # Обновить updated_at огнетушителя
            extinguisher.updated_at = datetime.now(timezone.utc) # type: ignore[attr-defined]

        except Exception as e:
            errors.append(f"Строка {row_num}: {str(e)}")

    db.commit()

    return {
        "success": len(created),
        "created": created,
        "errors": errors,
    }


@router.get("/templates/locations")
def download_locations_template():
    """Скачать шаблон CSV для импорта мест."""
    csv_content = "name;description\n"
    csv_content += "Кабинет 101;Первый этаж административного корпуса\n"
    csv_content += "Коридор 2 этаж;Второй этаж возле лестницы\n"

    output = StringIO(csv_content)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=locations_template.csv"
        },
    )


@router.get("/templates/employees")
def download_employees_template():
    """Скачать шаблон CSV для импорта сотрудников."""
    csv_content = "full_name;position\n"
    csv_content += (
        "Иванов Иван Иванович;Инженер по технике безопасности\n"
    )
    csv_content += "Петров Петр Петрович;Инспектор\n"

    output = StringIO(csv_content)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=employees_template.csv"
        },
    )


@router.get("/templates/extinguishers")
def download_extinguishers_template():
    """Скачать шаблон CSV для импорта огнетушителей."""
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

    output = StringIO(csv_content)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=extinguishers_template.csv"
        },
    )


@router.get("/templates/inspections")
def download_inspections_template():
    """Скачать шаблон CSV для импорта проверок."""
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

    output = StringIO(csv_content)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=inspections_template.csv"
        },
    )
