from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from devatlas.infrastructure.models.base import Base

if TYPE_CHECKING:
    from devatlas.infrastructure.models.identity import User, Workspace


class Conversation(Base):
    """A private, workspace-scoped conversation owned by one local user."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", name="uq_conversations_workspace_id_id"),
        CheckConstraint(
            "char_length(btrim(title)) > 0",
            name="ck_conversations_title_not_empty",
        ),
        Index(
            "ix_conversations_owner_updated", "workspace_id", "user_id", "updated_at"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    workspace: Mapped["Workspace"] = relationship()
    user: Mapped["User"] = relationship()
    turns: Mapped[list["ConversationTurnModel"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ConversationTurnModel(Base):
    """An immutable question/answer snapshot with citation provenance."""

    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "ordinal", name="uq_conversation_turns_ordinal"
        ),
        ForeignKeyConstraint(
            ["workspace_id", "conversation_id"],
            ["conversations.workspace_id", "conversations.id"],
            ondelete="CASCADE",
            name="fk_conversation_turns_workspace_conversation",
        ),
        CheckConstraint(
            "ordinal >= 0", name="ck_conversation_turns_ordinal_nonnegative"
        ),
        CheckConstraint(
            "char_length(btrim(question)) > 0",
            name="ck_conversation_turns_question_not_empty",
        ),
        CheckConstraint(
            "char_length(btrim(standalone_question)) > 0",
            name="ck_conversation_turns_standalone_question_not_empty",
        ),
        CheckConstraint(
            "char_length(btrim(answer)) > 0",
            name="ck_conversation_turns_answer_not_empty",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    conversation_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    standalone_question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    has_sufficient_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    conversation: Mapped[Conversation] = relationship(back_populates="turns")
