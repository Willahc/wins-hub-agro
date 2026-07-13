from pydantic import BaseModel


class OperationalFarmResponse(BaseModel):
    public_id: str
    organization_public_id: str
    name: str
    status: str
    request_id: str
