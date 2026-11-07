# tests/test_reports.py
"""Тесты отчетов для печати (XLSX и JSON для страницы печати)."""
from datetime import date, timedelta
from io import BytesIO

from openpyxl import load_workbook


def _seed(client, headers, base_refs, make_extinguisher):
    ext = make_extinguisher(type="ОУ-5", serial_number="ЗН-777", manufacturer="Завод",
                            last_recharge_date=(date.today() - timedelta(days=3)).isoformat())
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


def test_maintenance_form_a2(client, headers, base_refs, make_extinguisher):
    ext = _seed(client, headers, base_refs, make_extinguisher)
    today = date.today()
    resp = client.post("/service-records/", headers=headers, json={
        "fire_extinguisher_id": ext["id"], "service_date": today.isoformat(),
        "tested": True, "recharged": True, "organization": "ООО Пожсервис",
        "test_result": "Выдержал", "agent_brand": "CO2", "post_recharge_result": "Исправен",
        "responsible": "Инженер, Петров П. П."})
    assert resp.status_code == 201, resp.text

    data = client.get("/reports/print/maintenance", headers=headers).json()
    mine = [r for r in data["rows"] if r["extinguisher"].startswith(ext["inventory_number"])]
    assert any("проверка" in r["work"] and "давление 1.5 МПа" in r["test_result"] for r in mine)
    full = next(r for r in mine if "ООО Пожсервис" in r["work"])
    assert full["recharge_date"] == today.isoformat()
    assert full["agent_brand"] == "CO2"
    assert full["next_recharge_date"]  # ОУ: через 5 лет
    assert full["next_test_date"]

    resp = client.get("/reports/maintenance.xlsx", headers=headers)
    assert resp.status_code == 200
    ws = load_workbook(BytesIO(resp.content)).active
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    # Графы формы А.2 ГОСТ Р 59641-2021
    for title in ("Номер и марка огнетушителя", "Результаты осмотра и испытания на прочность",
                  "Срок следующего планового испытания", "Дата проведения перезарядки огнетушителя",
                  "Марка (концентрация) заряженного ОТВ", "Результат осмотра после перезарядки",
                  "Дата следующей плановой перезарядки",
                  "Должность, фамилия, инициалы и подпись ответственного лица"):
        assert title in texts, title


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
                             "Перезарядка", "Испытания", "Срок службы"]


def test_report_export_logged(client, headers):
    client.get("/reports/fleet.xlsx", headers=headers)
    items = client.get("/audit/", headers=headers, params={"action": "export", "entity_type": "report"}).json()
    assert items["total"] >= 1


def test_viewer_can_download_reports(client, make_user):
    _, vh = make_user("viewer")
    assert client.get("/reports/journal.xlsx", headers=vh).status_code == 200
    assert client.get("/reports/print/journal", headers=vh).status_code == 200


def test_cards_form_a1(client, headers, base_refs, make_extinguisher):
    ext = _seed(client, headers, base_refs, make_extinguisher)
    data = client.get("/reports/print/cards", headers=headers,
                      params={"extinguisher_id": ext["id"]}).json()
    assert len(data["cards"]) == 1
    card = data["cards"][0]
    assert card["serial_number"] == "ЗН-777"
    assert card["manufacturer"] == "Завод"
    assert card["next_recharge_date"]

    resp = client.get("/reports/cards.xlsx", headers=headers, params={"extinguisher_id": ext["id"]})
    assert resp.status_code == 200
    ws = load_workbook(BytesIO(resp.content)).active
    texts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    for label in ("1. Номер, присвоенный огнетушителю", "2. Дата размещения огнетушителя на объекте защиты",
                  "6. Заводской номер", "8. Дата очередной перезарядки огнетушителя",
                  "9. Срок службы огнетушителя", "10. Ответственное лицо и его подпись"):
        assert label in texts, label
    assert "ЗН-777" in texts


def test_all_cards_skip_decommissioned(client, headers, make_extinguisher):
    from conftest import status_id
    ext = make_extinguisher(status_id=status_id(client, headers, "Списан"))
    cards = client.get("/reports/print/cards", headers=headers).json()["cards"]
    assert ext["inventory_number"] not in [c["number"] for c in cards]
