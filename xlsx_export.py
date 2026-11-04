# xlsx_export.py (v1.0)
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
from openpyxl.worksheet.worksheet import Worksheet

THIN = Side(style="thin", color="7F7F7F")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HEADER_FILL = PatternFill("solid", fgColor="E7ECF3")
ZEBRA_FILL = PatternFill("solid", fgColor="F7F9FC")
ALERT_FILL = PatternFill("solid", fgColor="FDECEC")
WARN_FILL = PatternFill("solid", fgColor="FFF6E0")
DATE_FORMAT = "DD.MM.YYYY"
FONT = "Calibri"


def column(key: str, title: str, width: float = 14, kind: str = "text",
           group: Optional[str] = None) -> Dict[str, Any]:
    """
    Описание колонки таблицы.

    Args:
        key (str): Ключ значения в строке данных.
        title (str): Заголовок колонки.
        width (float): Минимальная ширина в символах.
        kind (str): ``text``, ``date``, ``num`` или ``int``.
        group (Optional[str]): Общий заголовок над несколькими колонками
            (двухуровневая шапка, как в форме Г.2).

    Returns:
        Dict[str, Any]: Описание колонки.
    """
    return {"key": key, "title": title, "width": width, "kind": kind, "group": group}


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
    """Пишет шапку таблицы (одно- или двухуровневую). Возвращает первую строку данных."""
    two_levels = any(c["group"] for c in columns)
    header_font = Font(name=FONT, size=10, bold=True)
    align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def style(cell):
        cell.font = header_font
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = align

    if not two_levels:
        for i, col in enumerate(columns, start=1):
            style(ws.cell(start_row, i, col["title"]))
        ws.row_dimensions[start_row].height = 32
        return start_row + 1

    top, bottom = start_row, start_row + 1
    i = 1
    while i <= len(columns):
        col = columns[i - 1]
        if col["group"]:
            j = i
            while j < len(columns) and columns[j]["group"] == col["group"]:
                j += 1
            ws.merge_cells(start_row=top, start_column=i, end_row=top, end_column=j)
            ws.cell(top, i, col["group"])
            for k in range(i, j + 1):
                ws.cell(bottom, k, columns[k - 1]["title"])
                style(ws.cell(top, k))
                style(ws.cell(bottom, k))
            i = j + 1
        else:
            ws.merge_cells(start_row=top, start_column=i, end_row=bottom, end_column=i)
            ws.cell(top, i, col["title"])
            style(ws.cell(top, i))
            style(ws.cell(bottom, i))
            i += 1
    ws.row_dimensions[top].height = 22
    ws.row_dimensions[bottom].height = 44
    return bottom + 1


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
            value = data.get(col["key"])
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

MAINTENANCE_GROUP = "Техническое обслуживание (вид и дата)"
MAINTENANCE_COLUMNS = [
    column("n", "№ п/п", 5, "int"),
    column("extinguisher", "№ и марка огнетушителя", 16),
    column("units_check", "Проверка узлов огнетушителя", 14, group=MAINTENANCE_GROUP),
    column("agent_check", "Проверка качества ОТВ", 14, group=MAINTENANCE_GROUP),
    column("pressure_check", "Проверка индикатора давления", 14, group=MAINTENANCE_GROUP),
    column("recharge", "Перезарядка огнетушителя", 13, group=MAINTENANCE_GROUP),
    column("units_test", "Испытание узлов огнетушителя", 13, group=MAINTENANCE_GROUP),
    column("remarks", "Замечания о техническом состоянии", 24),
    column("measures", "Принятые меры", 18),
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
    """Журнал ТО огнетушителей по форме Г.2 СП 9.13130.2009."""
    wb = new_workbook()
    add_table_sheet(wb, "Журнал ТО (Г.2)", "Журнал технического обслуживания огнетушителей",
                    MAINTENANCE_COLUMNS, rows, header,
                    [f"Период: {period}",
                     "Форма Г.2 приложения Г СП 9.13130.2009 (рекомендуемая)"])
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

    service = [{**r, "_fill": "alert" if r["state"] == "overdue" else "warn"} for r in summary["service_life"]]
    add_table_sheet(wb, "Срок службы", "Истекает или истек срок службы",
                    [column("inventory_number", "Инв. номер", 12), column("type", "Тип", 9),
                     column("location", "Место", 20),
                     column("service_end", "Окончание срока службы", 14, "date"),
                     column("days_left", "Осталось, дней", 10, "int")],
                    service, header, [day], row_fill_key="_fill",
                    empty_text="Сроки службы в порядке")
    return to_bytes(wb)
