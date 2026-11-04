# tests/test_reports.py
"""Тесты отчетов для печати (XLSX и JSON для страницы печати)."""
from datetime import date, timedelta
from io import BytesIO

from openpyxl import load_workbook


def _seed(client, headers, base_refs, make_extinguisher):
    ext = make_extinguisher(type="ОУ-5", last_recharge_date=(date.today() - timedelta(days=3)).isoformat())
    today = date.today()
    client.post("/inspections/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "employee_id": base_refs["employee_id"],
        "inspection_date": today.isoformat(), "pressure": 1.5, "weight": 7.8,
        "seal_condition": "Повреждена", "comments": "Заменить пломбу",
    })
    return ext


def test_journal_xlsx(client, headers, base_refs, make_extinguisher):
    ext = _seed(client, headers, base_refs, make_extinguisher)
    today = date.today().isoformat()
    resp = client.get("/reports/journal.xlsx", headers=headers,
                      params={"date_from": today, "date_to": today})
    assert resp.status_code == 200, resp.text
    assert "spreadsheetml" in resp.headers["content-type"]
    wb = load_workbook(BytesIO(resp.content))
    ws = wb["Журнал проверок"]
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    assert "Журнал проверок огнетушителей" in texts
    assert ext["inventory_number"] in texts
    assert any("пломба: повреждена" in t for t in texts)
    assert ws.freeze_panes is not None
    assert ws.page_setup.orientation == "landscape"


def test_maintenance_form_g2(client, headers, base_refs, make_extinguisher):
    ext = _seed(client, headers, base_refs, make_extinguisher)
    data = client.get("/reports/print/maintenance", headers=headers).json()
    mine = [r for r in data["rows"] if r["extinguisher"].startswith(ext["inventory_number"])]
    assert any(r["recharge"] for r in mine)          # строка перезарядки
    assert any("1.5 МПа" in r["pressure_check"] for r in mine)
    assert any("масса 7.8 кг" in r["agent_check"] for r in mine)

    resp = client.get("/reports/maintenance.xlsx", headers=headers)
    assert resp.status_code == 200
    ws = load_workbook(BytesIO(resp.content)).active
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    assert "Техническое обслуживание (вид и дата)" in texts
    assert "Перезарядка огнетушителя" in texts


def test_fleet_report(client, headers, base_refs, make_extinguisher):
    _seed(client, headers, base_refs, make_extinguisher)
    data = client.get("/reports/print/fleet", headers=headers).json()
    summary = data["summary"]
    assert summary["total"] >= 1
    assert sum(summary["by_status"].values()) == summary["total"]
    assert "organization_name" in data["header"]

    resp = client.get("/reports/fleet.xlsx", headers=headers)
    assert resp.status_code == 200
    wb = load_workbook(BytesIO(resp.content))
    assert wb.sheetnames == ["Сводка", "По местам", "Проблемные", "Ближайшие проверки",
                             "Перезарядка", "Срок службы"]


def test_report_export_logged(client, headers):
    client.get("/reports/fleet.xlsx", headers=headers)
    items = client.get("/audit/", headers=headers, params={"action": "export", "entity_type": "report"}).json()
    assert items["total"] >= 1


def test_viewer_can_download_reports(client, make_user):
    _, vh = make_user("viewer")
    assert client.get("/reports/journal.xlsx", headers=vh).status_code == 200
    assert client.get("/reports/print/journal", headers=vh).status_code == 200
