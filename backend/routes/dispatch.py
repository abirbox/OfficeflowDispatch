"""Dispatch module routes — Clients, Vendors, Officers, Post Sites, Schedule + Confirmation."""
from fastapi import APIRouter, HTTPException, Request, Depends, Query
from datetime import datetime, timezone, date, timedelta
from bson import ObjectId
import uuid

from models.dispatch import (
    ClientCreate, ClientUpdate,
    VendorCreate, VendorUpdate,
    OfficerCreate, OfficerUpdate, OFFICER_STATUSES,
    PostSiteCreate, PostSiteUpdate,
    ScheduleCreate, ScheduleUpdate, ConfirmationUpdate,
    SHIFT_TYPES, SHIFT_STATUSES, CONFIRMATION_STATUSES, CONFIRMATION_METHODS,
)
from utils.auth import get_current_user
from utils.permissions import (
    has_permission, require_permission, strip_financial,
    ALL_PERMISSIONS, FINANCIAL_FIELDS,
)

router = APIRouter(prefix="/dispatch", tags=["Dispatch"])

def get_db(request: Request):
    return request.app.state.db


def _now():
    return datetime.now(timezone.utc)


def _oid(x: str):
    try:
        return ObjectId(x)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def _doc_out(doc: dict) -> dict:
    if not doc:
        return doc
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, ObjectId):
            d[k] = str(v)
    return d


def _parse_hhmm(s: str) -> int:
    """Return minutes since midnight, or raise."""
    try:
        h, m = s.split(":")
        h, m = int(h), int(m)
        if not (0 <= h < 24 and 0 <= m < 60):
            raise ValueError()
        return h * 60 + m
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid time '{s}', expected HH:MM")


def _duty_hours(start: str, end: str) -> float:
    """Compute duty hours, handling overnight."""
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if e <= s:  # overnight (e.g. 22:00 → 06:00)
        e += 24 * 60
    return round((e - s) / 60.0, 2)


# ---------- Permissions meta endpoint (used by frontend) ----------
@router.get("/permissions/registry")
async def get_permissions_registry(request: Request, db=Depends(get_db)):
    await get_current_user(request, db)
    return {"permissions": ALL_PERMISSIONS}


# =====================================================================
#  CLIENTS
# =====================================================================
@router.post("/clients")
async def create_client(payload: ClientCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.create")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_clients.insert_one(doc)
    return _doc_out(await db.dispatch_clients.find_one({"_id": res.inserted_id}))


@router.get("/clients")
async def list_clients(request: Request, db=Depends(get_db), search: str = "",
                       status: str = None, skip: int = 0, limit: int = 100):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.view")
    q = {}
    if status: q["status"] = status
    if search: q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                            {"code": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_clients.find(q).skip(skip).limit(limit).to_list(limit)
    return [_doc_out(d) for d in docs]


@router.get("/clients/{cid}")
async def get_client(cid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.view")
    doc = await db.dispatch_clients.find_one({"_id": _oid(cid)})
    if not doc: raise HTTPException(404, "Client not found")
    return _doc_out(doc)


@router.put("/clients/{cid}")
async def update_client(cid: str, payload: ClientUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.edit")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_clients.update_one({"_id": _oid(cid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Client not found")
    return _doc_out(await db.dispatch_clients.find_one({"_id": _oid(cid)}))


@router.delete("/clients/{cid}")
async def delete_client(cid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.clients.delete")
    # Soft delete → set inactive to preserve historical Dispatch records
    r = await db.dispatch_clients.update_one({"_id": _oid(cid)},
                                             {"$set": {"status": "inactive", "updated_at": _now()}})
    if r.matched_count == 0: raise HTTPException(404, "Client not found")
    return {"message": "Client deactivated"}


# =====================================================================
#  VENDORS
# =====================================================================
@router.post("/vendors")
async def create_vendor(payload: VendorCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.create")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_vendors.insert_one(doc)
    return _doc_out(await db.dispatch_vendors.find_one({"_id": res.inserted_id}))


@router.get("/vendors")
async def list_vendors(request: Request, db=Depends(get_db), search: str = "",
                       status: str = None, skip: int = 0, limit: int = 100):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.view")
    q = {}
    if status: q["status"] = status
    if search: q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                            {"code": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_vendors.find(q).skip(skip).limit(limit).to_list(limit)
    return [_doc_out(d) for d in docs]


@router.get("/vendors/{vid}")
async def get_vendor(vid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.view")
    doc = await db.dispatch_vendors.find_one({"_id": _oid(vid)})
    if not doc: raise HTTPException(404, "Vendor not found")
    return _doc_out(doc)


@router.put("/vendors/{vid}")
async def update_vendor(vid: str, payload: VendorUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.edit")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_vendors.update_one({"_id": _oid(vid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Vendor not found")
    return _doc_out(await db.dispatch_vendors.find_one({"_id": _oid(vid)}))


@router.delete("/vendors/{vid}")
async def delete_vendor(vid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.vendors.delete")
    r = await db.dispatch_vendors.update_one({"_id": _oid(vid)},
                                             {"$set": {"status": "inactive", "updated_at": _now()}})
    if r.matched_count == 0: raise HTTPException(404, "Vendor not found")
    return {"message": "Vendor deactivated"}


# =====================================================================
#  SECURITY OFFICERS  (NO GPS — external persons)
# =====================================================================
@router.post("/officers")
async def create_officer(payload: OfficerCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.create")
    if payload.status not in OFFICER_STATUSES:
        raise HTTPException(400, "Invalid officer status")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_officers.insert_one(doc)
    return _doc_out(await db.dispatch_officers.find_one({"_id": res.inserted_id}))


@router.get("/officers")
async def list_officers(request: Request, db=Depends(get_db), search: str = "",
                        vendor_id: str = None, status: str = None,
                        skip: int = 0, limit: int = 200):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.view")
    q = {}
    if status: q["status"] = status
    if vendor_id: q["vendor_id"] = vendor_id
    if search:
        q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                    {"contact_number": {"$regex": search, "$options": "i"}},
                    {"officer_code": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_officers.find(q).skip(skip).limit(limit).to_list(limit)
    return [_doc_out(d) for d in docs]


@router.get("/officers/{oid}")
async def get_officer(oid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.view")
    doc = await db.dispatch_officers.find_one({"_id": _oid(oid)})
    if not doc: raise HTTPException(404, "Officer not found")
    return _doc_out(doc)


@router.put("/officers/{oid}")
async def update_officer(oid: str, payload: OfficerUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.edit")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "status" in upd and upd["status"] not in OFFICER_STATUSES:
        raise HTTPException(400, "Invalid officer status")
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_officers.update_one({"_id": _oid(oid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Officer not found")
    return _doc_out(await db.dispatch_officers.find_one({"_id": _oid(oid)}))


@router.delete("/officers/{oid}")
async def delete_officer(oid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.officers.delete")
    r = await db.dispatch_officers.update_one({"_id": _oid(oid)},
                                              {"$set": {"status": "inactive", "updated_at": _now()}})
    if r.matched_count == 0: raise HTTPException(404, "Officer not found")
    return {"message": "Officer deactivated"}


# =====================================================================
#  POST SITES  (NO GPS)
# =====================================================================
@router.post("/post-sites")
async def create_post_site(payload: PostSiteCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.create")
    # ensure post_pin unique
    if await db.dispatch_post_sites.find_one({"post_pin": payload.post_pin}):
        raise HTTPException(400, "Post Pin already exists")
    doc = payload.model_dump()
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_post_sites.insert_one(doc)
    return _doc_out(await db.dispatch_post_sites.find_one({"_id": res.inserted_id}))


@router.get("/post-sites")
async def list_post_sites(request: Request, db=Depends(get_db), search: str = "",
                          client_id: str = None, vendor_id: str = None, status: str = None,
                          skip: int = 0, limit: int = 200):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.view")
    q = {}
    if status: q["status"] = status
    if client_id: q["client_id"] = client_id
    if vendor_id: q["vendor_id"] = vendor_id
    if search:
        q["$or"] = [{"name": {"$regex": search, "$options": "i"}},
                    {"post_pin": {"$regex": search, "$options": "i"}}]
    docs = await db.dispatch_post_sites.find(q).skip(skip).limit(limit).to_list(limit)
    return [_doc_out(d) for d in docs]


@router.get("/post-sites/{pid}")
async def get_post_site(pid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.view")
    doc = await db.dispatch_post_sites.find_one({"_id": _oid(pid)})
    if not doc: raise HTTPException(404, "Post Site not found")
    return _doc_out(doc)


@router.put("/post-sites/{pid}")
async def update_post_site(pid: str, payload: PostSiteUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.edit")
    upd = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "post_pin" in upd:
        dup = await db.dispatch_post_sites.find_one({"post_pin": upd["post_pin"], "_id": {"$ne": _oid(pid)}})
        if dup: raise HTTPException(400, "Post Pin already exists")
    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    r = await db.dispatch_post_sites.update_one({"_id": _oid(pid)}, {"$set": upd})
    if r.matched_count == 0: raise HTTPException(404, "Post Site not found")
    return _doc_out(await db.dispatch_post_sites.find_one({"_id": _oid(pid)}))


@router.delete("/post-sites/{pid}")
async def delete_post_site(pid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.post_sites.delete")
    r = await db.dispatch_post_sites.update_one({"_id": _oid(pid)},
                                                 {"$set": {"status": "inactive", "updated_at": _now()}})
    if r.matched_count == 0: raise HTTPException(404, "Post Site not found")
    return {"message": "Post Site deactivated"}


# =====================================================================
#  DISPATCH SCHEDULES
# =====================================================================
async def _check_conflict(db, officer_id: str, sched_date: str,
                          start: str, end: str, exclude_id: str = None):
    """Return existing conflicting schedule for the officer on the same date."""
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if e <= s:
        e += 24 * 60
    q = {"officer_id": officer_id, "date": sched_date,
         "shift_status": {"$ne": "Cancelled"}}
    if exclude_id:
        q["_id"] = {"$ne": _oid(exclude_id)}
    existing = await db.dispatch_schedules.find(q).to_list(500)
    for ex in existing:
        xs = _parse_hhmm(ex["start_time"])
        xe = _parse_hhmm(ex["end_time"])
        if xe <= xs:
            xe += 24 * 60
        if s < xe and xs < e:
            return ex
    return None


@router.post("/schedules")
async def create_schedule(payload: ScheduleCreate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.create")
    if payload.shift_type not in SHIFT_TYPES:
        raise HTTPException(400, f"Shift type must be one of {SHIFT_TYPES}")

    # Financial fields require perm
    financial_write = has_permission(user, "dispatch.financial.view")
    if not financial_write and (payload.duty_rate is not None or
                                payload.billing_rate is not None or
                                payload.work_order_number is not None):
        raise HTTPException(403, "You do not have permission to set financial fields.")

    # Verify references exist
    client = await db.dispatch_clients.find_one({"_id": _oid(payload.client_id)})
    if not client: raise HTTPException(400, "Invalid client")
    vendor = await db.dispatch_vendors.find_one({"_id": _oid(payload.vendor_id)})
    if not vendor: raise HTTPException(400, "Invalid vendor")
    post = await db.dispatch_post_sites.find_one({"_id": _oid(payload.post_site_id)})
    if not post: raise HTTPException(400, "Invalid post site")
    officer = await db.dispatch_officers.find_one({"_id": _oid(payload.officer_id)})
    if not officer: raise HTTPException(400, "Invalid officer")
    if officer.get("status") != "active":
        raise HTTPException(400, "Security Officer is not active.")

    # Conflict detection
    conflict = await _check_conflict(db, payload.officer_id, payload.date,
                                     payload.start_time, payload.end_time)
    if conflict:
        raise HTTPException(409,
            f"Security Officer already has another shift on {conflict['date']} "
            f"{conflict['start_time']}–{conflict['end_time']}.")

    hours = _duty_hours(payload.start_time, payload.end_time)
    doc = payload.model_dump()
    doc["duty_hours"] = hours
    doc["shift_status"] = "Not Started"
    doc["confirmation_status"] = "Not Confirmed"
    doc["confirmation_method"] = None
    doc["confirmed_by_id"] = None
    doc["confirmed_by_name"] = None
    doc["confirmed_at"] = None
    doc["actual_check_in"] = None
    doc["actual_check_out"] = None
    doc["actual_duty_hours"] = None
    doc["late_minutes"] = 0
    doc["early_minutes"] = 0
    doc["overtime_minutes"] = 0
    doc["created_by"] = str(user["_id"]); doc["created_at"] = _now()
    doc["updated_by"] = str(user["_id"]); doc["updated_at"] = _now()
    res = await db.dispatch_schedules.insert_one(doc)
    saved = await db.dispatch_schedules.find_one({"_id": res.inserted_id})
    return strip_financial(_doc_out(saved), user)


@router.get("/schedules")
async def list_schedules(request: Request, db=Depends(get_db),
                         officer_id: str = None, vendor_id: str = None,
                         client_id: str = None, post_site_id: str = None,
                         post_pin: str = None,
                         date_from: str = None, date_to: str = None,
                         shift_type: str = None,
                         confirmation_status: str = None,
                         shift_status: str = None,
                         search: str = "",
                         page: int = 1, limit: int = 50):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.view")
    limit = min(max(limit, 1), 250)
    page = max(page, 1)

    q = {}
    if officer_id: q["officer_id"] = officer_id
    if vendor_id: q["vendor_id"] = vendor_id
    if client_id: q["client_id"] = client_id
    if post_site_id: q["post_site_id"] = post_site_id
    if shift_type: q["shift_type"] = shift_type
    if confirmation_status: q["confirmation_status"] = confirmation_status
    if shift_status: q["shift_status"] = shift_status
    if date_from or date_to:
        date_q = {}
        if date_from: date_q["$gte"] = date_from
        if date_to: date_q["$lte"] = date_to
        q["date"] = date_q

    # Post Pin lookup — resolve to post_site ids
    if post_pin:
        posts = await db.dispatch_post_sites.find(
            {"post_pin": {"$regex": post_pin, "$options": "i"}}, {"_id": 1}
        ).to_list(500)
        pids = [str(p["_id"]) for p in posts]
        # combine with existing post_site_id if any
        if post_site_id and post_site_id not in pids:
            pids = []
        q["post_site_id"] = {"$in": pids} if pids else "__none__"

    total = await db.dispatch_schedules.count_documents(q)
    docs = await db.dispatch_schedules.find(q).sort([("date", -1), ("start_time", -1)]) \
        .skip((page - 1) * limit).limit(limit).to_list(limit)

    # Enrich with names + strip financial
    def _cache_key(coll, _id): return f"{coll}:{_id}"
    cache = {}

    async def _name(coll, _id, field="name"):
        if not _id: return None
        k = _cache_key(coll, _id)
        if k in cache: return cache[k]
        try:
            d = await db[coll].find_one({"_id": _oid(_id)}, {field: 1, "post_pin": 1})
        except Exception:
            d = None
        cache[k] = d
        return d

    out = []
    for d in docs:
        row = strip_financial(_doc_out(d), user)
        cli = await _name("dispatch_clients", d.get("client_id"))
        ven = await _name("dispatch_vendors", d.get("vendor_id"))
        off = await _name("dispatch_officers", d.get("officer_id"))
        pst = await _name("dispatch_post_sites", d.get("post_site_id"))
        row["client_name"] = cli.get("name") if cli else None
        row["vendor_name"] = ven.get("name") if ven else None
        row["officer_name"] = off.get("name") if off else None
        row["post_site_name"] = pst.get("name") if pst else None
        row["post_pin"] = pst.get("post_pin") if pst else None
        out.append(row)

    return {"items": out, "total": total, "page": page, "limit": limit}


@router.get("/schedules/{sid}")
async def get_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.view")
    doc = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not doc: raise HTTPException(404, "Schedule not found")
    return strip_financial(_doc_out(doc), user)


@router.put("/schedules/{sid}")
async def update_schedule(sid: str, payload: ScheduleUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.edit")
    existing = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not existing: raise HTTPException(404, "Schedule not found")

    upd = {k: v for k, v in payload.model_dump().items() if v is not None}

    # Financial field guard
    fin_write = has_permission(user, "dispatch.financial.view")
    if not fin_write:
        for f in FINANCIAL_FIELDS:
            if f in upd:
                raise HTTPException(403, "You do not have permission to modify financial fields.")

    # Validate shift type / statuses
    if "shift_type" in upd and upd["shift_type"] not in SHIFT_TYPES:
        raise HTTPException(400, f"Shift type must be one of {SHIFT_TYPES}")
    if "shift_status" in upd and upd["shift_status"] not in SHIFT_STATUSES:
        raise HTTPException(400, f"Shift status must be one of {SHIFT_STATUSES}")

    # Recompute duty_hours if times changed
    st = upd.get("start_time", existing["start_time"])
    et = upd.get("end_time", existing["end_time"])
    upd["duty_hours"] = _duty_hours(st, et)

    # Conflict re-check when officer/date/times change
    if any(k in upd for k in ("officer_id", "date", "start_time", "end_time")):
        conflict = await _check_conflict(
            db, upd.get("officer_id", existing["officer_id"]),
            upd.get("date", existing["date"]),
            st, et, exclude_id=sid
        )
        if conflict:
            raise HTTPException(409,
                f"Security Officer already has another shift on {conflict['date']} "
                f"{conflict['start_time']}–{conflict['end_time']}.")

    upd["updated_by"] = str(user["_id"]); upd["updated_at"] = _now()
    await db.dispatch_schedules.update_one({"_id": _oid(sid)}, {"$set": upd})
    return strip_financial(_doc_out(await db.dispatch_schedules.find_one({"_id": _oid(sid)})), user)


@router.post("/schedules/{sid}/cancel")
async def cancel_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.cancel")
    r = await db.dispatch_schedules.update_one(
        {"_id": _oid(sid)},
        {"$set": {"shift_status": "Cancelled", "updated_by": str(user["_id"]), "updated_at": _now()}}
    )
    if r.matched_count == 0: raise HTTPException(404, "Schedule not found")
    return {"message": "Schedule cancelled"}


@router.delete("/schedules/{sid}")
async def delete_schedule(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.schedule.delete")
    r = await db.dispatch_schedules.delete_one({"_id": _oid(sid)})
    if r.deleted_count == 0: raise HTTPException(404, "Schedule not found")
    return {"message": "Schedule deleted"}


# ---------- Confirmation ----------
@router.post("/schedules/{sid}/confirm")
async def confirm_schedule(sid: str, payload: ConfirmationUpdate, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.confirmation.manage")
    if payload.confirmation_status not in CONFIRMATION_STATUSES:
        raise HTTPException(400, f"Confirmation status must be one of {CONFIRMATION_STATUSES}")
    if payload.confirmation_method and payload.confirmation_method not in CONFIRMATION_METHODS:
        raise HTTPException(400, f"Method must be one of {CONFIRMATION_METHODS}")

    sched = await db.dispatch_schedules.find_one({"_id": _oid(sid)})
    if not sched: raise HTTPException(404, "Schedule not found")

    now = _now()
    await db.dispatch_schedules.update_one(
        {"_id": _oid(sid)},
        {"$set": {
            "confirmation_status": payload.confirmation_status,
            "confirmation_method": payload.confirmation_method,
            "confirmed_by_id": str(user["_id"]),
            "confirmed_by_name": user.get("name"),
            "confirmed_at": now,
            "updated_by": str(user["_id"]),
            "updated_at": now,
        }}
    )
    # Append history entry
    await db.dispatch_confirmation_history.insert_one({
        "schedule_id": sid,
        "officer_id": sched.get("officer_id"),
        "status": payload.confirmation_status,
        "method": payload.confirmation_method,
        "remarks": payload.remarks,
        "contacted_by_id": str(user["_id"]),
        "contacted_by_name": user.get("name"),
        "contacted_by_role": user.get("role"),
        "contacted_by_department_id": user.get("department_id"),
        "contacted_at": now,
    })
    return {"message": "Confirmation updated"}


@router.get("/schedules/{sid}/history")
async def schedule_history(sid: str, request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.confirmation.history")
    docs = await db.dispatch_confirmation_history.find({"schedule_id": sid}) \
        .sort("contacted_at", -1).to_list(500)
    return [_doc_out(d) for d in docs]


# =====================================================================
#  DASHBOARD  (aggregates)
# =====================================================================
@router.get("/dashboard/stats")
async def dashboard_stats(request: Request, db=Depends(get_db)):
    user = await get_current_user(request, db)
    require_permission(user, "dispatch.dashboard.view")
    today = date.today().isoformat()
    base = {"date": today}
    stats = {
        "today_total": await db.dispatch_schedules.count_documents(base),
        "confirmed": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Confirmed"}),
        "pending": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Pending"}),
        "no_response": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "No Response"}),
        "declined": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Declined"}),
        "not_confirmed": await db.dispatch_schedules.count_documents({**base, "confirmation_status": "Not Confirmed"}),
        "late": await db.dispatch_schedules.count_documents({**base, "shift_status": "Late Clock In"}),
        "absent": await db.dispatch_schedules.count_documents({**base, "shift_status": "Absent"}),
        "clients": await db.dispatch_clients.count_documents({"status": "active"}),
        "vendors": await db.dispatch_vendors.count_documents({"status": "active"}),
        "officers": await db.dispatch_officers.count_documents({"status": "active"}),
        "post_sites": await db.dispatch_post_sites.count_documents({"status": "active"}),
    }
    # Open posts (required - assigned today)
    posts = await db.dispatch_post_sites.find({"status": "active"}).to_list(1000)
    open_positions = 0
    for p in posts:
        assigned = await db.dispatch_schedules.count_documents({
            "post_site_id": str(p["_id"]), "date": today,
            "shift_status": {"$ne": "Cancelled"}
        })
        req = p.get("required_officers", 1) or 1
        if assigned < req:
            open_positions += (req - assigned)
    stats["open_positions"] = open_positions
    return stats
