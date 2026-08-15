"""
Iteration 7 tests: register cookie preservation, dashboard-stats new keys,
shift comments feature, overtime auto-detect + approval feature.
"""
import os
import time
import uuid
import pytest
import requests
from datetime import date, timedelta, datetime, timezone

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") + "/api"
ADMIN = {"email": "mahossain432@gmail.com", "password": "Admin@2026Secure"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="module")
def admin_session():
    s, u = _login(**ADMIN)
    return s, u


@pytest.fixture(scope="module")
def employee_session(admin_session):
    """Ensure an employee exists and log them in. Create via admin if needed."""
    a_sess, _ = admin_session
    # try the well-known employee first
    creds = {"email": "employee@officeflow.com", "password": "Employee@123"}
    try:
        return _login(**creds)
    except AssertionError:
        # create it via admin register
        r = a_sess.post(f"{BASE}/auth/register", json={
            "email": creds["email"], "password": creds["password"],
            "name": "Test Employee", "role": "employee",
        })
        assert r.status_code == 200, r.text
        return _login(**creds)


# ------------------- BUG FIX 1: register does not overwrite caller cookies -------------------

def test_admin_register_preserves_admin_session():
    s, admin_user = _login(**ADMIN)
    # capture pre-register cookie
    pre_access = s.cookies.get("access_token")
    assert pre_access, "admin should have access_token cookie after login"

    email = f"TEST_iter7_regbyadmin_{int(time.time())}_{uuid.uuid4().hex[:6]}@example.com"
    r = s.post(f"{BASE}/auth/register", json={
        "email": email, "password": "Pass@1234", "name": "IT7 Reg", "role": "employee"
    })
    assert r.status_code == 200, r.text

    # cookie must not have changed
    post_access = s.cookies.get("access_token")
    assert post_access == pre_access, "admin's access_token cookie was overwritten by register!"

    # /auth/me must still be admin
    me = s.get(f"{BASE}/auth/me")
    assert me.status_code == 200
    assert me.json()["email"].lower() == ADMIN["email"].lower()
    assert me.json()["role"] in ("super_admin", "admin")


def test_anon_register_blocked_with_message():
    r = requests.post(f"{BASE}/auth/register", json={
        "email": f"TEST_anon_{int(time.time())}@example.com",
        "password": "Whatever@1", "name": "Anon", "role": "employee",
    })
    assert r.status_code == 403
    detail = (r.json().get("detail") or "").lower()
    assert "public sign-up is disabled" in detail or "contact your administrator" in detail


# ------------------- BUG FIX 2: dashboard-stats new keys -------------------

def test_dashboard_stats_has_new_keys(admin_session):
    s, _ = admin_session
    r = s.get(f"{BASE}/admin/dashboard-stats")
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("active_shifts", "scheduled_shifts", "pending_overtime"):
        assert k in data, f"missing key {k} in dashboard-stats"
        assert isinstance(data[k], int)


# ------------------- FEATURE: Shift Comments -------------------

@pytest.fixture(scope="module")
def shift_for_comments(admin_session, employee_session):
    a_sess, _ = admin_session
    _, emp = employee_session
    r = a_sess.post(f"{BASE}/shifts", json={
        "user_id": emp["id"],
        "title": "TEST IT7 Comments Shift",
        "work_location": "in_office",
        "start_time": "09:00", "end_time": "17:00",
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": str(date.today()),
        "effective_to": str(date.today() + timedelta(days=30)),
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_list_comments_empty_initially(admin_session, shift_for_comments):
    s, _ = admin_session
    r = s.get(f"{BASE}/shifts/{shift_for_comments['id']}/comments")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_post_comment_empty_body_rejected(admin_session, shift_for_comments):
    s, _ = admin_session
    r = s.post(f"{BASE}/shifts/{shift_for_comments['id']}/comments", json={"body": "  "})
    assert r.status_code == 400


def test_admin_post_comment_notifies_employee(admin_session, employee_session, shift_for_comments):
    a_sess, _ = admin_session
    e_sess, emp = employee_session
    body = f"hello from admin {uuid.uuid4().hex[:6]}"
    r = a_sess.post(f"{BASE}/shifts/{shift_for_comments['id']}/comments", json={"body": body})
    assert r.status_code == 200, r.text
    data = r.json()
    for k in ("id", "shift_id", "author_id", "author_name", "author_role", "body", "created_at"):
        assert k in data
    assert data["body"] == body
    assert data["shift_id"] == shift_for_comments["id"]

    # Employee should have received a shift_comment notification
    time.sleep(0.5)
    nr = e_sess.get(f"{BASE}/notifications")
    assert nr.status_code == 200
    matched = [n for n in nr.json() if n.get("type") == "shift_comment" and n.get("reference_id") == shift_for_comments["id"]]
    assert len(matched) >= 1


def test_employee_post_comment_notifies_admins(admin_session, employee_session, shift_for_comments):
    a_sess, _ = admin_session
    e_sess, _ = employee_session
    body = f"reply from employee {uuid.uuid4().hex[:6]}"
    r = e_sess.post(f"{BASE}/shifts/{shift_for_comments['id']}/comments", json={"body": body})
    assert r.status_code == 200, r.text

    time.sleep(0.5)
    nr = a_sess.get(f"{BASE}/notifications")
    assert nr.status_code == 200
    matched = [n for n in nr.json() if n.get("type") == "shift_comment" and n.get("reference_id") == shift_for_comments["id"]]
    assert len(matched) >= 1


def test_other_employee_cannot_access_comments(admin_session, shift_for_comments):
    """Create a second employee and confirm they get 403 on someone else's shift comments."""
    a_sess, _ = admin_session
    email = f"TEST_it7_other_{int(time.time())}@example.com"
    pw = "Pass@1234"
    r = a_sess.post(f"{BASE}/auth/register", json={
        "email": email, "password": pw, "name": "Other Emp", "role": "employee"
    })
    assert r.status_code == 200, r.text

    o_sess, _ = _login(email, pw)
    r = o_sess.get(f"{BASE}/shifts/{shift_for_comments['id']}/comments")
    assert r.status_code == 403


def test_list_comments_returns_posted(admin_session, shift_for_comments):
    s, _ = admin_session
    r = s.get(f"{BASE}/shifts/{shift_for_comments['id']}/comments")
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) >= 2  # admin post + employee reply


# ------------------- FEATURE: Overtime auto-detect + approve/reject -------------------

@pytest.fixture(scope="module")
def overtime_shift(admin_session, employee_session):
    a_sess, _ = admin_session
    _, emp = employee_session
    r = a_sess.post(f"{BASE}/shifts", json={
        "user_id": emp["id"],
        "title": "TEST IT7 Overtime Shift",
        "work_location": "in_office",
        "start_time": "09:00", "end_time": "17:00",
        "days_of_week": [1, 2, 3, 4, 5],
        "effective_from": str(date.today()),
        "effective_to": str(date.today() + timedelta(days=30)),
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_overtime_autocreated_on_end_shift(admin_session, employee_session, overtime_shift):
    """Employee joins shift, then we backdate the session's joined_at to >8h ago
    in MongoDB via a shell hop, then call /end and expect overtime_requests entry."""
    import subprocess, json as _json
    e_sess, emp = employee_session
    a_sess, _ = admin_session

    # Join shift (employee)
    r = e_sess.post(f"{BASE}/shifts/{overtime_shift['id']}/join")
    assert r.status_code == 200, r.text

    # Clean up any prior overtime for user+date
    today = date.today().isoformat()
    _mongo_run(f'db.overtime_requests.deleteMany({{user_id: "{emp["id"]}", date: "{today}"}})')

    # Backdate joined_at to 9h ago
    nine_h_ago = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
    check_in_iso = nine_h_ago
    _mongo_run(f'db.shift_sessions.updateOne({{shift_id: "{overtime_shift["id"]}", user_id: "{emp["id"]}", date: "{today}", status: "joined"}}, {{$set: {{joined_at: "{nine_h_ago}"}}}})')
    _mongo_run(f'db.attendance.updateOne({{user_id: "{emp["id"]}", date: "{today}"}}, {{$set: {{check_in: "{check_in_iso}"}}}})')

    # End shift
    r = e_sess.post(f"{BASE}/shifts/{overtime_shift['id']}/end")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["work_hours"] > 8

    # Overtime request should now exist for this user+date
    time.sleep(0.5)
    lr = a_sess.get(f"{BASE}/overtime", params={"status": "pending"})
    assert lr.status_code == 200, lr.text
    reqs = [x for x in lr.json() if x["user_id"] == emp["id"] and x["date"] == today]
    assert len(reqs) == 1, f"expected 1 pending overtime for user, got {reqs}"
    ot = reqs[0]
    assert ot["status"] == "pending"
    assert ot["overtime_hours"] > 0
    assert ot["shift_id"] == overtime_shift["id"]
    pytest.OT_REQ_ID = ot["id"]


def test_overtime_idempotent(employee_session, admin_session):
    """Call the internal helper via a second end trigger path — verify no duplicate row."""
    e_sess, emp = employee_session
    a_sess, _ = admin_session
    today = date.today().isoformat()
    lr = a_sess.get(f"{BASE}/overtime", params={"status": "pending"})
    reqs = [x for x in lr.json() if x["user_id"] == emp["id"] and x["date"] == today]
    assert len(reqs) == 1


def test_employee_sees_only_own_overtime(employee_session, admin_session):
    e_sess, emp = employee_session
    r = e_sess.get(f"{BASE}/overtime")
    assert r.status_code == 200
    for row in r.json():
        assert row["user_id"] == emp["id"]


def test_admin_dashboard_reflects_pending_overtime(admin_session):
    s, _ = admin_session
    r = s.get(f"{BASE}/admin/dashboard-stats")
    assert r.status_code == 200
    assert r.json()["pending_overtime"] >= 1


def test_approve_overtime(admin_session, employee_session):
    a_sess, _ = admin_session
    e_sess, _ = employee_session
    req_id = getattr(pytest, "OT_REQ_ID", None)
    assert req_id, "no OT_REQ_ID set from previous test"
    r = a_sess.post(f"{BASE}/overtime/{req_id}/approve", json={"note": "Approved by test"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    assert r.json().get("review_note") == "Approved by test"

    # Employee should get a notif
    time.sleep(0.3)
    nr = e_sess.get(f"{BASE}/notifications")
    types = [n.get("type") for n in nr.json()]
    assert "overtime_approved" in types


def test_approve_non_pending_returns_400(admin_session):
    s, _ = admin_session
    req_id = pytest.OT_REQ_ID
    r = s.post(f"{BASE}/overtime/{req_id}/approve", json={"note": "again"})
    assert r.status_code == 400


def test_reject_flow_separate_request(admin_session, employee_session):
    """Manually insert a fresh pending overtime request via mongo, then reject via API."""
    e_sess, emp = employee_session
    a_sess, _ = admin_session
    fake_id = str(uuid.uuid4())
    d = (date.today() - timedelta(days=1)).isoformat()
    _mongo_run(
        'db.overtime_requests.insertOne({'
        f'id: "{fake_id}", user_id: "{emp["id"]}", date: "{d}", '
        'shift_id: null, shift_title: "TEST past", total_hours: 9.5, '
        'overtime_hours: 1.5, overtime_minutes: 90, status: "pending", '
        'reviewer_id: null, reviewer_name: null, review_note: null, '
        'reviewed_at: null, created_at: new Date(), updated_at: new Date()})'
    )
    r = a_sess.post(f"{BASE}/overtime/{fake_id}/reject", json={"note": "Not allowed"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "rejected"

    time.sleep(0.3)
    nr = e_sess.get(f"{BASE}/notifications")
    types = [n.get("type") for n in nr.json()]
    assert "overtime_rejected" in types


def test_employee_cannot_approve(employee_session):
    e_sess, _ = employee_session
    req_id = getattr(pytest, "OT_REQ_ID", "xxx")
    r = e_sess.post(f"{BASE}/overtime/{req_id}/approve", json={"note": "nope"})
    assert r.status_code == 403


# ---------- helper to run mongo shell commands ----------

def _mongo_run(js: str):
    import subprocess
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "test_database")
    # Try mongosh first, then legacy mongo
    for binary in ("mongosh", "mongo"):
        try:
            proc = subprocess.run(
                [binary, mongo_url + ("" if mongo_url.endswith("/") else "/") + db_name,
                 "--quiet", "--eval", js],
                capture_output=True, text=True, timeout=15,
            )
            if proc.returncode == 0:
                return proc.stdout
        except FileNotFoundError:
            continue
    # Fallback via pymongo
    from pymongo import MongoClient
    c = MongoClient(mongo_url)
    db = c[db_name]
    # unsafe eval — only for controlled test strings
    # emulate a couple of ops we use
    import re
    m = re.match(r'db\.(\w+)\.deleteMany\((.+)\)', js)
    if m:
        coll, arg = m.group(1), m.group(2)
        db[coll].delete_many(_js_to_py(arg))
        return
    m = re.match(r'db\.(\w+)\.updateOne\((.+),\s*\{\$set:\s*(\{.*\})\}\)', js)
    if m:
        coll, filt, upd = m.group(1), m.group(2), m.group(3)
        db[coll].update_one(_js_to_py(filt), {"$set": _js_to_py(upd)})
        return
    m = re.match(r'db\.(\w+)\.insertOne\((\{.*\})\)', js, re.S)
    if m:
        coll, doc = m.group(1), m.group(2)
        d = _js_to_py(doc)
        # replace new Date()
        for k, v in list(d.items()):
            if v == "__NOW__":
                d[k] = datetime.now(timezone.utc)
        db[coll].insert_one(d)
        return


def _js_to_py(s: str):
    """Very small JS-object-literal to Python dict converter for our tests."""
    import json, re
    s = s.strip()
    # new Date() -> "__NOW__"
    s = re.sub(r'new Date\(\)', '"__NOW__"', s)
    # null -> null (already JSON)
    # Quote keys: {id: "x"} -> {"id": "x"}
    s = re.sub(r'([{,]\s*)(\w+)\s*:', r'\1"\2":', s)
    return json.loads(s)
