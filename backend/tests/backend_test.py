"""
OfficeFlow backend regression tests (pytest).

NOTE: The public preview URL (REACT_APP_BACKEND_URL) is currently returning
Emergent's "Not Found" marketing page (ingress not routed to this pod).
Tests are executed against the internal supervisor-managed backend on
localhost:8001 which is what the ingress *should* be forwarding to.
"""
import os
import time
import uuid
import pytest
import requests

# Prefer localhost for regression until preview ingress is fixed.
BASE_URL = os.environ.get("BACKEND_TEST_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "mahossain432@gmail.com"
ADMIN_PASSWORD = "Admin@2026Secure"


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text}")
    # Cookies are set with Secure+SameSite=None, so `requests` will not resend
    # them over http://localhost. Extract from Set-Cookie and pass via header.
    access = r.cookies.get("access_token")
    refresh = r.cookies.get("refresh_token")
    cookie_hdr_parts = []
    if access:
        cookie_hdr_parts.append(f"access_token={access}")
    if refresh:
        cookie_hdr_parts.append(f"refresh_token={refresh}")
    if cookie_hdr_parts:
        s.headers.update({"Cookie": "; ".join(cookie_hdr_parts)})
    return s


# ---------------- Health ----------------
class TestHealth:
    def test_health(self):
        r = requests.get(f"{API}/health")
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"

    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert "OfficeFlow" in r.json().get("message", "")


# ---------------- Auth ----------------
class TestAuth:
    def test_login_success_sets_cookies(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] in ("super_admin", "admin")
        # httpOnly cookies
        cookies_hdr = ";".join(r.headers.get_all("set-cookie") if hasattr(r.headers, "get_all") else r.raw.headers.getlist("set-cookie")) if False else ""
        # requests lowercases headers; just check the cookie jar
        names = {c.name for c in r.cookies}
        assert "access_token" in names
        assert "refresh_token" in names

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN_EMAIL, "password": "wrong-pass"})
        assert r.status_code in (401, 429)

    def test_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_me_without_auth(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code in (401, 403)

    def test_logout(self, admin_session):
        # Use a separate session so we don't kill admin_session for other tests
        s = requests.Session()
        s.post(f"{API}/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200


# ---------------- Companies ----------------
class TestCompanies:
    def test_list_companies(self, admin_session):
        r = admin_session.get(f"{API}/companies")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_get_delete_company(self, admin_session):
        payload = {"name": f"TEST_Company_{uuid.uuid4().hex[:6]}",
                   "industry": "Tech", "size": "1-10"}
        r = admin_session.post(f"{API}/companies", json=payload)
        assert r.status_code == 200, r.text
        company = r.json()
        assert company["name"] == payload["name"]
        cid = company["id"]

        # GET verifies persistence
        r2 = admin_session.get(f"{API}/companies/{cid}")
        assert r2.status_code == 200
        assert r2.json()["name"] == payload["name"]

        # Cleanup
        r3 = admin_session.delete(f"{API}/companies/{cid}")
        assert r3.status_code == 200

        # Should no longer appear
        r4 = admin_session.get(f"{API}/companies/{cid}")
        assert r4.status_code == 404


# ---------------- Employees ----------------
class TestEmployees:
    def test_list_employees(self, admin_session):
        r = admin_session.get(f"{API}/employees")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Admin user must be present
        emails = [e["email"] for e in data]
        assert ADMIN_EMAIL in emails


# ---------------- Attendance ----------------
class TestAttendance:
    def test_today_shape(self, admin_session):
        r = admin_session.get(f"{API}/attendance/today")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "checked_in" in body
        assert "attendance" in body
        assert isinstance(body["checked_in"], bool)

    def test_history(self, admin_session):
        r = admin_session.get(f"{API}/attendance/history")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats(self, admin_session):
        r = admin_session.get(f"{API}/attendance/stats")
        assert r.status_code == 200
        for k in ("total_days", "present_days", "total_hours"):
            assert k in r.json()


# ---------------- GPS ----------------
class TestGPS:
    def test_active_no_session(self, admin_session):
        r = admin_session.get(f"{API}/gps/active")
        assert r.status_code == 200
        body = r.json()
        assert "active" in body
        assert "session" in body

    def test_history(self, admin_session):
        r = admin_session.get(f"{API}/gps/history")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Tasks ----------------
class TestTasks:
    created_task_id = None

    def test_list_tasks(self, admin_session):
        r = admin_session.get(f"{API}/tasks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_get_update_delete_task(self, admin_session):
        payload = {
            "title": f"TEST_Task_{uuid.uuid4().hex[:6]}",
            "description": "regression test task",
            "priority": "medium",
            "status": "todo",
        }
        r = admin_session.post(f"{API}/tasks", json=payload)
        assert r.status_code == 200, r.text
        task = r.json()
        assert task["title"] == payload["title"]
        assert task["status"] == "todo"
        tid = task["id"]

        # GET
        r2 = admin_session.get(f"{API}/tasks/{tid}")
        assert r2.status_code == 200
        assert r2.json()["title"] == payload["title"]

        # UPDATE status
        r3 = admin_session.put(f"{API}/tasks/{tid}", json={"status": "in_progress"})
        assert r3.status_code == 200
        assert r3.json()["status"] == "in_progress"

        # Persistence check
        r4 = admin_session.get(f"{API}/tasks/{tid}")
        assert r4.json()["status"] == "in_progress"

        # DELETE
        r5 = admin_session.delete(f"{API}/tasks/{tid}")
        assert r5.status_code == 200
        r6 = admin_session.get(f"{API}/tasks/{tid}")
        assert r6.status_code == 404

    def test_task_stats(self, admin_session):
        r = admin_session.get(f"{API}/tasks/stats/overview")
        assert r.status_code == 200
        for k in ("total", "todo", "in_progress", "done"):
            assert k in r.json()


# ---------------- Public preview ingress ----------------
class TestPublicIngress:
    """Confirms whether the preview URL forwards /api to the backend."""

    PUBLIC_URL = os.environ.get(
        "REACT_APP_BACKEND_URL",
        "https://mahossain432-gmail-com-officeflow.preview.emergentagent.com",
    ).rstrip("/")

    def test_public_health(self):
        r = requests.get(f"{self.PUBLIC_URL}/api/health", timeout=15)
        # If preview is asleep this will not be 200; we assert 200 to flag it.
        assert r.status_code == 200, (
            f"Public preview /api/health -> {r.status_code}. "
            f"Preview ingress not routing to backend."
        )
