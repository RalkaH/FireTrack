# xlsx_export.py (v1.1)
"""
Оформленные отчеты в Excel (XLSX) через openpyxl.

Каждый лист устроен одинаково: название организации, заголовок отчета,
период и дата формирования, таблица с границами, закрепленной шапкой,
переносом текста и форматом дат ДД.ММ.ГГГГ, а в конце строки для подписи
ответственного. Настройки печати: A4, альбомная ориентация, вписать по
ширине страницы, шапка таблицы повторяется на каждой странице, внизу
номер страницы.
"""
from datetime import date, datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Sequence

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.pagebreak import Break
from openpyxl.worksheet.worksheet import Worksheet

from export_utils import safe_cell

THIN = Side(style="thin", color="7F7F7F")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="E7ECF3")
ZEBRA_FILL = PatternFill("solid", fgColor="F7F9FC")
ALERT_FILL = PatternFill("solid", fgColor="FDECEC")
WARN_FILL = PatternFill("solid", fgColor="FFF6E0")
DATE_FORMAT = "DD.MM.YYYY"
FONT = "Calibri"


def column(key: str, title: str, width: float = 14, kind: str = "text") -> Dict[str, Any]:
    """
    Описание колонки таблицы.

    Args:
        key (str): Ключ значения в строке данных.
        title (str): Заголовок колонки.
        width (float): Минимальная ширина в символах.
        kind (str): ``text``, ``date``, ``num`` или ``int``.

    Returns:
        Dict[str, Any]: Описание колонки.
    """
    return {"key": key, "title": title, "width": width, "kind": kind}


def _write_header_block(ws: Worksheet, ncols: int, organization: str, title: str,
                        lines: Sequence[str]) -> int:
    """Пишет шапку листа и возвращает номер следующей свободной строки."""
    last = get_column_letter(ncols)
    row = 1
    if organization:
        ws.merge_cells(f"A{row}:{last}{row}")
        ws.cell(row, 1, organization).font = Font(name=FONT, size=11, bold=True)
        row += 1
    ws.merge_cells(f"A{row}:{last}{row}")
    cell = ws.cell(row, 1, title)
    cell.font = Font(name=FONT, size=14, bold=True)
    cell.alignment = Alignment(horizontal="center")
    ws.row_dimensions[row].height = 22
    row += 1
    for line in lines:
        ws.merge_cells(f"A{row}:{last}{row}")
        c = ws.cell(row, 1, line)
        c.font = Font(name=FONT, size=10, color="404040")
        c.alignment = Alignment(horizontal="center")
        row += 1
    return row + 1


def _write_table_header(ws: Worksheet, start_row: int, columns: List[Dict[str, Any]]) -> int:
    """Пишет шапку таблицы. Возвращает номер первой строки данных."""
    for i, col in enumerate(columns, start=1):
        cell = ws.cell(start_row, i, col["title"])
        cell.font = Font(name=FONT, size=10, bold=True)
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    longest = max(len(col["title"]) / max(col["width"], 1) for col in columns)
    ws.row_dimensions[start_row].height = max(32, 15 * (int(longest) + 1))
    return start_row + 1


def _display_len(value: Any) -> int:
    """Длина значения в символах для автоширины."""
    if value is None:
        return 0
    if isinstance(value, (date, datetime)):
        return 10
    return max(len(part) for part in str(value).split("\n"))


def add_table_sheet(
    wb: Workbook,
    sheet_title: str,
    report_title: str,
    columns: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
    header: Dict[str, str],
    info_lines: Sequence[str] = (),
    row_fill_key: Optional[str] = None,
    signature: bool = True,
    empty_text: str = "Нет данных",
) -> Worksheet:
    """
    Добавляет в книгу лист с оформленной таблицей.

    Args:
        wb (Workbook): Книга Excel.
        sheet_title (str): Название листа (до 31 символа).
        report_title (str): Заголовок отчета над таблицей.
        columns (List[Dict[str, Any]]): Колонки (см. :func:`column`).
        rows (List[Dict[str, Any]]): Строки данных.
        header (Dict[str, str]): Организация и ответственный из настроек.
        info_lines (Sequence[str]): Строки под заголовком (период и т.п.).
        row_fill_key (Optional[str]): Ключ строки со значением ``alert``
            или ``warn`` для подсветки.
        signature (bool): Добавить строки для подписи.
        empty_text (str): Текст, если строк нет.

    Returns:
        Worksheet: Созданный лист.
    """
    ws = wb.create_sheet(sheet_title[:31])
    ncols = len(columns)
    lines = list(info_lines) + [f"Сформирован {datetime.now():%d.%m.%Y %H:%M}"]
    header_row = _write_header_block(ws, ncols, header.get("organization_name", ""),
                                     report_title, lines)
    first_data = _write_table_header(ws, header_row, columns)
    ws.freeze_panes = ws.cell(first_data, 1)
    ws.print_title_rows = f"{header_row}:{first_data - 1}"

    widths = [max(c["width"], _display_len(c["title"]) * 0.6) for c in columns]
    data_font = Font(name=FONT, size=10)
    row_idx = first_data
    if not rows:
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=ncols)
        c = ws.cell(row_idx, 1, empty_text)
        c.font = Font(name=FONT, size=10, italic=True, color="7F7F7F")
        c.alignment = Alignment(horizontal="center")
        for k in range(1, ncols + 1):
            ws.cell(row_idx, k).border = BORDER
        row_idx += 1

    for n, data in enumerate(rows):
        fill = None
        if row_fill_key:
            fill = {"alert": ALERT_FILL, "warn": WARN_FILL}.get(data.get(row_fill_key))
        if fill is None and n % 2 == 1:
            fill = ZEBRA_FILL
        for i, col in enumerate(columns, start=1):
            value = safe_cell(data.get(col["key"]))
            if value == "":
                value = None
            cell = ws.cell(row_idx, i, value)
            cell.font = data_font
            cell.border = BORDER
            if fill is not None:
                cell.fill = fill
            if col["kind"] == "date":
                cell.number_format = DATE_FORMAT
                cell.alignment = Alignment(horizontal="center", vertical="top")
            elif col["kind"] in ("num", "int"):
                cell.alignment = Alignment(horizontal="right", vertical="top")
                if col["kind"] == "num":
                    cell.number_format = "0.0#"
            else:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            widths[i - 1] = max(widths[i - 1], min(_display_len(value) + 2, 48))
        row_idx += 1

    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width

    if signature:
        row_idx += 2
        position = header.get("responsible_position") or "Ответственный за пожарную безопасность"
        name = header.get("responsible_name") or ""
        ws.cell(row_idx, 1, position).font = data_font
        sign_col = max(2, ncols - 3)
        ws.cell(row_idx, sign_col, "_______________").font = data_font
        ws.cell(row_idx, min(ncols, sign_col + 2), f"/ {name or '________________'} /").font = data_font
        ws.cell(row_idx + 1, sign_col, "(подпись)").font = Font(name=FONT, size=8, color="7F7F7F")
        ws.cell(row_idx + 2, 1, "«___» ____________ 20___ г.").font = data_font

    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5
    ws.oddFooter.center.text = "Страница &P из &N"
    ws.oddFooter.center.size = 8
    return ws


def new_workbook() -> Workbook:
    """Пустая книга без листа по умолчанию."""
    wb = Workbook()
    wb.remove(wb.active)
    return wb


def to_bytes(wb: Workbook) -> bytes:
    """Сохраняет книгу в байты."""
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ---------- Готовые отчеты ----------

JOURNAL_COLUMNS = [
    column("n", "№", 5, "int"),
    column("inspection_date", "Дата проверки", 12, "date"),
    column("inventory_number", "Инв. номер", 12),
    column("type", "Тип", 9),
    column("location", "Место установки", 18),
    column("pressure", "Давление, МПа", 9, "num"),
    column("weight", "Масса, кг", 8, "num"),
    column("visual_inspection", "Внешний осмотр", 12),
    column("seal_condition", "Пломба", 10),
    column("safety_pin_condition", "Чека", 10),
    column("hose_condition", "Шланг", 10),
    column("comments", "Замечания", 22),
    column("next_inspection_date", "Следующая проверка", 12, "date"),
    column("employee", "Проверяющий", 20),
]

MAINTENANCE_COLUMNS = [
    column("n", "№ п/п", 5, "int"),
    column("extinguisher", "Номер и марка огнетушителя", 16),
    column("work", "Дата проведения испытания, перезарядки, ремонта; организация, проводившая техобслуживание или ремонт", 24),
    column("test_result", "Результаты осмотра и испытания на прочность", 30),
    column("next_test_date", "Срок следующего планового испытания", 12, "date"),
    column("recharge_date", "Дата проведения перезарядки огнетушителя", 12, "date"),
    column("agent_brand", "Марка (концентрация) заряженного ОТВ", 13),
    column("post_recharge_result", "Результат осмотра после перезарядки", 16),
    column("next_recharge_date", "Дата следующей плановой перезарядки", 12, "date"),
    column("responsible", "Должность, фамилия, инициалы и подпись ответственного лица", 26),
]


def journal_workbook(rows: List[Dict[str, Any]], header: Dict[str, str], period: str) -> bytes:
    """Журнал проверок за период."""
    wb = new_workbook()
    for r in rows:
        r["_fill"] = "alert" if r.get("defects") else None
        if r.get("defects") and not r.get("comments"):
            r["comments"] = r["defects"]
        elif r.get("defects"):
            r["comments"] = f"{r['defects']}. {r['comments']}"
    add_table_sheet(wb, "Журнал проверок", "Журнал проверок огнетушителей", JOURNAL_COLUMNS,
                    rows, header, [f"Период: {period}", f"Всего проверок: {len(rows)}"],
                    row_fill_key="_fill")
    return to_bytes(wb)


def maintenance_workbook(rows: List[Dict[str, Any]], header: Dict[str, str], period: str) -> bytes:
    """Записи журнала эксплуатации СПЗ по форме А.2 ГОСТ Р 59641-2021."""
    wb = new_workbook()
    add_table_sheet(wb, "Журнал ТО и ремонта (А.2)",
                    "Журнал эксплуатации систем противопожарной защиты: "
                    "техническое обслуживание и ремонт огнетушителей",
                    MAINTENANCE_COLUMNS, rows, header,
                    [f"Период: {period}", "Форма А.2 приложения А ГОСТ Р 59641-2021"])
    return to_bytes(wb)


def cards_workbook(cards: List[Dict[str, Any]], header: Dict[str, str]) -> bytes:
    """Карточки учета огнетушителей по форме А.1 ГОСТ Р 59641-2021, каждая на своей странице."""
    wb = new_workbook()
    ws = wb.create_sheet("Карточки учета (А.1)")
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 44
    label_font = Font(name=FONT, size=11)
    value_font = Font(name=FONT, size=11, bold=True)
    row = 1
    for index, card in enumerate(cards):
        if header.get("organization_name"):
            ws.cell(row, 1, safe_cell(header["organization_name"])).font = Font(name=FONT, size=11, bold=True)
            row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        title = ws.cell(row, 1, f"Карточка учета огнетушителя № {safe_cell(card['number'])}")
        title.font = Font(name=FONT, size=14, bold=True)
        title.alignment = Alignment(horizontal="center")
        row += 1
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        note = ws.cell(row, 1, "Форма А.1 приложения А ГОСТ Р 59641-2021")
        note.font = Font(name=FONT, size=9, color="7F7F7F")
        note.alignment = Alignment(horizontal="center")
        row += 2

        life = f"{card['service_life_years']} лет" if card["service_life_years"] else None
        if life and card["service_end_date"]:
            life += f" (до {card['service_end_date']:%d.%m.%Y})"
        responsible = header.get("responsible_name") or ""
        if header.get("responsible_position"):
            responsible = f"{header['responsible_position']}, {responsible}".rstrip(", ")
        fields = [
            ("1. Номер, присвоенный огнетушителю", card["number"]),
            ("2. Дата размещения огнетушителя на объекте защиты", card["placed_date"]),
            ("3. Место установки огнетушителя", card["location"]),
            ("4. Тип и марка огнетушителя", card["type"]),
            ("5. Завод-изготовитель огнетушителя", card["manufacturer"]),
            ("6. Заводской номер", card["serial_number"]),
            ("7. Дата изготовления огнетушителя", card["manufacture_date"]),
            ("8. Дата очередной перезарядки огнетушителя", card["next_recharge_date"]),
            ("9. Срок службы огнетушителя", life),
            ("10. Ответственное лицо и его подпись", responsible),
        ]
        for label, value in fields:
            left = ws.cell(row, 1, label)
            left.font = label_font
            left.border = BORDER
            left.alignment = Alignment(vertical="center", wrap_text=True)
            right = ws.cell(row, 2, safe_cell(value) if value not in ("", None) else None)
            right.font = value_font
            right.border = BORDER
            right.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            if isinstance(value, date):
                right.number_format = DATE_FORMAT
            ws.row_dimensions[row].height = 30
            row += 1
        if index < len(cards) - 1:
            ws.row_breaks.append(Break(id=row))
            row += 2

    if not cards:
        ws.cell(1, 1, "Нет огнетушителей")
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return to_bytes(wb)


def fleet_workbook(summary: Dict[str, Any], header: Dict[str, str]) -> bytes:
    """Состояние парка: сводка и списки на отдельных листах."""
    wb = new_workbook()
    day = f"на {summary['date']:%d.%m.%Y}"

    status_rows = [{"name": k, "count": v} for k, v in sorted(summary["by_status"].items())]
    status_rows.append({"name": "Всего", "count": summary["total"]})
    ws = add_table_sheet(wb, "Сводка", "Состояние парка огнетушителей",
                         [column("name", "Статус", 32), column("count", "Количество", 12, "int")],
                         status_rows, header, [day], signature=False)
    last = ws.max_row
    ws.cell(last, 1).font = Font(name=FONT, size=10, bold=True)
    ws.cell(last, 2).font = Font(name=FONT, size=10, bold=True)

    add_table_sheet(wb, "По местам", "Огнетушители по местам установки",
                    [column("location", "Место", 30), column("total", "Всего", 10, "int"),
                     column("problems", "Просрочено или требует обслуживания", 18, "int")],
                    summary["by_location"], header, [day], signature=False)

    problems = [{**r, "_fill": "alert"} for r in summary["problems"]]
    add_table_sheet(wb, "Проблемные", "Просроченные и требующие обслуживания",
                    [column("inventory_number", "Инв. номер", 12), column("type", "Тип", 9),
                     column("location", "Место", 20), column("status", "Статус", 20),
                     column("last_inspection", "Последняя проверка", 12, "date"),
                     column("next_inspection", "Срок проверки", 12, "date"),
                     column("days_overdue", "Просрочено, дней", 10, "int")],
                    problems, header, [day], row_fill_key="_fill", signature=False,
                    empty_text="Проблемных огнетушителей нет")

    add_table_sheet(wb, "Ближайшие проверки",
                    f"Плановые проверки в ближайшие {summary['horizon_days']} дней",
                    [column("inventory_number", "Инв. номер", 12), column("type", "Тип", 9),
                     column("location", "Место", 20), column("next_inspection", "Дата проверки", 12, "date"),
                     column("days_left", "Осталось, дней", 10, "int")],
                    summary["upcoming_inspections"], header, [day], signature=False,
                    empty_text="Проверок в этот период нет")

    recharge = [{**r, "_fill": "alert" if r["state"] == "overdue" else "warn"} for r in summary["recharge"]]
    add_table_sheet(wb, "Перезарядка",
                    f"Перезарядка: просрочена или в ближайшие {summary['recharge_warning_days']} дней",
                    [column("inventory_number", "Инв. номер", 12), column("type", "Тип", 9),
                     column("agent", "ОТВ", 12), column("location", "Место", 20),
                     column("next_recharge", "Срок перезарядки", 12, "date"),
                     column("days_left", "Осталось, дней", 10, "int"),
                     column("basis", "Отсчет от", 18)],
                    recharge, header, [day], row_fill_key="_fill", signature=False,
                    empty_text="Перезарядка в ближайшее время не требуется")

    tests = [{**r, "_fill": "alert" if r["state"] == "overdue" else "warn"} for r in summary["tests"]]
    add_table_sheet(wb, "Испытания",
                    "Испытания один раз в пять лет: просрочены или скоро (п. 5.1.9 ГОСТ Р 59641-2021)",
                    [column("inventory_number", "Инв. номер", 12), column("type", "Тип", 9),
                     column("location", "Место", 20), column("next_test", "Срок испытания", 12, "date"),
                     column("days_left", "Осталось, дней", 10, "int")],
                    tests, header, [day], row_fill_key="_fill", signature=False,
                    empty_text="Испытания в ближайшее время не требуются")

    service = [{**r, "_fill": "alert" if r["state"] == "overdue" else "warn"} for r in summary["service_life"]]
    add_table_sheet(wb, "Срок службы", "Истекает или истек срок службы",
                    [column("inventory_number", "Инв. номер", 12), column("type", "Тип", 9),
                     column("location", "Место", 20),
                     column("service_end", "Окончание срока службы", 14, "date"),
                     column("days_left", "Осталось, дней", 10, "int")],
                    service, header, [day], row_fill_key="_fill",
                    empty_text="Сроки службы в порядке")
    return to_bytes(wb)
