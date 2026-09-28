"""
Pydantic models and schemas for request validation and response formatting.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time

# --- Authentication & User Models ---
class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: str
    is_active: bool

class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    email: Optional[str] = None
    role: str = Field(..., pattern="^(Administrator|Storekeeper|Viewer)$")

# --- Chemical & Location Models ---
class ChemicalResponse(BaseModel):
    id: int
    name: str
    code: str
    default_unit: str
    storage_location_id: Optional[int]
    storage_location_name: Optional[str] = None
    requires_daily_physical_check: bool
    min_stock_level: float
    description: Optional[str]
    total_stock: float = 0.0

class StorageLocationResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str]

# --- Batch Models ---
class BatchResponse(BaseModel):
    id: int
    chemical_id: int
    chemical_name: str
    chemical_code: str
    batch_number: str
    manufacturing_date: Optional[str]
    expiry_date: str
    date_received: str
    supplier_id: Optional[int]
    supplier_name: Optional[str]
    storage_location_id: int
    storage_location_name: str
    received_quantity: float
    current_quantity: float
    unit: str
    status: str
    remarks: Optional[str]

class CreateBatchRequest(BaseModel):
    chemical_id: int
    batch_number: str
    manufacturing_date: Optional[date] = None
    expiry_date: date
    date_received: date
    supplier_id: Optional[int] = None
    storage_location_id: int
    received_quantity: float = Field(..., gt=0)
    unit: str = "kg"
    remarks: Optional[str] = None

# --- Ammonia Barrel Models ---
class BarrelResponse(BaseModel):
    id: int
    barrel_id: str
    batch_id: int
    batch_number: str
    chemical_id: int
    chemical_name: str
    original_quantity: float
    current_quantity: float
    supplier_id: Optional[int]
    supplier_name: Optional[str]
    received_date: str
    expiry_date: str
    storage_location_id: int
    storage_location_name: str
    status: str

class BarrelHistoryResponse(BaseModel):
    id: int
    barrel_id: str
    batch_number: str
    action_date: str
    action_time: str
    original_quantity: float
    used_or_transferred_quantity: float
    remaining_quantity: float
    usage_purpose: str
    supplier_customer_name: Optional[str]
    destination: Optional[str]
    reference_number: Optional[str]
    remarks: Optional[str]
    operator_name: str

class BarrelUsageRequest(BaseModel):
    barrel_id: str
    quantity_used: float = Field(..., gt=0)
    usage_purpose: str = Field(..., pattern="^(10% Ammonia Preparation|25% Ammonia Usage|Transfer to Ready-to-Use 25% Ammonia Store|Latex Supplier / Customer Supply|Other)$")
    supplier_customer_name: Optional[str] = None
    destination: Optional[str] = None
    reference_number: Optional[str] = None
    remarks: Optional[str] = None
    date: Optional[date] = None
    time: Optional[time] = None

# --- Receiving (GRN) Models ---
class ReceivingRequest(BaseModel):
    chemical_id: int
    batch_number: str
    manufacturing_date: Optional[date] = None
    expiry_date: date
    supplier_id: int
    storage_location_id: int
    quantity: float = Field(..., gt=0)
    unit: str = "kg"
    grn_number: str
    invoice_number: Optional[str] = None
    received_date: date
    remarks: Optional[str] = None

# --- Usage Models ---
class UsageRequest(BaseModel):
    date: date
    time: Optional[time] = None
    chemical_id: int
    batch_id: int
    storage_location_id: int
    quantity_used: float = Field(..., gt=0)
    unit: str = "kg"
    purpose: str
    supplier_customer_name: Optional[str] = None
    reference_number: str
    remarks: Optional[str] = None

# --- Transfer Models ---
class TransferRequest(BaseModel):
    date: date
    time: Optional[time] = None
    chemical_id: int
    batch_id: int
    barrel_id: Optional[str] = None
    from_location_id: int
    to_location_id: int
    quantity: float = Field(..., gt=0)
    unit: str = "kg"
    purpose: str
    reference_number: str
    remarks: Optional[str] = None

# --- 10% Ammonia Preparation Request ---
class DilutionRequest(BaseModel):
    source_barrel_id: str
    production_date: date
    expiry_date: date
    reference_number: str
    remarks: Optional[str] = None

# --- Daily Physical Stock Verification Models ---
class DailyStockItem(BaseModel):
    storage_location_id: int
    chemical_id: int
    physical_quantity: float = Field(..., ge=0)
    remarks: Optional[str] = None

class DailyStockSubmitRequest(BaseModel):
    date: date
    time: Optional[time] = None
    entries: List[DailyStockItem]
    operator_name: Optional[str] = None

# --- Controlled Stock Adjustment Models ---
class StockAdjustmentRequest(BaseModel):
    chemical_id: int
    batch_id: int
    storage_location_id: int
    new_quantity: float = Field(..., ge=0)
    reason: str
    reference_number: Optional[str] = None

# --- System Settings Models ---
class UpdateSettingRequest(BaseModel):
    key: str
    value: str
