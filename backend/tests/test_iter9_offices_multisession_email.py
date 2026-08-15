"""Iteration 9 backend tests:
- Office Locations CRUD + admin RBAC
- Nearest office (haversine, missing params, no offices)
- Attendance multi-session (check-in → out → in → out → in cycles)
- Legacy attendance backward compat via GET /today
- Payroll auto-email when RESEND_API_KEY absent + resend endpoint
- Payroll resend RBAC (403 for employee, 404 missing id)
- GPS start/stop for employees
"""
import os
import time
import uuid
import requests
import pytest
from pymongo import MongoClient
from datetime import date, datetime, timezone

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://officeflow-prod.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN = {"email": "mahossain432@gmail.com", "password": "Admin@2026Secure"}
EMP = {"email": "employee@officeflow.com", "password": "Employee@123"}


def _login(sess, creds):
    r = sess.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, f"login failed for {creds['email']}: {r.status_code} {r.text}"
    tok = r.json().get("access_token")
    if tok:
        sess.headers.update({"Authorization": f"Bearer {tok}"})
    return r.json()


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    _login(s, ADMIN)
    return s


@pytest.fixture(scope="module")
def employee():
    s = requests.Session()
    # ensure employee exists
    try:
        _login(s, EMP)
    except AssertionError:
        # create via admin
        adm = requests.Session()
        _login(adm, ADMIN)
        adm.post(f"{API}/employees", json={
            "email": EMP["email"], "name": "Test Employee",
            "password": EMP["password"], "role": "employee",
        })
        s = requests.Session()
        _login(s, EMP)
    return s


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


# -------- OFFICE LOCATIONS --------
class TestOfficeLocations:
    created_id = None

    def test_non_admin_create_403(self, employee):
        r = employee.post(f"{API}/office-locations", json={
            "name": "TEST_denied", "latitude": 23.8, "longitude": 90.4, "radius_meters": 100,
        })
        assert r.status_code == 403

    def test_admin_create(self, admin):
        r = admin.post(f"{API}/office-locations", json={
            "name": "TEST_HQ", "address": "Dhaka",
            "latitude": 23.8103, "longitude": 90.4125, "radius_meters": 150,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["name"] == "TEST_HQ"
        assert data["radius_meters"] == 150
        assert data["latitude"] == 23.8103
        TestOfficeLocations.created_id = data["id"]

    def test_list_offices_authenticated(self, employee):
        r = employee.get(f"{API}/office-locations")
        assert r.status_code == 200
        assert any(o["id"] == TestOfficeLocations.created_id for o in r.json())

    def test_update_office(self, admin):
        r = admin.put(f"{API}/office-locations/{TestOfficeLocations.created_id}", json={
            "radius_meters": 250,
        })
        assert r.status_code == 200
        assert r.json()["radius_meters"] == 250

    def test_nearest_missing_params(self, employee):
        r = employee.get(f"{API}/office-locations/nearest")
        assert r.status_code == 400

    def test_nearest_within_and_distance(self, employee):
        # 23.815,90.415 vs 23.8103,90.4125 -> ~581m
        r = employee.get(f"{API}/office-locations/nearest", params={"lat": 23.815, "lng": 90.415})
        assert r.status_code == 200
        j = r.json()
        assert j["office"] is not None
        assert 400 < j["distance_meters"] < 800
        assert j["within_geofence"] is False  # radius is 250

        r2 = employee.get(f"{API}/office-locations/nearest", params={"lat": 23.8103, "lng": 90.4125})
        assert r2.status_code == 200
        assert r2.json()["within_geofence"] is True

    def test_delete_office(self, admin):
        r = admin.delete(f"{API}/office-locations/{TestOfficeLocations.created_id}")
        assert r.status_code == 200

    def test_nearest_no_offices_returns_null(self, admin, employee, db):
        # Clean any TEST_ offices first
        db.office_locations.delete_many({"name": {"$regex": "^TEST_"}})
        # If there is at least one office not TEST_, we can't assert null. Only assert on empty case.
        cnt = db.office_locations.count_documents({})
        if cnt == 0:
            r = employee.get(f"{API}/office-locations/nearest", params={"lat": 10, "lng": 10})
            assert r.status_code == 200
            assert r.json()["office"] is None


# -------- ATTENDANCE MULTI-SESSION --------
class TestAttendanceMultiSession:
    def _reset_today(self, db, emp):
        # Get employee _id
        me = emp.get(f"{API}/auth/me").json()
        uid = me["id"]
        today = date.today().isoformat()
        db.attendance.delete_many({"user_id": uid, "date": today})
        # stop any active gps
        db.gps_sessions.update_many({"user_id": uid, "status": "active"},
                                     {"$set": {"status": "ended"}})
        return uid

    def test_multi_session_cycles(self, employee, db):
        self._reset_today(db, employee)

        # cycle 1
        r1 = employee.post(f"{API}/attendance/check-in", json={"latitude": 23.81, "longitude": 90.41})
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["is_working"] is True
        assert len(d1["sessions"]) == 1

        # double check-in should 400
        r_dup = employee.post(f"{API}/attendance/check-in", json={"latitude": 23.81, "longitude": 90.41})
        assert r_dup.status_code == 400
        assert "already checked in" in r_dup.json()["detail"].lower()

        time.sleep(1.2)
        r2 = employee.post(f"{API}/attendance/check-out", json={"latitude": 23.81, "longitude": 90.41})
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["is_working"] is False
        assert len(d2["sessions"]) == 1
        first_total = d2["total_hours"]

        # cycle 2 - start again succeeds
        r3 = employee.post(f"{API}/attendance/check-in", json={"latitude": 23.81, "longitude": 90.41})
        assert r3.status_code == 200, r3.text
        d3 = r3.json()
        assert d3["is_working"] is True
        assert len(d3["sessions"]) == 2

        time.sleep(1.2)
        r4 = employee.post(f"{API}/attendance/check-out", json={"latitude": 23.81, "longitude": 90.41})
        assert r4.status_code == 200
        d4 = r4.json()
        assert d4["is_working"] is False
        assert len(d4["sessions"]) == 2
        assert d4["total_hours"] >= first_total  # accumulates

        # today endpoint
        r5 = employee.get(f"{API}/attendance/today")
        assert r5.status_code == 200
        j5 = r5.json()
        assert j5["checked_in"] is False  # not working
        assert len(j5["attendance"]["sessions"]) == 2

    def test_legacy_backfill(self, employee, db):
        # write a legacy doc (no sessions[])
        uid = self._reset_today(db, employee)
        today = date.today().isoformat()
        legacy = {
            "id": str(uuid.uuid4()),
            "user_id": uid,
            "date": today,
            "check_in": datetime.now(timezone.utc).isoformat(),
            "check_out": datetime.now(timezone.utc).isoformat(),
            "total_hours": 3.5,
            "status": "present",
            "created_at": datetime.now(timezone.utc),
        }
        db.attendance.insert_one(legacy)
        r = employee.get(f"{API}/attendance/today")
        assert r.status_code == 200
        att = r.json()["attendance"]
        assert att is not None
        assert len(att["sessions"]) == 1  # backfilled
        assert att["total_hours"] == 3.5
        # cleanup
        db.attendance.delete_one({"id": legacy["id"]})


# -------- PAYROLL EMAIL --------
class TestPayrollEmail:
    def _get_or_make_emp_uid(self, db, admin_sess):
        emp = db.users.find_one({"email": EMP["email"]})
        if not emp:
            pytest.skip("employee user missing")
        return str(emp["_id"])

    def test_create_payroll_no_resend_key(self, admin, db):
        # Ensure RESEND_API_KEY not set in the running backend env
        # (we don't restart in test — just assert branch behaviour)
        uid = self._get_or_make_emp_uid(db, admin)
        # unique month/year not previously used
        # try current month - 4 to avoid collisions
        today = date.today()
        y, m = today.year, today.month - 4
        while m <= 0:
            m += 12
            y -= 1
        # remove any existing
        db.payroll.delete_many({"user_id": uid, "month": m, "year": y})

        r = admin.post(f"{API}/payroll", json={
            "user_id": uid, "month": m, "year": y,
            "base_salary": 5000, "bonuses": 200, "deductions": 100,
            "notes": "iter9 test",
        })
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        # Poll DB briefly: email flag might be set asynchronously (it's actually inline)
        doc = None
        for _ in range(6):
            doc = db.payroll.find_one({"id": pid})
            if doc and "email_result" in doc:
                break
            time.sleep(0.5)
        assert doc is not None
        # If RESEND_API_KEY not configured, we expect email_sent=false, reason='no_api_key'
        if not os.environ.get("RESEND_API_KEY"):
            assert doc.get("email_sent") is False
            assert doc.get("email_result", {}).get("reason") == "no_api_key"
        TestPayrollEmail.pid = pid

    def test_resend_endpoint_no_api_key(self, admin):
        pid = getattr(TestPayrollEmail, "pid", None)
        if not pid:
            pytest.skip("no payroll created")
        r = admin.post(f"{API}/payroll/{pid}/email")
        assert r.status_code == 200
        j = r.json()
        if not os.environ.get("RESEND_API_KEY"):
            assert j["sent"] is False
            assert j.get("reason") == "no_api_key"

    def test_resend_forbidden_for_employee(self, employee):
        pid = getattr(TestPayrollEmail, "pid", None)
        if not pid:
            pytest.skip("no payroll created")
        r = employee.post(f"{API}/payroll/{pid}/email")
        assert r.status_code == 403

    def test_resend_404_missing(self, admin):
        r = admin.post(f"{API}/payroll/nonexistent-id-xyz/email")
        assert r.status_code == 404


# -------- GPS EMPLOYEE START/STOP --------
class TestGPSEmployee:
    def test_start_stop(self, employee):
        r = employee.post(f"{API}/gps/start", json={"latitude": 23.8, "longitude": 90.4})
        assert r.status_code in (200, 201), r.text
        sid = r.json().get("id")
        assert sid
        r2 = employee.post(f"{API}/gps/{sid}/stop")
        assert r2.status_code == 200, r2.text


# -------- REGRESSION SANITY --------
class TestRegression:
    def test_auth_me(self, admin, employee):
        assert admin.get(f"{API}/auth/me").status_code == 200
        assert employee.get(f"{API}/auth/me").status_code == 200

    def test_settings_public(self):
        r = requests.get(f"{API}/settings/public")
        assert r.status_code == 200

    def test_admin_stats(self, admin):
        assert admin.get(f"{API}/admin/dashboard-stats").status_code == 200

    def test_leaves_list(self, employee):
        assert employee.get(f"{API}/leaves").status_code == 200

    def test_shifts_list(self, employee):
        assert employee.get(f"{API}/shifts").status_code == 200

    def test_notifications(self, employee):
        assert employee.get(f"{API}/notifications").status_code == 200
