import sys
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from core.authorization import (  # noqa: E402
    AuthorizationService, ForbiddenError, HiddenResourceError, UnauthenticatedError,
)
from core.permissions import FarmAccessLevel, Permission, Role, role_allows  # noqa: E402
from domain.foundation import (  # noqa: E402
    FarmAccessRecord, MembershipRecord, OperationalFarmRecord, OrganizationRecord,
    RecordStatus, UserRecord,
)
from tests.fase0_fakes import FakeFoundationRepository, NOW, synthetic_scope  # noqa: E402


def uid(number):
    return UUID(int=number)


class AuthorizationFoundationTest(unittest.TestCase):
    def setUp(self):
        self.org_a = OrganizationRecord(10, uid(10), "Organização Alfa", "organizacao-alfa")
        self.org_b = OrganizationRecord(20, uid(20), "Organização Beta", "organizacao-beta")
        self.user_a = UserRecord(1, uid(1), "synthetic-user-a")
        self.user_b = UserRecord(2, uid(2), "synthetic-user-b")
        self.membership = MembershipRecord(100, uid(100), 10, uid(10), 1, Role.TECHNICIAN)
        self.farm_a = OperationalFarmRecord(1000, uid(1000), 10, uid(10), "Fazenda Sintética A")
        self.farm_b = OperationalFarmRecord(2000, uid(2000), 20, uid(20), "Fazenda Sintética B")
        self.access = FarmAccessRecord(1, uid(101), 1000, 100, FarmAccessLevel.OPERATE)
        self.repo = FakeFoundationRepository(
            [self.user_a, self.user_b], [self.membership], [self.farm_a, self.farm_b], [self.access]
        )
        self.service = AuthorizationService(self.repo, now=lambda: NOW)

    def context(self):
        return self.service.require_organization_membership("synthetic-user-a", uid(10), "req-synthetic")

    def test_roles_and_owner_only_permission(self):
        self.assertTrue(role_allows(Role.OWNER, Permission.OWNERSHIP_TRANSFER))
        self.assertFalse(role_allows(Role.ADMIN, Permission.OWNERSHIP_TRANSFER))
        self.assertFalse(role_allows(Role.MANAGER, Permission.MEMBERSHIP_MANAGE))
        self.assertFalse(role_allows(Role.VIEWER, Permission.FARM_OPERATE))

    def test_active_membership_builds_server_context(self):
        context = self.context()
        self.assertEqual(context.user_id, 1)
        self.assertEqual(context.organization_id, 10)
        self.assertEqual(context.role, Role.TECHNICIAN)

    def test_unauthenticated_is_401(self):
        with self.assertRaises(UnauthenticatedError) as caught:
            self.service.require_organization_membership(None, uid(10), "request")
        self.assertEqual(caught.exception.status_code, 401)

    def test_membership_missing_is_403(self):
        with self.assertRaises(ForbiddenError) as caught:
            self.service.require_organization_membership("synthetic-user-b", uid(10), "request")
        self.assertEqual((caught.exception.status_code, caught.exception.code), (403, "membership_missing"))

    def test_inactive_and_revoked_memberships_are_denied(self):
        for status, expected in ((RecordStatus.INACTIVE, "membership_inactive"), (RecordStatus.REVOKED, "membership_revoked")):
            repo = FakeFoundationRepository([self.user_a], [replace(self.membership, status=status)])
            with self.subTest(status=status), self.assertRaises(ForbiddenError) as caught:
                AuthorizationService(repo, now=lambda: NOW).require_organization_membership(
                    "synthetic-user-a", uid(10), "request"
                )
            self.assertEqual(caught.exception.code, expected)

    def test_technician_reads_only_assigned_farm(self):
        allowed = self.service.require_farm_access(self.context(), uid(1000))
        self.assertEqual(allowed.farm_id, 1000)
        without_access = AuthorizationService(FakeFoundationRepository(
            [self.user_a], [self.membership], [self.farm_a]
        ), now=lambda: NOW)
        context = without_access.require_organization_membership("synthetic-user-a", uid(10), "request")
        with self.assertRaises(ForbiddenError) as caught:
            without_access.require_farm_access(context, uid(1000))
        self.assertEqual(caught.exception.code, "farm_not_assigned")

    def test_viewer_cannot_write_even_with_farm_assignment(self):
        membership = replace(self.membership, role=Role.VIEWER)
        repo = FakeFoundationRepository([self.user_a], [membership], [self.farm_a], [self.access])
        service = AuthorizationService(repo, now=lambda: NOW)
        context = service.require_organization_membership("synthetic-user-a", uid(10), "request")
        with self.assertRaises(ForbiddenError) as caught:
            service.require_farm_access(context, uid(1000), Permission.FARM_OPERATE)
        self.assertEqual(caught.exception.code, "role_denied")

    def test_changed_farm_url_cannot_cross_organization(self):
        with self.assertRaises(HiddenResourceError) as caught:
            self.service.require_farm_access(self.context(), uid(2000))
        self.assertEqual(caught.exception.status_code, 404)

    def test_nonexistent_and_cross_org_are_both_hidden(self):
        for farm_id in (uid(2000), uid(9999)):
            with self.subTest(farm_id=farm_id), self.assertRaises(HiddenResourceError) as caught:
                self.service.require_farm_access(self.context(), farm_id)
            self.assertEqual(caught.exception.code, "resource_not_found")

    def test_client_claim_does_not_change_server_ownership(self):
        browser_json = {"cliente_id": 20, "farm_id": str(uid(2000))}
        context = self.context()
        self.assertEqual(context.organization_id, 10)
        with self.assertRaises(HiddenResourceError):
            self.service.require_farm_access(context, UUID(browser_json["farm_id"]))

    def test_private_animal_and_export_follow_farm_scope(self):
        animal_a = uid(3000)
        animal_b = uid(4000)
        scopes = [
            synthetic_scope("animal", str(animal_a), self.farm_a, self.org_a),
            synthetic_scope("animal", str(animal_b), self.farm_b, self.org_b),
        ]
        manager = replace(self.membership, role=Role.MANAGER)
        access = replace(self.access, access_level=FarmAccessLevel.MANAGE)
        repo = FakeFoundationRepository([self.user_a], [manager], [self.farm_a, self.farm_b], [access], scopes)
        service = AuthorizationService(repo, now=lambda: NOW)
        context = service.require_organization_membership("synthetic-user-a", uid(10), "request")
        self.assertEqual(service.require_resource_access(context, "animal", animal_a, Permission.EXPORT).farm_id, 1000)
        with self.assertRaises(HiddenResourceError):
            service.require_resource_access(context, "animal", animal_b)

    def test_owner_and_admin_have_org_wide_farm_access(self):
        for role in (Role.OWNER, Role.ADMIN):
            membership = replace(self.membership, role=role)
            repo = FakeFoundationRepository([self.user_a], [membership], [self.farm_a])
            service = AuthorizationService(repo, now=lambda: NOW)
            context = service.require_organization_membership("synthetic-user-a", uid(10), "request")
            self.assertEqual(service.require_farm_access(context, uid(1000)).farm_id, 1000)


if __name__ == "__main__":
    unittest.main()
