from enum import StrEnum


class SessionStatus(StrEnum):
    ACTIVE = "active"
    WAITING_INPUT = "waiting_input"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    FAILED = "failed"

