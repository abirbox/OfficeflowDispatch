"""Dispatch module models — all Pydantic schemas for the Dispatch System."""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# ---------- Client ----------
class ClientBase(BaseModel):
    code: Optional[str] = None
    name: str
    logo_path: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    website: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None

class ClientCreate(ClientBase): pass
class ClientUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    logo_path: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    website: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

# ---------- Vendor ----------
class VendorBase(BaseModel):
    code: Optional[str] = None
    name: str
    logo_path: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    website: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    status: str = "active"
    notes: Optional[str] = None

class VendorCreate(VendorBase): pass
class VendorUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    logo_path: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    website: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

# ---------- Security Officer ----------
OFFICER_STATUSES = ["active", "inactive", "suspended", "terminated", "on_leave"]

class OfficerBase(BaseModel):
    officer_code: Optional[str] = None
    profile_image: Optional[str] = None
    name: str
    contact_number: Optional[str] = None
    alternate_contact_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    vendor_id: Optional[str] = None
    status: str = "active"
    joining_date: Optional[str] = None
    notes: Optional[str] = None

class OfficerCreate(OfficerBase): pass
class OfficerUpdate(BaseModel):
    officer_code: Optional[str] = None
    profile_image: Optional[str] = None
    name: Optional[str] = None
    contact_number: Optional[str] = None
    alternate_contact_number: Optional[str] = None
    address: Optional[str] = None
    email: Optional[EmailStr] = None
    vendor_id: Optional[str] = None
    status: Optional[str] = None
    joining_date: Optional[str] = None
    notes: Optional[str] = None

# ---------- Post Site ----------
class PostSiteBase(BaseModel):
    post_pin: str
    name: str
    client_id: str
    vendor_id: str
    address: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    required_officers: int = 1
    status: str = "active"
    notes: Optional[str] = None

class PostSiteCreate(PostSiteBase): pass
class PostSiteUpdate(BaseModel):
    post_pin: Optional[str] = None
    name: Optional[str] = None
    client_id: Optional[str] = None
    vendor_id: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    contact_person: Optional[str] = None
    contact_number: Optional[str] = None
    required_officers: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None

# ---------- Dispatch Schedule ----------
SHIFT_TYPES = ["Morning", "Afternoon", "Evening", "Night"]
SHIFT_STATUSES = ["Not Started", "Check-in", "Checkout", "Late Clock In",
                  "Early Clock Out", "Late Clock Out", "Absent", "Completed", "Cancelled"]
CONFIRMATION_STATUSES = ["Not Confirmed", "Pending", "Confirmed", "Declined", "No Response"]
CONFIRMATION_METHODS = ["Call", "Text", "Call + Text"]

class ScheduleCreate(BaseModel):
    date: str  # YYYY-MM-DD
    shift_type: str
    start_time: str  # HH:MM 24h
    end_time: str
    client_id: str
    vendor_id: str
    post_site_id: str
    officer_id: str
    duty_rate: Optional[float] = None
    billing_rate: Optional[float] = None
    work_order_number: Optional[str] = None
    remarks: Optional[str] = None

class ScheduleUpdate(BaseModel):
    date: Optional[str] = None
    shift_type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    client_id: Optional[str] = None
    vendor_id: Optional[str] = None
    post_site_id: Optional[str] = None
    officer_id: Optional[str] = None
    duty_rate: Optional[float] = None
    billing_rate: Optional[float] = None
    work_order_number: Optional[str] = None
    remarks: Optional[str] = None
    shift_status: Optional[str] = None
    actual_check_in: Optional[str] = None
    actual_check_out: Optional[str] = None

class ConfirmationUpdate(BaseModel):
    confirmation_status: str
    confirmation_method: Optional[str] = None
    remarks: Optional[str] = None
