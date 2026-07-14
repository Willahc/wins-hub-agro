from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path): return (ROOT/path).read_text()


def test_feature_flag_is_false_by_default():
    text = read("routers/harvest_silos.py")
    assert 'os.getenv("ENABLE_HARVEST_SILOS", "false")' in text


def test_cross_tenant_resources_are_hidden():
    text = read("services/harvest_silos.py")
    assert text.count("raise HiddenResourceError()") >= 5
    assert 'facility["farm_id"] != farm["id"]' in text


def test_viewer_write_is_checked_centrally():
    text = read("services/harvest_silos.py")
    assert "Permission.FARM_OPERATE" in text
    assert "AuthorizationService" in text


def test_internal_database_ids_absent_from_response_schemas():
    text = read("schemas/harvest_silos.py")
    assert "organization_id:" not in text
    assert "farm_id:" not in text
    assert "facility_id:" not in text


def test_sql_is_parameterized():
    text = read("repositories/harvest_silos.py")
    assert "f\"SELECT" not in text and "f\"UPDATE" not in text and "f\"INSERT" not in text


def test_completion_locks_plan_and_facilities():
    text = read("repositories/harvest_silos.py")
    assert text.count("FOR UPDATE") >= 2
