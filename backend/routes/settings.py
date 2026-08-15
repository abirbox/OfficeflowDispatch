from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile
from datetime import datetime, timezone

from models.settings import (
    AppSettings, AppSettingsUpdate, CURRENCY_DIRECTORY, TIMEZONE_DIRECTORY,
)
from utils.auth import get_current_user
from utils.storage import put_object, generate_upload_path

router = APIRouter(prefix="/settings", tags=["App Settings"])

SETTINGS_KEY = "app_settings_singleton"


def get_db(request: Request):
    return request.app.state.db


async def require_admin(request: Request, db):
    user = await get_current_user(request, db)
    if user.get("role") not in ["super_admin", "admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_settings_doc(db) -> dict:
    doc = await db.app_settings.find_one({"key": SETTINGS_KEY}, {"_id": 0})
    if not doc:
        defaults = AppSettings().model_dump()
        doc = {"key": SETTINGS_KEY, **defaults, "created_at": datetime.now(timezone.utc)}
        await db.app_settings.insert_one(doc)
        doc.pop("_id", None)
    return doc


@router.get("/public")
async def get_public_settings(request: Request, db=Depends(get_db)):
    """Login page and other pre-auth screens read this."""
    doc = await get_settings_doc(db)
    return {
        "brand_name": doc.get("brand_name", "OfficeFlow"),
        "brand_logo_url": doc.get("brand_logo_url"),
        "login_hero_title": doc.get("login_hero_title", "OfficeFlow"),
        "login_hero_subtitle": doc.get("login_hero_subtitle", ""),
        "login_welcome_title": doc.get("login_welcome_title", "Welcome Back"),
        "login_welcome_subtitle": doc.get("login_welcome_subtitle", "Sign in to your account"),
        "currency": doc.get("currency", "BDT"),
        "currency_symbol": doc.get("currency_symbol", "৳"),
    }


@router.get("")
async def get_settings(request: Request, db=Depends(get_db)):
    await get_current_user(request, db)
    doc = await get_settings_doc(db)
    return {k: v for k, v in doc.items() if k not in ("_id", "created_at")}


@router.put("")
async def update_settings(payload: AppSettingsUpdate, request: Request, db=Depends(get_db)):
    await require_admin(request, db)
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    # Auto-derive currency symbol when only code is provided
    if update.get("currency") and not update.get("currency_symbol"):
        info = CURRENCY_DIRECTORY.get(update["currency"].upper())
        if info:
            update["currency_symbol"] = info["symbol"]
    # Auto-derive tz offset when only tz code is provided
    if update.get("timezone") and update.get("tz_offset_hours") is None:
        match = next((t for t in TIMEZONE_DIRECTORY if t["code"] == update["timezone"]), None)
        if match:
            update["tz_offset_hours"] = match["offset"]
    update["updated_at"] = datetime.now(timezone.utc)
    await db.app_settings.update_one(
        {"key": SETTINGS_KEY},
        {"$set": update, "$setOnInsert": {"key": SETTINGS_KEY, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    doc = await get_settings_doc(db)
    return {k: v for k, v in doc.items() if k not in ("_id", "created_at")}


@router.post("/logo")
async def upload_logo(file: UploadFile, request: Request, db=Depends(get_db)):
    await require_admin(request, db)
    data = await file.read()
    path = generate_upload_path("branding", file.filename)
    result = put_object(path, data, file.content_type or "image/png")
    await db.app_settings.update_one(
        {"key": SETTINGS_KEY},
        {"$set": {"brand_logo_url": result["path"], "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"brand_logo_url": result["path"]}


@router.get("/currencies")
async def list_currencies():
    return [{"code": k, **v} for k, v in CURRENCY_DIRECTORY.items()]


@router.get("/timezones")
async def list_timezones():
    return TIMEZONE_DIRECTORY
