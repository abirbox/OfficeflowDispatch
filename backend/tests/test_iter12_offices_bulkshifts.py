"""Iter 12 tests: office geocoding, address-only office create, bulk shift assignment + reports smoke."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8001"

ADMIN_EMAIL = "mahossain432@gmail.com"
ADMIN_PASS = "Admin@2026Secure"
EMP_EMAIL = "employee@officeflow.com"
EMP_PASS = "Employee@123"


def _login(email, pw):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def admin():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def employee():
    # Try login; if not exists register
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMP_EMAIL, "password": EMP_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Employee login unavailable: {r.status_code}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ---------- Office geocoding ----------
class TestOfficeGeocoding:
    def test_geocode_valid_address(self, admin):
        r = admin.get(f"{BASE_URL}/api/office-locations/geocode", params={"address": "Gulshan 2, Dhaka, Bangladesh"}, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert d["found"] is True
        assert isinstance(d["latitude"], float)
        assert isinstance(d["longitude"], float)
        time.sleep(1.2)

    def test_geocode_missing_address(self, admin):
        r = admin.get(f"{BASE_URL}/api/office-locations/geocode", params={"address": ""}, timeout=15)
        assert r.status_code == 400

    def test_geocode_available_to_employee(self, employee):
        r = employee.get(f"{BASE_URL}/api/office-locations/geocode", params={"address": "Banani, Dhaka, Bangladesh"}, timeout=20)
        assert r.status_code == 200
        time.sleep(1.2)


# ---------- Office create (address-only auto-geocode) ----------
class TestOfficeCreate:
    created_ids = []

    def test_create_office_address_only(self, admin):
        name = f"TEST_Off_{uuid.uuid4().hex[:6]}"
        r = admin.post(f"{BASE_URL}/api/office-locations", json={
            "name": name, "address": "Banani, Dhaka, Bangladesh", "radius_meters": 120,
        }, timeout=25)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["name"] == name
        assert d["latitude"] and d["longitude"]
        assert d["address"] == "Banani, Dhaka, Bangladesh"
        TestOfficeCreate.created_ids.append(d["id"])
        time.sleep(1.2)

    def test_create_office_name_only_400(self, admin):
        r = admin.post(f"{BASE_URL}/api/office-locations", json={"name": f"TEST_bad_{uuid.uuid4().hex[:5]}"}, timeout=15)
        assert r.status_code == 400

    def test_create_office_with_explicit_coords(self, admin):
        name = f"TEST_Off_{uuid.uuid4().hex[:6]}"
        r = admin.post(f"{BASE_URL}/api/office-locations", json={
            "name": name, "address": "manual", "latitude": 23.79, "longitude": 90.41, "radius_meters": 100,
        }, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert abs(d["latitude"] - 23.79) < 0.01
        TestOfficeCreate.created_ids.append(d["id"])

    def test_cleanup(self, admin):
        for oid in TestOfficeCreate.created_ids:
            admin.delete(f"{BASE_URL}/api/office-locations/{oid}", timeout=10)


# ---------- Bulk shifts ----------
class TestBulkShifts:
    created_shift_ids = []

    @pytest.fixture(scope="class")
    def user_ids(self, admin):
        # Fetch employees
        r = admin.get(f"{BASE_URL}/api/employees", timeout=15)
        assert r.status_code == 200, r.text
        users = r.json()
        emp_ids = [u.get("id") for u in users if u.get("role") == "employee"][:2]
        if len(emp_ids) < 1:
            pytest.skip("Need at least one employee user for bulk-shift test")
        return emp_ids

    def test_bulk_create_success(self, admin, user_ids):
        payload = {
            "user_ids": user_ids,
            "title": "TEST_Bulk Shift",
            "work_location": "in_office",
            "start_time": "09:00",
            "end_time": "17:00",
            "days_of_week": [1, 2, 3, 4, 5],
            "effective_from": "2030-01-01",
            "effective_to": "2030-01-31",
        }
        r = admin.post(f"{BASE_URL}/api/shifts/bulk", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "created_count" in d and "created_ids" in d and "skipped" in d
        assert d["created_count"] == len(user_ids)
        TestBulkShifts.created_shift_ids.extend(d["created_ids"])

    def test_bulk_overlap_skip(self, admin, user_ids):
        payload = {
            "user_ids": user_ids,
            "title": "TEST_Bulk Overlap",
            "work_location": "in_office",
            "start_time": "10:00",
            "end_time": "18:00",
            "days_of_week": [1, 2, 3],
            "effective_from": "2030-01-15",
            "effective_to": "2030-02-15",
        }
        r = admin.post(f"{BASE_URL}/api/shifts/bulk", json=payload, timeout=20)
        assert r.status_code == 200
        d = r.json()
        # All the ones from prev test should be skipped as overlap
        assert len(d["skipped"]) >= 1
        assert d["skipped"][0]["reason"] == "overlapping shift already assigned"
        TestBulkShifts.created_shift_ids.extend(d.get("created_ids", []))

    def test_bulk_empty_users_400(self, admin):
        r = admin.post(f"{BASE_URL}/api/shifts/bulk", json={
            "user_ids": [], "title": "x", "work_location": "in_office",
            "start_time": "09:00", "end_time": "17:00", "days_of_week": [1],
            "effective_from": "2030-03-01", "effective_to": "2030-03-31",
        }, timeout=15)
        assert r.status_code == 400

    def test_bulk_empty_days_400(self, admin, user_ids):
        r = admin.post(f"{BASE_URL}/api/shifts/bulk", json={
            "user_ids": user_ids, "title": "x", "work_location": "in_office",
            "start_time": "09:00", "end_time": "17:00", "days_of_week": [],
            "effective_from": "2030-03-01", "effective_to": "2030-03-31",
        }, timeout=15)
        assert r.status_code == 400

    def test_bulk_employee_403(self, employee, user_ids):
        r = employee.post(f"{BASE_URL}/api/shifts/bulk", json={
            "user_ids": user_ids, "title": "x", "work_location": "in_office",
            "start_time": "09:00", "end_time": "17:00", "days_of_week": [1],
            "effective_from": "2030-04-01", "effective_to": "2030-04-30",
        }, timeout=15)
        assert r.status_code == 403

    def test_cleanup_shifts(self, admin):
        for sid in TestBulkShifts.created_shift_ids:
            admin.delete(f"{BASE_URL}/api/shifts/{sid}", timeout=10)


# ---------- Reports smoke (regression) ----------
class TestReports:
    def test_summary_admin(self, admin):
        from datetime import datetime
        n = datetime.utcnow()
        r = admin.get(f"{BASE_URL}/api/reports/summary", params={"month": n.month, "year": n.year}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for key in ("employees", "attendance", "leaves", "overtime"):
            assert key in d

    def test_attendance_admin(self, admin):
        from datetime import datetime
        n = datetime.utcnow()
        r = admin.get(f"{BASE_URL}/api/reports/attendance", params={"month": n.month, "year": n.year}, timeout=15)
        assert r.status_code == 200
        assert "rows" in r.json()

    def test_payroll_admin(self, admin):
        from datetime import datetime
        n = datetime.utcnow()
        r = admin.get(f"{BASE_URL}/api/reports/payroll", params={"month": n.month, "year": n.year}, timeout=15)
        assert r.status_code == 200

    def test_overtime_admin(self, admin):
        from datetime import datetime
        n = datetime.utcnow()
        r = admin.get(f"{BASE_URL}/api/reports/overtime", params={"month": n.month, "year": n.year}, timeout=15)
        assert r.status_code == 200

    def test_reports_employee_403(self, employee):
        from datetime import datetime
        n = datetime.utcnow()
        r = employee.get(f"{BASE_URL}/api/reports/summary", params={"month": n.month, "year": n.year}, timeout=15)
        assert r.status_code == 403
