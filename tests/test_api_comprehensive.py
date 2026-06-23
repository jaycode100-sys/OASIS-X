"""Comprehensive API endpoint tests for OASIS-X."""

import pytest
from httpx import AsyncClient, ASGITransport
from api.app import app


@pytest.fixture
async def cli():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def admin_token(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
async def user_token(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture
def auth_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_h(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ── Public endpoints ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_status(cli):
    r = await cli.get("/api/status")
    assert r.status_code == 200
    d = r.json()
    assert d["system"] == "running"
    assert d["service"] == "SWIFT FHS"
    assert "supported_cities" in d
    assert "Lagos" in d["supported_cities"]
    assert "current_season" in d


@pytest.mark.asyncio
async def test_llm_status(cli):
    r = await cli.get("/api/llm-status")
    assert r.status_code == 200
    d = r.json()
    assert "available" in d
    assert "model" in d


@pytest.mark.asyncio
async def test_login_page(cli):
    r = await cli.get("/login")
    assert r.status_code == 200
    assert "OASIS-X" in r.text


@pytest.mark.asyncio
async def test_docs_page(cli):
    r = await cli.get("/docs")
    assert r.status_code == 200


# ── Auth endpoints ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_valid(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    d = r.json()
    assert "access_token" in d
    assert d["token_type"] == "bearer"
    assert d["username"] == "admin"
    assert d["role"] == "superadmin"


@pytest.mark.asyncio
async def test_login_invalid_password(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_invalid_user(cli):
    r = await cli.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_missing_fields(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_me_authenticated(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    d = r.json()
    assert d["username"] == "admin"
    assert d["role"] == "superadmin"
    assert "profile" in d


@pytest.mark.asyncio
async def test_me_unauthorized(cli):
    r = await cli.get("/api/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_bad_token(cli):
    r = await cli.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_superadmin(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.post("/api/auth/register",
        json={"username": "newuser", "password": "newpass", "role": "user"},
        headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json()["username"] == "newuser"


@pytest.mark.asyncio
async def test_register_duplicate(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.post("/api/auth/register",
        json={"username": "admin", "password": "x"},
        headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_register_forbidden_for_user(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    t = r.json()["access_token"]
    r = await cli.post("/api/auth/register",
        json={"username": "another", "password": "x"},
        headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_users(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.get("/api/auth/users", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert "users" in r.json()
    assert len(r.json()["users"]) >= 2


@pytest.mark.asyncio
async def test_list_users_forbidden(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    t = r.json()["access_token"]
    r = await cli.get("/api/auth/users", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_delete_user(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.get("/api/auth/users", headers={"Authorization": f"Bearer {t}"})
    target = [u for u in r.json()["users"] if u["username"] == "user"][0]
    r = await cli.delete(f"/api/auth/users/{target['id']}", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200
    assert r.json()["deleted"] is True


@pytest.mark.asyncio
async def test_delete_self_blocked(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.get("/api/auth/users", headers={"Authorization": f"Bearer {t}"})
    admin_user = [u for u in r.json()["users"] if u["username"] == "admin"][0]
    r = await cli.delete(f"/api/auth/users/{admin_user['id']}", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_nonexistent(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    r = await cli.delete("/api/auth/users/99999", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 404


# ── Pipeline endpoints ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_pipeline(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/run?city=Lagos&n=200", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert "summary" in d
    assert "rows" in d
    assert len(d["rows"]) <= 15
    s = d["summary"]
    assert s["city"] == "Lagos"
    assert s["total_records"] == 200
    assert "state_distribution" in s
    assert "ncc_compliance" in s


@pytest.mark.asyncio
async def test_run_pipeline_all_cities(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    for city in ["Lagos", "Abuja", "PortHarcourt", "Kano"]:
        r = await cli.get(f"/api/run?city={city}&n=100", headers=h)
        assert r.status_code == 200, f"{city} failed: {r.text}"
        assert r.json()["summary"]["city"] == city


@pytest.mark.asyncio
async def test_run_pipeline_no_drift(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/run?city=Lagos&n=100&apply_ncc_drift=false", headers=h)
    assert r.status_code == 200
    assert r.json()["summary"]["ncc_drift_applied"] is False


@pytest.mark.asyncio
async def test_run_pipeline_unauthorized(cli):
    r = await cli.get("/api/run?city=Lagos")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_run_pipeline_different_data_each_time(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r1 = await cli.get("/api/run?city=Lagos&n=200", headers=h)
    r2 = await cli.get("/api/run?city=Lagos&n=200", headers=h)
    rows1 = r1.json()["rows"]
    rows2 = r2.json()["rows"]
    assert rows1 != rows2, "Pipeline returned identical data — seed not varying"


@pytest.mark.asyncio
async def test_run_pipeline_row_shape(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/run?city=Lagos&n=200", headers=h)
    row = r.json()["rows"][0]
    for key in ("time", "osnr_db", "ber", "latency_ms", "state", "recommended_action"):
        assert key in row, f"Missing key: {key}"


# ── Nigerian Context ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_nigerian_context(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/nigerian-context?city=Lagos", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["city"] == "Lagos"
    assert "baselines" in d
    assert "osnr_db" in d["baselines"]
    assert "ncc_thresholds" in d
    assert "risk_factors" in d
    assert "current_season" in d


@pytest.mark.asyncio
async def test_nigerian_context_unauthorized(cli):
    r = await cli.get("/api/nigerian-context?city=Lagos")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_all_city_profiles(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/nigerian-context/all-cities", headers=h)
    assert r.status_code == 200
    d = r.json()
    for city in ("Lagos", "Abuja", "PortHarcourt", "Kano"):
        assert city in d
        assert d[city]["city"] == city


# ── Fault Injection ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_simulate_event(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/simulate/event/fiber_cut?city=Lagos", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["event_injected"] == "fiber_cut"
    assert d["city"] == "Lagos"
    assert "telemetry" in d
    assert "diagnosis" in d


@pytest.mark.asyncio
async def test_simulate_all_events(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    events = ["generator_failure", "fiber_cut", "harmattan_degradation", "rain_attenuation", "peak_congestion"]
    for ev in events:
        r = await cli.get(f"/api/simulate/event/{ev}?city=Abuja", headers=h)
        assert r.status_code == 200, f"{ev} failed: {r.text}"
        assert r.json()["event_injected"] == ev


@pytest.mark.asyncio
async def test_simulate_event_unauthorized(cli):
    r = await cli.get("/api/simulate/event/fiber_cut?city=Lagos")
    assert r.status_code == 401


# ── Diagnosis ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_diagnose_row(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/diagnose/100?city=Lagos", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["row_index"] == 100
    assert d["city"] == "Lagos"
    assert "telemetry" in d


@pytest.mark.asyncio
async def test_diagnose_out_of_range(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/diagnose/9999?city=Lagos", headers=h)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_diagnose_unauthorized(cli):
    r = await cli.get("/api/diagnose/100?city=Lagos")
    assert r.status_code == 401


# ── Summarize ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_summarize(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/summarize",
        json={"summary": {"osnr_avg": 22, "ber_avg": 1e-5}, "ncc": {"status": "compliant"}},
        headers=h)
    assert r.status_code == 200
    d = r.json()
    assert "source" in d


@pytest.mark.asyncio
async def test_summarize_unauthorized(cli):
    r = await cli.post("/api/summarize", json={"summary": {}})
    assert r.status_code == 401


# ── Pipeline Logs ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_list_logs(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/logs",
        json={"city": "Lagos", "n": 100, "rows": [{"osnr_db": 25}], "summary": {"ok": True}},
        headers=h)
    assert r.status_code == 200
    r = await cli.get("/api/logs", headers=h)
    assert r.status_code == 200
    assert len(r.json()["runs"]) >= 1


@pytest.mark.asyncio
async def test_get_log_by_id(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/logs",
        json={"city": "Lagos", "n": 50, "rows": [{"osnr_db": 22}], "summary": {"ok": True}},
        headers=h)
    run_id = r.json()["run_id"]
    r = await cli.get(f"/api/logs/{run_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == run_id


@pytest.mark.asyncio
async def test_get_log_not_found(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/logs/99999", headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_log(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/logs",
        json={"city": "Kano", "n": 75, "rows": [], "summary": {}},
        headers=h)
    run_id = r.json()["run_id"]
    r = await cli.delete(f"/api/logs/{run_id}", headers=h)
    assert r.status_code == 200
    assert r.json()["deleted"] is True
    r = await cli.get(f"/api/logs/{run_id}", headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_logs_unauthorized(cli):
    r = await cli.get("/api/logs")
    assert r.status_code == 401


# ── Chat ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_history(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/chat/history", headers=h)
    assert r.status_code == 200
    assert "messages" in r.json()


@pytest.mark.asyncio
async def test_clear_chat(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.delete("/api/chat/history", headers=h)
    assert r.status_code == 200
    assert r.json()["cleared"] is True


@pytest.mark.asyncio
async def test_chat_history_unauthorized(cli):
    r = await cli.get("/api/chat/history")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_chat_technical(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/chat",
        json={"message": "Hello", "mode": "technical"},
        headers=h)
    assert r.status_code == 200
    d = r.json()
    assert "reply" in d
    assert "source" in d


@pytest.mark.asyncio
async def test_chat_simple(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/chat",
        json={"message": "Hello", "mode": "simple"},
        headers=h)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_chat_unauthorized(cli):
    r = await cli.post("/api/chat", json={"message": "Hi", "mode": "technical"})
    assert r.status_code == 401


# ── Profile ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_profile(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/profile", headers=h)
    assert r.status_code == 200
    assert "profile" in r.json()


@pytest.mark.asyncio
async def test_get_profile_unauthorized(cli):
    r = await cli.get("/api/profile")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_update_profile(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.put("/api/profile",
        json={"display_name": "Test Admin", "theme": "light"},
        headers=h)
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["display_name"] == "Test Admin"
    assert p["theme"] == "light"


@pytest.mark.asyncio
async def test_update_profile_settings(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.put("/api/profile",
        json={"settings": {"notifications": True}},
        headers=h)
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["settings"]["notifications"] is True


# ── Complaints ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_complaint(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/complaints",
        json={"subject": "Network issue"},
        headers=h)
    assert r.status_code == 200
    d = r.json()["complaint"]
    assert d["subject"] == "Network issue"
    assert d["status"] == "open"


@pytest.mark.asyncio
async def test_list_complaints_superadmin(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/complaints", json={"subject": "Test 1"}, headers=h)
    r = await cli.get("/api/complaints", headers=h)
    assert r.status_code == 200
    assert "complaints" in r.json()
    # Superadmin sees only open complaints by default
    for c in r.json()["complaints"]:
        assert c["status"] == "open"


@pytest.mark.asyncio
async def test_list_complaints_user_own_only(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    ut = r.json()["access_token"]
    uh = {"Authorization": f"Bearer {ut}"}
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    at = r.json()["access_token"]
    ah = {"Authorization": f"Bearer {at}"}
    r = await cli.get("/api/auth/me", headers=uh)
    uid = r.json()["id"]
    await cli.post("/api/complaints", json={"subject": "Admin issue"}, headers=ah)
    await cli.post("/api/complaints", json={"subject": "User issue"}, headers=uh)
    r = await cli.get("/api/complaints", headers=uh)
    assert r.status_code == 200
    # User should see only their own complaint
    for c in r.json()["complaints"]:
        assert c["user_id"] == uid


@pytest.mark.asyncio
async def test_create_and_message_complaint(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    ut = r.json()["access_token"]
    uh = {"Authorization": f"Bearer {ut}"}
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    at = r.json()["access_token"]
    ah = {"Authorization": f"Bearer {at}"}
    r = await cli.post("/api/complaints",
        json={"subject": "Fault in Lagos"},
        headers=uh)
    cid = r.json()["complaint"]["id"]
    r = await cli.post(f"/api/complaints/{cid}/messages",
        json={"message": "Please help"},
        headers=uh)
    assert r.status_code == 200
    r = await cli.get(f"/api/complaints/{cid}/messages", headers=ah)
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) >= 1
    assert msgs[-1]["message"] == "Please help"


@pytest.mark.asyncio
async def test_close_complaint(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/complaints",
        json={"subject": "Resolved issue"},
        headers=h)
    cid = r.json()["complaint"]["id"]
    r = await cli.post(f"/api/complaints/{cid}/close", headers=h)
    assert r.status_code == 200
    assert r.json()["complaint"]["status"] == "closed"


@pytest.mark.asyncio
async def test_complaint_other_user_messages_forbidden(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    ut = r.json()["access_token"]
    uh = {"Authorization": f"Bearer {ut}"}
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    at = r.json()["access_token"]
    ah = {"Authorization": f"Bearer {at}"}
    # Admin creates a complaint
    r = await cli.post("/api/complaints", json={"subject": "Admin issue"}, headers=ah)
    cid = r.json()["complaint"]["id"]
    # Regular user tries to read messages
    r = await cli.get(f"/api/complaints/{cid}/messages", headers=uh)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_complaint_other_user_close_forbidden(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    ut = r.json()["access_token"]
    uh = {"Authorization": f"Bearer {ut}"}
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    at = r.json()["access_token"]
    ah = {"Authorization": f"Bearer {at}"}
    r = await cli.post("/api/complaints", json={"subject": "Admin issue"}, headers=ah)
    cid = r.json()["complaint"]["id"]
    # Regular user tries to close
    r = await cli.post(f"/api/complaints/{cid}/close", headers=uh)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_complaint_other_user_post_forbidden(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    ut = r.json()["access_token"]
    uh = {"Authorization": f"Bearer {ut}"}
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    at = r.json()["access_token"]
    ah = {"Authorization": f"Bearer {at}"}
    r = await cli.post("/api/complaints", json={"subject": "Admin issue"}, headers=ah)
    cid = r.json()["complaint"]["id"]
    r = await cli.post(f"/api/complaints/{cid}/messages",
        json={"message": "spam"}, headers=uh)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_complaint_unauthorized(cli):
    r = await cli.get("/api/complaints")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_complaint_not_found(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/complaints/99999/messages", headers=h)
    assert r.status_code == 404
    r = await cli.post("/api/complaints/99999/close", headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_complaint_closed_status_filter(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/complaints", json={"subject": "Will close"}, headers=h)
    cid = r.json()["complaint"]["id"]
    await cli.post(f"/api/complaints/{cid}/close", headers=h)
    r = await cli.get("/api/complaints?status=closed", headers=h)
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()["complaints"]]
    assert cid in ids


@pytest.mark.asyncio
async def test_complaints_unauthorized(cli):
    r = await cli.get("/api/complaints")
    assert r.status_code == 401


# ── Activity Log ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_log_activity(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.post("/api/activity",
        json={"type": "test", "message": "Test activity"},
        headers=h)
    assert r.status_code == 200
    assert r.json()["logged"] is True


@pytest.mark.asyncio
async def test_list_activities_superadmin(cli):
    r = await cli.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/activity", headers=h)
    assert r.status_code == 200
    assert "activities" in r.json()


@pytest.mark.asyncio
async def test_list_activities_user_own(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/activity?own=true", headers=h)
    assert r.status_code == 200
    assert "activities" in r.json()


@pytest.mark.asyncio
async def test_list_activities_user_all_forbidden(cli):
    r = await cli.post("/api/auth/login", json={"username": "user", "password": "user123"})
    t = r.json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await cli.get("/api/activity", headers=h)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_activity_unauthorized(cli):
    r = await cli.get("/api/activity")
    assert r.status_code == 401
