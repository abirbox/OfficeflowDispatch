"""
Iteration 8 tests: App Settings (branding/currency/timezone), Employee create w/ password,
Payroll PDF invoice, Live-map location fallback, Shifts timezone (Asia/Dhaka).
"""
import io
import os
import time
import uuid
import pytest
import requests
from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pymongo import MongoClient
from bson import ObjectId

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN = {"email": "mahossain432@gmail.com", "password": "Admin@2026Secure"}

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
_mc = MongoClient(MONGO_URL)
_db = _mc[DB_NAME]


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="module")
def admin_session():
    return _login(**ADMIN)


@pytest.fixture(scope="module")
def employee_session(admin_session):
    creds = {"email": "employee@officeflow.com", "password": "Employee@123"}
    try:
        return _login(**creds)
    except AssertionError:
        a_sess, _ = admin_session
        r = a_sess.post(f"{BASE}/auth/register", json={
            "email": creds["email"], "password": creds["password"],
            "name": "Test Employee", "role": "employee",
        })
        assert r.status_code == 200, r.text
        return _login(**creds)


# =============== SETTINGS ===============

def test_settings_public_no_auth():
    r = requests.get(f"{BASE}/settings/public", timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("brand_name", "login_hero_title", "login_hero_subtitle",
              "login_welcome_title", "login_welcome_subtitle",
              "currency", "currency_symbol"):
        assert k in d, f"missing {k}"
    assert "brand_logo_url" in d  # may be None


def test_settings_auth_returns_timezone(admin_session):
    s, _ = admin_session
    r = s.get(f"{BASE}/settings")
    assert r.status_code == 200
    d = r.json()
    assert "timezone" in d and "tz_offset_hours" in d


def test_settings_currencies_list():
    r = requests.get(f"{BASE}/settings/currencies")
    assert r.status_code == 200
    codes = {c["code"] for c in r.json()}
    for c in ("BDT", "USD", "EUR", "GBP", "INR"):
        assert c in codes


def test_settings_timezones_list():
    r = requests.get(f"{BASE}/settings/timezones")
    assert r.status_code == 200
    tzs = r.json()
    assert tzs[0]["code"] == "Asia/Dhaka"
    assert tzs[0]["offset"] == 6.0


def test_settings_put_non_admin_forbidden(employee_session):
    s, _ = employee_session
    r = s.put(f"{BASE}/settings", json={"brand_name": "HackedName"})
    assert r.status_code == 403


def test_settings_put_admin_updates_and_derives(admin_session):
    s, _ = admin_session
    new_brand = f"OF-TEST-{uuid.uuid4().hex[:6]}"
    # Set to USD -> symbol auto-derive to $
    r = s.put(f"{BASE}/settings", json={
        "brand_name": new_brand, "currency": "USD", "timezone": "Asia/Dhaka"
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["brand_name"] == new_brand
    assert d["currency"] == "USD"
    assert d["currency_symbol"] == "$"
    assert d["timezone"] == "Asia/Dhaka"
    assert d["tz_offset_hours"] == 6.0

    # public reflects
    pub = requests.get(f"{BASE}/settings/public").json()
    assert pub["brand_name"] == new_brand
    assert pub["currency"] == "USD"

    # Restore to BDT for downstream tests
    r = s.put(f"{BASE}/settings", json={
        "brand_name": "OfficeFlow", "currency": "BDT", "timezone": "Asia/Dhaka"
    })
    assert r.status_code == 200
    assert r.json()["currency_symbol"] == "৳"


# =============== EMPLOYEE CREATE with password ===============

def test_create_employee_with_password_can_login(admin_session):
    s, _ = admin_session
    email = f"test_iter8_emp_{int(time.time())}_{uuid.uuid4().hex[:5]}@example.com"
    pw = "Test@Pass123"
    r = s.post(f"{BASE}/employees", json={
        "email": email, "name": "IT8 Emp With PW",
        "password": pw, "role": "employee",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email
    assert body["role"] == "employee"

    # Now login
    login = requests.post(f"{BASE}/auth/login", json={"email": email, "password": pw})
    assert login.status_code == 200, login.text
    assert login.json()["role"] == "employee"


def test_create_employee_default_password_welcome(admin_session):
    s, _ = admin_session
    email = f"test_iter8_dfl_{int(time.time())}_{uuid.uuid4().hex[:5]}@example.com"
    r = s.post(f"{BASE}/employees", json={
        "email": email, "name": "IT8 Default PW", "role": "employee",
    })
    assert r.status_code == 200, r.text
    login = requests.post(f"{BASE}/auth/login",
                          json={"email": email, "password": "Welcome@123"})
    assert login.status_code == 200, login.text


# =============== PAYROLL PDF ===============

@pytest.fixture(scope="module")
def payroll_record(admin_session, employee_session):
    a_sess, _ = admin_session
    _, emp = employee_session
    # use a distinct month/year to avoid duplicate
    now = datetime.now(timezone.utc)
    # go 3 months back
    m = now.month - 3
    y = now.year
    if m <= 0:
        m += 12
        y -= 1
    # delete any pre-existing
    _db.payroll.delete_many({"user_id": emp["id"], "month": m, "year": y})
    r = a_sess.post(f"{BASE}/payroll", json={
        "user_id": emp["id"], "month": m, "year": y,
        "base_salary": 50000, "bonuses": 2500, "deductions": 500,
        "notes": "iter8 test payslip",
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_payroll_pdf_admin_downloads(admin_session, payroll_record):
    s, _ = admin_session
    r = s.get(f"{BASE}/payroll/{payroll_record['id']}/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    body = r.content
    assert body[:5] == b"%PDF-"
    assert 1500 < len(body) < 50000
    disp = r.headers.get("content-disposition", "")
    assert "payslip_" in disp
    assert str(payroll_record["year"]) in disp


def test_payroll_pdf_employee_own(employee_session, payroll_record):
    s, _ = employee_session
    r = s.get(f"{BASE}/payroll/{payroll_record['id']}/pdf")
    assert r.status_code == 200, r.text
    assert r.content[:5] == b"%PDF-"


def test_payroll_pdf_other_employee_forbidden(admin_session, payroll_record):
    a, _ = admin_session
    # create another employee via /employees
    email = f"test_iter8_pdfneg_{int(time.time())}@example.com"
    r = a.post(f"{BASE}/employees", json={
        "email": email, "name": "IT8 Other", "password": "Pass@1234", "role": "employee",
    })
    assert r.status_code == 200, r.text
    other, _ = _login(email, "Pass@1234")
    r = other.get(f"{BASE}/payroll/{payroll_record['id']}/pdf")
    assert r.status_code == 403


# =============== TIMEZONE (Asia/Dhaka) ===============

def test_shift_join_uses_dhaka_late_calculation(admin_session, employee_session):
    """
    Force a shift with start_time=09:00 in Asia/Dhaka.
    Compute expected late_minutes = max(0, local_now_minutes - 540).
    Join and validate.
    """
    a, _ = admin_session
    e_sess, emp = employee_session
    # ensure fresh: delete any shift_session for today
    today_dhaka = datetime.now(ZoneInfo("Asia/Dhaka")).date().isoformat()
    _db.shift_sessions.delete_many({"user_id": emp["id"], "date": today_dhaka})
    _db.attendance.delete_many({"user_id": emp["id"], "date": today_dhaka})

    r = a.post(f"{BASE}/shifts", json={
        "user_id": emp["id"],
        "title": "TEST IT8 TZ Shift",
        "work_location": "in_office",
        "start_time": "09:00", "end_time": "17:00",
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": str(date.today()),
        "effective_to": str(date.today() + timedelta(days=1)),
    })
    assert r.status_code == 200, r.text
    shift = r.json()

    now_dhaka = datetime.now(ZoneInfo("Asia/Dhaka"))
    now_mins = now_dhaka.hour * 60 + now_dhaka.minute
    expected_late = max(0, now_mins - 540)

    r = e_sess.post(f"{BASE}/shifts/{shift['id']}/join")
    assert r.status_code == 200, r.text
    ses = r.json()
    # If Dhaka local time is before 09:05 (grace) is_late=False. Otherwise expected true.
    if expected_late > 5:
        assert ses["is_late"] is True
        # allow +/-1 minute drift
        assert abs(ses["late_minutes"] - expected_late) <= 2, f"late_minutes={ses['late_minutes']} expected~{expected_late}"
    else:
        assert ses["is_late"] is False
    # date must be Dhaka local date
    assert ses["date"] == today_dhaka


# =============== LIVE-MAP FALLBACK ===============

def test_employee_status_falls_back_to_checkin_location(admin_session, employee_session):
    a, _ = admin_session
    _, emp = employee_session
    today = date.today().isoformat()
    # Ensure attendance with check_in_location + active gps_session w/o coords
    _db.attendance.update_one(
        {"user_id": emp["id"], "date": today},
        {"$set": {
            "user_id": emp["id"], "date": today,
            "check_in": datetime.now(timezone.utc).isoformat(),
            "check_out": None,
            "check_in_location": {"latitude": 23.81, "longitude": 90.41},
        }},
        upsert=True,
    )
    # Delete any existing active session first, then insert empty-coord one
    _db.gps_sessions.delete_many({"user_id": emp["id"], "status": "active"})
    _db.gps_sessions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": emp["id"], "status": "active",
        "coordinates": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc),
    })

    r = a.get(f"{BASE}/admin/employee-status")
    assert r.status_code == 200, r.text
    row = next((x for x in r.json() if x["id"] == emp["id"]), None)
    assert row is not None
    loc = row.get("current_location")
    assert loc is not None, f"expected fallback location but got None for row={row}"
    assert loc["latitude"] == 23.81
    assert loc["longitude"] == 90.41

    # cleanup
    _db.gps_sessions.delete_many({"user_id": emp["id"], "status": "active"})


# =============== REGRESSION: quick sanity ===============

def test_regression_endpoints_up(admin_session):
    s, _ = admin_session
    for path in ("/auth/me", "/shifts", "/overtime", "/leaves",
                 "/payroll", "/notifications", "/admin/dashboard-stats"):
        r = s.get(f"{BASE}{path}")
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
