from datetime import datetime, timezone
from uuid import UUID

from domain.foundation import ResourceScope


class FakeFoundationRepository:
    def __init__(self, users=(), memberships=(), farms=(), accesses=(), resources=()):
        self.users = {item.subject: item for item in users}
        self.memberships = {(item.user_id, item.organization_public_id): item for item in memberships}
        self.farms = {item.public_id: item for item in farms}
        self.accesses = {(item.membership_id, item.farm_id): item for item in accesses}
        self.resources = {(item.resource_type, item.resource_public_id): item for item in resources}
        self.audited = []

    def find_user_by_subject(self, subject):
        return self.users.get(subject)

    def find_membership(self, user_id, organization_public_id):
        return self.memberships.get((user_id, organization_public_id))

    def find_farm(self, farm_public_id):
        return self.farms.get(farm_public_id)

    def find_farm_access(self, membership_id, farm_id):
        return self.accesses.get((membership_id, farm_id))

    def find_resource_scope(self, resource_type, resource_public_id):
        return self.resources.get((resource_type, resource_public_id))

    def audit_farm_read(self, context, farm):
        self.audited.append((context, farm))


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def synthetic_scope(resource_type, resource_id, farm, organization):
    return ResourceScope(
        resource_type, UUID(resource_id), organization.id, organization.public_id,
        farm.id, farm.public_id,
    )
