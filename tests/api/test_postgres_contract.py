from types import SimpleNamespace

import httpx
import pytest

from guanchen_v2.api.app import create_app
from guanchen_v2.api.service import ChatApplicationService
from guanchen_v2.memory.implementations.postgres import PostgresMemoryStore
from guanchen_v2.memory.selector import MemorySelector
from guanchen_v2.safety.rules import SafetyRuleEngine
from guanchen_v2.safety.service import SafetyService


@pytest.mark.integration
async def test_profile_and_credential_persist_across_api_instances(postgres_session_factory):
    store = PostgresMemoryStore(postgres_session_factory)
    memory = MemorySelector(postgres_session_factory)
    runtime = SimpleNamespace(load_session_state=store.load, metrics=None)

    def app():
        return create_app(ChatApplicationService(runtime, SafetyService(SafetyRuleEngine()), store=store, memory=memory), session_store=store)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()), base_url="http://test") as client:
        created = (await client.post("/api/v1/sessions")).json()
        sid = created["session_id"]
        headers = {"Authorization": "Bearer " + created["session_token"]}
        partial = await client.patch("/api/v1/profile", headers=headers, json={"session_id": sid, "birth_profile": {"year": 1992}})
        assert partial.status_code == 200 and partial.json()["birth_profile"] is None
        rest = {"month": 8, "day": 18, "hour": 10, "minute": 0, "gender": "male"}
        full = await client.patch("/api/v1/profile", headers=headers, json={"session_id": sid, "birth_profile": rest})
        assert full.status_code == 200 and full.json()["birth_profile"]["year"] == 1992
        bad = await client.patch("/api/v1/profile", headers=headers, json={"session_id": sid, "birth_profile": {"month": 2, "day": 30}})
        assert bad.status_code == 422

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()), base_url="http://test") as client:
        restored = await client.get(f"/api/v1/sessions/{sid}/profile", headers=headers)
        assert restored.status_code == 200
        assert restored.json()["birth_profile"]["month"] == 8
        assert (await client.get(f"/api/v1/sessions/{sid}/profile")).status_code == 401
        state = await store.load(sid)
        assert created["session_token"] not in state.model_dump_json()
