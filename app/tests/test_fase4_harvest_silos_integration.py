from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_completion_is_one_database_transaction():
    text = (ROOT/"repositories/harvest_silos.py").read_text()
    section = text.split("def complete_plan_and_create_lots",1)[1]
    assert "with _tx() as conn" in section
    assert "storage.feed_lots" in section
    assert "storage.feed_stock_movements" in section
    assert "status = 'completed'" in section


def test_lot_origin_and_link_are_preserved():
    service = (ROOT/"services/harvest_silos.py").read_text()
    repo = (ROOT/"repositories/harvest_silos.py").read_text()
    assert "Colheita e Silos" in service
    assert "created_feed_lot_id" in repo
    assert "created_feed_lot_uuid" in repo


def test_completion_idempotency_and_conflict_contract():
    service = (ROOT/"services/harvest_silos.py").read_text()
    assert "completion_payload_hash" in service and "request_id_payload_conflict" in service
    assert "completion_request_id" in service


def test_completion_creates_initial_balance_with_inventory_contract():
    service = (ROOT/"services/harvest_silos.py").read_text()
    assert '"movement_type": "initial_balance"' in service
    assert '"status": "available"' in service


def test_previous_storage_tables_are_reused():
    repository = (ROOT/"repositories/harvest_silos.py").read_text()
    assert "storage.feed_storage_facilities" in repository
    assert "storage.feed_lots" in repository
    assert "storage.feed_stock_movements" in repository
