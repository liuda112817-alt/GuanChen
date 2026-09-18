from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)


class MemoryBase(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 会话状态（Application 层恢复容器）
# ---------------------------------------------------------------------------


class ConversationStateRecord(MemoryBase):

    __tablename__ = "conversation_states"

    session_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    state_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


# ---------------------------------------------------------------------------
# Stage 8 长期用户资料（Long-term Memory）
# 只保存“用户明确提供 / 确认”的结构化资料。
# ---------------------------------------------------------------------------


class UserProfileRow(MemoryBase):
    """用户主体。v2.0 采用匿名 session 身份，user_id 即会话 / 匿名身份标识。"""

    __tablename__ = "user_profile"

    user_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class BirthProfileRow(MemoryBase):
    """
    用户明确提供的出生资料（唯一有效事实）。

    更正语义（Stage 8）：
    - 每个用户只保留一条“当前有效”出生资料；
    - 后写的明确更正覆盖当前事实（upsert），并刷新 updated_at；
    - v2.0 不做完整版本树。
    """

    __tablename__ = "birth_profile"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            name="uq_birth_profile_user_id",
        ),
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        primary_key=True,
    )

    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)
    minute: Mapped[int] = mapped_column(Integer, nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False)
    birth_place_text: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ConversationRow(MemoryBase):
    """会话主体。conversation_id 即 Application 层 session_id。"""

    __tablename__ = "conversation"

    conversation_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class MessageRow(MemoryBase):
    """会话中的单条消息。"""

    __tablename__ = "message"

    message_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("conversation.conversation_id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_message_conversation_created", "conversation_id", "created_at"),
    )


class DreamRecordRow(MemoryBase):
    """
    解梦域的当前 DreamRecord。

    领域隔离：dream_record 只被 Dream 域读取，不得进入 Bazi / Liuyao 的 memory context。
    """

    __tablename__ = "dream_record"

    record_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    record_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_dream_record_user_updated", "user_id", "updated_at"),
    )


class DecisionRecordRow(MemoryBase):
    """
    六爻决策域的当前 DecisionRecord（含 LangGraph thread_id 引用）。

    领域隔离：decision_record 只被 Liuyao 域读取。
    """

    __tablename__ = "decision_record"

    record_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    thread_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    record_json: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_decision_record_user_updated", "user_id", "updated_at"),
    )
