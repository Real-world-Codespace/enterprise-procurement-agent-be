from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Role(str, Enum):
    REQUESTER = "requester"
    PROCUREMENT = "procurement"
    APPROVER = "approver"


class RequestStatus(str, Enum):
    DRAFT = "draft"
    POLICY_REVIEW = "policy_review"
    SOURCING = "sourcing"
    PENDING_APPROVAL = "pending_approval"
    PR_CREATED = "pr_created"
    REJECTED = "rejected"
    NEEDS_INFO = "needs_info"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(SqlEnum(Role))
    department: Mapped[str] = mapped_column(String(80))


class PurchaseRequest(Base):
    __tablename__ = "purchase_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[int] = mapped_column(Integer)
    estimated_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="VND")
    cost_center: Mapped[str] = mapped_column(String(80))
    business_justification: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(SqlEnum(RequestStatus), default=RequestStatus.DRAFT)
    policy_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_available: Mapped[float | None] = mapped_column(Float, nullable=True)
    pr_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    selected_quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id", use_alter=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    quotes: Mapped[list["Quote"]] = relationship(back_populates="request", foreign_keys="Quote.request_id")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id"))
    vendor_name: Mapped[str] = mapped_column(String(160))
    total_amount: Mapped[float] = mapped_column(Float)
    delivery_days: Mapped[int] = mapped_column(Integer)
    warranty_months: Mapped[int] = mapped_column(Integer)
    compliance_status: Mapped[str] = mapped_column(String(32))
    score: Mapped[float] = mapped_column(Float)
    is_selected: Mapped[bool] = mapped_column(default=False)
    request: Mapped[PurchaseRequest] = relationship(back_populates="quotes", foreign_keys=[request_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("purchase_requests.id"), index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    request: Mapped[PurchaseRequest] = relationship(back_populates="audit_events")
    actor: Mapped[User] = relationship(foreign_keys=[actor_id])
