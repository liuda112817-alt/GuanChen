"""Anonymous capability credentials persisted as hashes, independent of HTTP."""

import hashlib
import secrets
import uuid

from guanchen_v2.api.contracts import SessionResponse
from guanchen_v2.api.errors import APIApplicationError
from guanchen_v2.core.session.models import ConversationState


class SessionAccess:
    def __init__(self, store):
        self.store = store

    async def create(self) -> SessionResponse:
        token = secrets.token_urlsafe(32)
        state = ConversationState(session_id=str(uuid.uuid4()))
        state.metadata.extra["access_hash"] = hashlib.sha256(token.encode()).hexdigest()
        await self.store.save(state)
        return SessionResponse(session_id=state.session_id, session_token=token)

    async def authorize(self, session_id: str, authorization: str | None) -> None:
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else ""
        state = await self.store.load(session_id) if token else None
        expected = state.metadata.extra.get("access_hash", "") if state else ""
        if not expected or not secrets.compare_digest(expected, hashlib.sha256(token.encode()).hexdigest()):
            raise APIApplicationError("SESSION_ACCESS_DENIED", "会话凭证无效。", None, 401)
