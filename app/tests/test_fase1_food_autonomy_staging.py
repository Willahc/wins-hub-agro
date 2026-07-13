"""Testes de integração do módulo de Autonomia Alimentar no staging."""
import unittest
import os


STAGING_URL = os.getenv("STAGING_URL", "http://127.0.0.1:18080")


@unittest.skipUnless(
    os.getenv("STAGING_TEST", "").lower() in {"1", "true", "yes"},
    "Staging tests disabled (set STAGING_TEST=1 to enable)"
)
class TestFoodAutonomyStaging(unittest.TestCase):
    def _client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_healthz(self):
        r = self._client().get("/healthz")
        self.assertEqual(r.status_code, 200)

    def test_food_autonomy_page_requires_auth(self):
        r = self._client().get("/autonomia-alimentar")
        self.assertIn(r.status_code, [302, 401])

    def test_simulate_requires_auth(self):
        r = self._client().post(
            "/api/v2/farms/00000000-0000-0000-0000-000000000001/food-autonomy/simulate",
            json={"herd": [], "reference_date": "2026-07-01"},
        )
        self.assertIn(r.status_code, [401, 403])

    def test_scenarios_list_requires_auth(self):
        r = self._client().get(
            "/api/v2/farms/00000000-0000-0000-0000-000000000001/food-autonomy/scenarios",
        )
        self.assertIn(r.status_code, [401, 403])


@unittest.skipUnless(
    os.getenv("STAGING_TEST", "").lower() in {"1", "true", "yes"},
    "Staging tests disabled"
)
class TestFoodAutonomyStagingWithAuth(unittest.TestCase):
    def setUp(self):
        self.client = self._client()
        self.token = self._login()

    def _client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def _login(self):
        r = self.client.post("/api/login", data={
            "email": os.getenv("TEST_USER_EMAIL", "mari@wins"),
            "password": os.getenv("TEST_USER_PASSWORD", "test"),
        })
        if r.status_code == 200:
            return r.cookies.get("access_token")
        return None

    @unittest.skipIf(not os.getenv("TEST_USER_EMAIL"), "No test credentials")
    def test_simulate_adequate(self):
        if not self.token:
            self.skipTest("Login failed")
        r = self.client.post(
            "/api/v2/farms/00000000-0000-0000-0000-000000000001/food-autonomy/simulate",
            json={
                "name": "Teste Adequado",
                "reference_date": "2026-07-01",
                "target_days": 30,
                "herd": [{"category": "lactating_cows", "head_count": 20,
                           "average_weight_kg": "450", "intake_pct_body_weight": "2.5"}],
                "feeds": [{"feed_type": "silage", "name": "Silo",
                           "quantity_natural_kg": "100000", "dry_matter_pct": "35",
                           "utilization_pct": "100"}],
            },
            cookies={"access_token": self.token},
        )
        if r.status_code == 200:
            d = r.json()
            self.assertIn(d["status"], ["adequate", "warning", "critical"])

    @unittest.skipIf(not os.getenv("TEST_USER_EMAIL"), "No test credentials")
    def test_decimal_precision_in_response(self):
        if not self.token:
            self.skipTest("Login failed")
        r = self.client.post(
            "/api/v2/farms/00000000-0000-0000-0000-000000000001/food-autonomy/simulate",
            json={
                "reference_date": "2026-07-01",
                "target_days": 90,
                "herd": [{"category": "lactating_cows", "head_count": 20,
                           "average_weight_kg": "450", "intake_pct_body_weight": "2.5"}],
                "feeds": [{"feed_type": "silage", "name": "S",
                           "quantity_natural_kg": "10000", "dry_matter_pct": "35",
                           "utilization_pct": "90"}],
            },
            cookies={"access_token": self.token},
        )
        if r.status_code == 200:
            d = r.json()
            self.assertIn(".", d["daily_demand_dm_kg"])
            self.assertNotIn("e", d["daily_demand_dm_kg"])


if __name__ == "__main__":
    unittest.main()
