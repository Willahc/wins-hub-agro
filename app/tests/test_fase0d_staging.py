import sys
import unittest
from pathlib import Path
from uuid import UUID

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

try:
    from fastapi.testclient import TestClient
    from main import app
    from routers.farms_v2 import get_farms_repository, get_auth_repository
    from auth import create_access_token
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from domain.foundation import RecordStatus, UserRecord, MembershipRecord
from core.permissions import Role
from tests.test_fase0d_farms_v2 import FakeFarmsV2Repository, FakeAuthRepository

def uid(number):
    return UUID(int=number)


@unittest.skipIf(not HAS_FASTAPI, "FastAPI ou dependências de autenticação não disponíveis neste ambiente")
class StagingRouterTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeFarmsV2Repository()
        self.auth_repo = FakeAuthRepository()

        # Override dependencies
        app.dependency_overrides[get_farms_repository] = lambda: self.repo
        app.dependency_overrides[get_auth_repository] = lambda: self.auth_repo
        self.client = TestClient(app)

        # Setup synthetic user
        self.user = UserRecord(1, uid(1), "usr_owner_alfa", RecordStatus.ACTIVE)
        self.auth_repo.users["usr_owner_alfa"] = self.user

        # Membership
        self.membership = MembershipRecord(10, uid(10), 100, uid(100), 1, Role.OWNER, RecordStatus.ACTIVE)
        self.auth_repo.memberships[(1, uid(100))] = self.membership
        self.repo.memberships.append({
            "id": 10,
            "public_id": uid(10),
            "organization_id": 100,
            "organization_public_id": uid(100),
            "organization_name": "Organização Sintética Alfa",
            "user_id": 1,
            "role": Role.OWNER,
            "status": "active",
        })
        self.repo.orgs[100] = "Organização Sintética Alfa"

        # Farm
        self.repo.farms.append({
            "id": 1001,
            "public_id": uid(1001),
            "organization_id": 100,
            "name": "Fazenda Sintética Norte",
            "state": "SP",
            "municipality_code": "3550308",
            "area_ha": "150.50",
            "status": "active",
            "access_level": "manage",
        })

        # Generate a valid synthetic token
        self.token = create_access_token({"sub": "usr_owner_alfa"})

    def tearDown(self):
        if HAS_FASTAPI:
            app.dependency_overrides.clear()

    def test_unauthenticated_returns_401(self):
        # Sem cookie de token
        res = self.client.get("/api/v2/farms")
        self.assertEqual(res.status_code, 401)

    def test_authenticated_lists_farms(self):
        self.client.cookies.set("access_token", self.token)
        res = self.client.get("/api/v2/farms")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["Cache-Control"], "no-store, private")
        self.assertEqual(res.headers["Pragma"], "no-cache")

        json_data = res.json()
        self.assertEqual(json_data["organization"]["name"], "Organização Sintética Alfa")
        self.assertEqual(len(json_data["items"]), 1)
        self.assertEqual(json_data["items"][0]["name"], "Fazenda Sintética Norte")
        self.assertNotIn("id", json_data["items"][0])
        self.assertEqual(json_data["items"][0]["id"], str(uid(1001)))

    def test_invalid_pagination_returns_422(self):
        self.client.cookies.set("access_token", self.token)
        res = self.client.get("/api/v2/farms?limit=150")
        self.assertEqual(res.status_code, 422)

    def test_invalid_status_returns_422(self):
        self.client.cookies.set("access_token", self.token)
        res = self.client.get("/api/v2/farms?status=invalid_status_value")
        self.assertEqual(res.status_code, 422)

    def test_cross_tenant_returns_404(self):
        self.client.cookies.set("access_token", self.token)
        res = self.client.get(f"/api/v2/farms?organization_uuid={uid(200)}")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
