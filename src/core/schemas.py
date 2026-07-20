from typing import Optional, Any
from pydantic import BaseModel, EmailStr, ConfigDict

class VehicleBase(BaseModel):
    unit_number: str
    status: str


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = None
    role: Optional[str] = "Driver"
    carrier_id: int = 1

class VehicleCreate(VehicleBase):
    pass

class UserCreate(UserBase):
    password: str

class VehicleOut(VehicleBase):
    id: int
    carrier_id: Any  # Using Any to allow flexibility for now, will replace with specific type if needed
    model_config = ConfigDict(from_attributes=True)


class UserOut(UserBase):
    id: int
    role: str
    carrier_id: int

    is_active: bool

    model_config = ConfigDict(from_attributes=True)

# Load schemas
from typing import Optional

class LoadBase(BaseModel):
    load_number: str
    load_weight: int
    commodity: str
    pickup_ref: str
    delivery_ref: str
    dispatcher_notes: Optional[str] = None
    status: str
    carrier_id: int

class LoadCreate(LoadBase):
    pass

class LoadOut(LoadBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
