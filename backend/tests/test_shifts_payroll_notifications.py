"""
E2E backend tests for Work Shifts, Payroll, Notifications, and public-registration lockdown.
Uses the public REACT_APP_BACKEND_URL so it mirrors what the UI sees.
"""
import os
import time
import pytest
import requests
from datetime import date, timedelta

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"

ADMIN = {"email": "mahossain432@gmail.com", "password": "Admin@2026Secure"}
EMPLOYEE = {"email": "employee@officeflow.com", "password": "Employee@123"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="module")
def admin():
    s, u = _login(**ADMIN)
    return s, u


@pytest.fixture(scope="module")
def employee():
    s, u = _login(**EMPLOYEE)
    return s, u


@pytest.fixture(scope="module")
def cleanup_shifts(admin):
    """Delete all shifts belonging to the target employee before running tests."""
    a_sess, _ = admin
    _, emp_user = _login(**EMPLOYEE)
    emp_id = emp_user["id"]
    r = a_sess.get(f"{BASE}/shifts", params={"user_id": emp_id})
    if r.status_code == 200:
        for s in r.json():
            a_sess.delete(f"{BASE}/shifts/{s['id']}")
    return emp_id


# ---------- Public registration lockdown ----------

def test_anon_register_forbidden():
    r = requests.post(f"{BASE}/auth/register", json={
        "email": "TEST_should_not_create@example.com",
        "password": "Whatever@123",
        "name": "Nope",
        "role": "employee",
    }, timeout=15)
    assert r.status_code == 403
    body = r.json()
    assert "admin" in (body.get("detail", "") or "").lower()


def test_admin_can_still_register():
    # Use a dedicated admin session because /auth/register sets cookies for the
    # newly-created user, which would clobber the caller's session.
    s, _ = _login(**ADMIN)
    email = f"TEST_regbyadmin_{int(time.time())}@example.com"
    r = s.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Pass@1234", "name": "Reg By Admin", "role": "employee"
    })
    assert r.status_code == 200, r.text
    assert r.json()["email"].lower() == email.lower()


# ---------- Shift CRUD & RBAC ----------

def test_employee_cannot_create_shift(employee, cleanup_shifts):
    s, _ = employee
    r = s.post(f"{BASE}/shifts", json={
        "user_id": cleanup_shifts,
        "start_time": "09:00", "end_time": "17:00",
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": str(date.today()),
        "effective_to": str(date.today() + timedelta(days=30)),
    })
    assert r.status_code == 403


@pytest.fixture(scope="module")
def created_shift(admin, cleanup_shifts):
    a_sess, _ = admin
    # start_time in past so join won't be marked late (immediately) - actually we want to test late
    # Use current UTC hour so join happens near start_time
    r = a_sess.post(f"{BASE}/shifts", json={
        "user_id": cleanup_shifts,
        "title": "TEST Shift",
        "work_location": "in_office",
        "start_time": "09:00",
        "end_time": "17:00",
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": str(date.today()),
        "effective_to": str(date.today() + timedelta(days=30)),
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user_name"] is not None
    assert data["user_id"] == cleanup_shifts
    return data


def test_admin_shift_created_ok(created_shift):
    assert created_shift["status"] == "scheduled"
    assert created_shift["work_location"] == "in_office"


def test_employee_get_shifts_only_own(employee, created_shift):
    s, u = employee
    r = s.get(f"{BASE}/shifts")
    assert r.status_code == 200
    shifts = r.json()
    assert len(shifts) >= 1
    for sh in shifts:
        assert sh["user_id"] == u["id"]


def test_admin_get_all_shifts(admin, created_shift):
    s, _ = admin
    r = s.get(f"{BASE}/shifts")
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert created_shift["id"] in ids


# ---------- Join / End / Cancel ----------

def test_join_by_wrong_user_forbidden(admin, created_shift):
    s, _ = admin  # admin is not the assigned employee
    r = s.post(f"{BASE}/shifts/{created_shift['id']}/join")
    assert r.status_code == 403


def test_join_shift_and_gps_active(employee, created_shift):
    s, _ = employee
    r = s.post(f"{BASE}/shifts/{created_shift['id']}/join")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "joined"
    assert "is_late" in data and "late_minutes" in data

    # GPS should be active
    g = s.get(f"{BASE}/gps/active")
    assert g.status_code == 200
    assert g.json().get("active") is True


def test_join_twice_blocked(employee, created_shift):
    s, _ = employee
    r = s.post(f"{BASE}/shifts/{created_shift['id']}/join")
    assert r.status_code == 400


def test_end_shift_and_gps_stopped(employee, created_shift):
    s, _ = employee
    r = s.post(f"{BASE}/shifts/{created_shift['id']}/end")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "ended"
    assert data["work_hours"] >= 0
    g = s.get(f"{BASE}/gps/active")
    assert g.status_code == 200
    assert g.json().get("active") is False


# Cancel test needs a separate shift
@pytest.fixture(scope="module")
def cancel_shift(admin, cleanup_shifts):
    a_sess, _ = admin
    r = a_sess.post(f"{BASE}/shifts", json={
        "user_id": cleanup_shifts,
        "title": "TEST Cancel Shift",
        "work_location": "work_from_home",
        "start_time": "10:00", "end_time": "18:00",
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": str(date.today()),
        "effective_to": str(date.today() + timedelta(days=30)),
    })
    assert r.status_code == 200
    return r.json()


def test_cancel_shift_creates_admin_notification(employee, admin, cancel_shift):
    e_sess, _ = employee
    a_sess, _ = admin
    r = e_sess.post(f"{BASE}/shifts/{cancel_shift['id']}/cancel")
    assert r.status_code == 200, r.text

    # Verify admin got a notification
    n = a_sess.get(f"{BASE}/notifications")
    assert n.status_code == 200
    notifs = n.json()
    matched = [x for x in notifs if x.get("type") == "shift_cancelled" and x.get("reference_id") == cancel_shift["id"]]
    assert len(matched) >= 1, f"No shift_cancelled notification found. Got: {notifs[:3]}"


# ---------- Notifications endpoints ----------

def test_notifications_mark_read_flow(admin):
    s, _ = admin
    r = s.get(f"{BASE}/notifications")
    assert r.status_code == 200
    notifs = r.json()
    if not notifs:
        pytest.skip("no notifications to test mark-read")
    nid = notifs[0]["id"]
    r2 = s.post(f"{BASE}/notifications/{nid}/read")
    assert r2.status_code == 200

    r3 = s.post(f"{BASE}/notifications/read-all")
    assert r3.status_code == 200
    unread = s.get(f"{BASE}/notifications", params={"unread_only": True}).json()
    assert unread == []


# ---------- Payroll ----------

def test_payroll_preview_auto_computes(admin, cleanup_shifts):
    s, _ = admin
    today = date.today()
    r = s.get(f"{BASE}/payroll/preview/{cleanup_shifts}", params={"month": today.month, "year": today.year})
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ["total_hours", "overtime_hours", "leave_days", "late_days", "user_name", "user_email"]:
        assert k in data
    assert isinstance(data["leave_days"], int)


def test_payroll_create_and_duplicate_blocked(admin, cleanup_shifts):
    s, _ = admin
    today = date.today()
    # Cleanup any existing payroll for this month/user
    lst = s.get(f"{BASE}/payroll", params={"user_id": cleanup_shifts}).json()
    for p in lst:
        if p["month"] == today.month and p["year"] == today.year:
            # No delete endpoint - test may already be seeded. Use a far year to avoid clash.
            pass
    year = today.year + 5  # future year unlikely to have existing payroll
    payload = {
        "user_id": cleanup_shifts,
        "month": today.month,
        "year": year,
        "base_salary": 5000,
        "bonuses": 300,
        "deductions": 100,
    }
    r = s.post(f"{BASE}/payroll", json=payload)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["net_salary"] == 5000 + 300 - 100
    assert data["user_name"]

    # Duplicate
    r2 = s.post(f"{BASE}/payroll", json=payload)
    assert r2.status_code == 400
