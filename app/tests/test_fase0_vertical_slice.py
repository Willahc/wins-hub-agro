import sys
import unittest
from pathlib import Path
from uuid import UUID

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))
from core.permissions import FarmAccessLevel, Role  # noqa: E402
from core.authorization import HiddenResourceError, UnauthenticatedError  # noqa: E402
from domain.foundation import FarmAccessRecord, MembershipRecord, OperationalFarmRecord, UserRecord  # noqa: E402
from tests.fase0_fakes import FakeFoundationRepository  # noqa: E402
from services.foundation import resolve_operational_farm  # noqa: E402


def uid(number):
    return UUID(int=number)


class VerticalSliceTest(unittest.TestCase):
    def setUp(self):
        self.user = UserRecord(1, uid(1), "synthetic-user-a")
        self.membership = MembershipRecord(10, uid(10), 100, uid(100), 1, Role.TECHNICIAN)
        self.farm_a = OperationalFarmRecord(1000, uid(1000), 100, uid(100), "Fazenda Sintética A")
        self.farm_b = OperationalFarmRecord(2000, uid(2000), 200, uid(200), "Fazenda Sintética B")
        self.access = FarmAccessRecord(20, uid(20), 1000, 10, FarmAccessLevel.READ)

    def resolve(self, repo, subject="synthetic-user-a", farm_id=None):
        return resolve_operational_farm(
            repo, subject=subject, organization_public_id=uid(100),
            farm_public_id=farm_id or uid(1000), request_id="req-synthetic-route",
        )

    def test_private_route_authorizes_and_audits(self):
        repo = FakeFoundationRepository(
            [self.user], [self.membership], [self.farm_a], [self.access]
        )
        context, farm = self.resolve(repo)
        self.assertEqual(farm.name, "Fazenda Sintética A")
        self.assertEqual(context.request_id, "req-synthetic-route")
        self.assertEqual(len(repo.audited), 1)

    def test_private_route_returns_401_without_session(self):
        with self.assertRaises(UnauthenticatedError) as caught:
            self.resolve(FakeFoundationRepository(), subject=None)
        self.assertEqual(caught.exception.status_code, 401)

    def test_private_route_hides_cross_organization_farm(self):
        repo = FakeFoundationRepository(
            [self.user], [self.membership], [self.farm_a, self.farm_b], [self.access]
        )
        with self.assertRaises(HiddenResourceError) as caught:
            self.resolve(repo, farm_id=uid(2000))
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(repo.audited, [])


if __name__ == "__main__":
    unittest.main()
