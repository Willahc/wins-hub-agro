import sys
import unittest
from pathlib import Path
from uuid import UUID
from dataclasses import replace

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from core.authorization import ForbiddenError, HiddenResourceError, UnauthenticatedError
from core.permissions import Role
from domain.foundation import RecordStatus, UserRecord, MembershipRecord
from services.farms_v2 import FarmsV2Service


def uid(number):
    return UUID(int=number)


class FakeFarmsV2Repository:
    def __init__(self):
        self.memberships = []
        self.farms = []
        self.orgs = {}
        self.audited = []

    def find_active_memberships(self, user_id: int):
        return [
            m for m in self.memberships
            if m["user_id"] == user_id and m["status"] == "active"
        ]

    def get_organization_name(self, org_id: int):
        return self.orgs.get(org_id, "Unknown Org")

    def list_farms(self, organization_id, membership_id, is_org_wide, limit, offset, status_filter):
        result = []
        for farm in self.farms:
            if farm["organization_id"] != organization_id:
                continue
            if status_filter and farm["status"] != status_filter:
                continue

            access_level = "manage"
            if not is_org_wide:
                matching_access = [
                    acc for acc in farm.get("access_list", [])
                    if acc["farm_id"] == farm["id"] and acc["membership_id"] == membership_id
                ]
                if not matching_access:
                    continue
                access_level = matching_access[0]["access_level"]

            farm_copy = farm.copy()
            farm_copy["access_level"] = access_level
            result.append(farm_copy)
        return result[offset : offset + limit]

    def audit_farms_listed(self, context, returned_count, limit, offset):
        self.audited.append((context, returned_count, limit, offset))


class FakeAuthRepository:
    def __init__(self):
        self.users = {}
        self.memberships = {}

    def find_user_by_subject(self, subject):
        return self.users.get(subject)

    def find_membership(self, user_id, organization_public_id):
        return self.memberships.get((user_id, organization_public_id))


class FarmsV2UnitTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeFarmsV2Repository()
        self.auth_repo = FakeAuthRepository()
        self.service = FarmsV2Service(self.repo, self.auth_repo)

        # Configura dados sintéticos
        self.user = UserRecord(1, uid(1), "usr_owner_alfa", RecordStatus.ACTIVE)
        self.auth_repo.users["usr_owner_alfa"] = self.user

        # Membership Alfa
        self.membership_alfa = MembershipRecord(10, uid(10), 100, uid(100), 1, Role.OWNER, RecordStatus.ACTIVE)
        self.auth_repo.memberships[(1, uid(100))] = self.membership_alfa
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

        # Fazendas
        self.farm_1 = {
            "id": 1001,
            "public_id": uid(1001),
            "organization_id": 100,
            "name": "Fazenda Sintética Norte",
            "state": "SP",
            "municipality_code": "3550308",
            "area_ha": "150.50",
            "status": "active",
            "access_level": "manage",
        }
        self.repo.farms.append(self.farm_1)

    def test_authenticated_user_required(self):
        with self.assertRaises(UnauthenticatedError):
            self.service.list_authorized_farms(
                subject=None,
                organization_uuid=None,
                request_id="req-123"
            )

    def test_inactive_user_rejected(self):
        inactive_user = UserRecord(1, uid(1), "usr_owner_alfa", RecordStatus.INACTIVE)
        self.auth_repo.users["usr_owner_alfa"] = inactive_user
        with self.assertRaises(UnauthenticatedError):
            self.service.list_authorized_farms(
                subject="usr_owner_alfa",
                organization_uuid=None,
                request_id="req-123"
            )

    def test_single_active_membership_resolves_automatically(self):
        res = self.service.list_authorized_farms(
            subject="usr_owner_alfa",
            organization_uuid=None,
            request_id="req-123"
        )
        self.assertEqual(res["organization"]["name"], "Organização Sintética Alfa")
        self.assertEqual(res["organization"]["id"], uid(100))
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["name"], "Fazenda Sintética Norte")

    def test_multiple_memberships_require_context(self):
        # Adiciona segunda membership ativada
        self.repo.memberships.append({
            "id": 11,
            "public_id": uid(11),
            "organization_id": 200,
            "organization_public_id": uid(200),
            "organization_name": "Organização Sintética Beta",
            "user_id": 1,
            "role": Role.TECHNICIAN,
            "status": "active",
        })
        with self.assertRaises(ForbiddenError) as caught:
            self.service.list_authorized_farms(
                subject="usr_owner_alfa",
                organization_uuid=None,
                request_id="req-123"
            )
        self.assertEqual(caught.exception.code, "organization_context_required")

    def test_revoked_membership_raises_forbidden(self):
        revoked_membership = MembershipRecord(10, uid(10), 100, uid(100), 1, Role.OWNER, RecordStatus.REVOKED)
        self.auth_repo.memberships[(1, uid(100))] = revoked_membership
        with self.assertRaises(ForbiddenError) as caught:
            self.service.list_authorized_farms(
                subject="usr_owner_alfa",
                organization_uuid=uid(100),
                request_id="req-123"
            )
        self.assertEqual(caught.exception.code, "membership_revoked")

    def test_cross_tenant_access_hidden(self):
        # Usuário não possui membership na org 200
        with self.assertRaises(HiddenResourceError):
            self.service.list_authorized_farms(
                subject="usr_owner_alfa",
                organization_uuid=uid(200),
                request_id="req-123"
            )

    def test_audit_logs_successfully_recorded(self):
        self.service.list_authorized_farms(
            subject="usr_owner_alfa",
            organization_uuid=None,
            request_id="req-123"
        )
        self.assertEqual(len(self.repo.audited), 1)
        context, returned_count, limit, offset = self.repo.audited[0]
        self.assertEqual(returned_count, 1)
        self.assertEqual(context.role, Role.OWNER)

    def test_technician_sees_only_assigned_farms(self):
        # Altera papel para technician
        self.repo.memberships[0]["role"] = Role.TECHNICIAN
        self.auth_repo.memberships[(1, uid(100))] = replace(self.membership_alfa, role=Role.TECHNICIAN)

        # Sem farm access
        res = self.service.list_authorized_farms(
            subject="usr_owner_alfa",
            organization_uuid=None,
            request_id="req-123"
        )
        self.assertEqual(len(res["items"]), 0)

        # Adiciona farm access
        self.farm_1["access_list"] = [{
            "farm_id": 1001,
            "membership_id": 10,
            "access_level": "operate",
        }]
        res = self.service.list_authorized_farms(
            subject="usr_owner_alfa",
            organization_uuid=None,
            request_id="req-123"
        )
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["access_level"], "operate")


if __name__ == "__main__":
    unittest.main()
