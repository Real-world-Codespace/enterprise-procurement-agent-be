from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .config import POLICY_VERSION
from .models import AuditEvent, PurchaseRequest, Quote, RequestStatus, Role, User
from .schemas import AuditOut, RequestOut

BUDGETS = {"PRODUCT": 420_000_000, "ENGINEERING": 650_000_000, "HR": 180_000_000}
APPROVED_CATEGORIES = {"laptop", "monitor", "software", "saas", "office equipment", "thiết bị văn phòng"}


def audit(db: Session, request: PurchaseRequest, actor: User | None, event_type: str, message: str):
    db.add(AuditEvent(request_id=request.id, actor_id=actor.id if actor else None, event_type=event_type, message=message))


def reference() -> str:
    return f"PRQ-{datetime.utcnow():%Y%m%d}-{uuid4().hex[:5].upper()}"


def request_query():
    return select(PurchaseRequest).options(joinedload(PurchaseRequest.requester), joinedload(PurchaseRequest.quotes))


def to_request_out(item: PurchaseRequest) -> RequestOut:
    return RequestOut(
        id=item.id, reference=item.reference, title=item.title, category=item.category, quantity=item.quantity,
        estimated_amount=item.estimated_amount, currency=item.currency, cost_center=item.cost_center,
        business_justification=item.business_justification, status=item.status, policy_result=item.policy_result,
        budget_available=item.budget_available, pr_number=item.pr_number, requester_name=item.requester.name,
        created_at=item.created_at, quotes=item.quotes,
    )


def visible_request(db: Session, request_id: int, user: User) -> PurchaseRequest:
    item = db.execute(request_query().where(PurchaseRequest.id == request_id)).unique().scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    if user.role == Role.REQUESTER and item.requester_id != user.id:
        raise HTTPException(status_code=403, detail="You can only access your own requests")
    return item


def run_policy_check(db: Session, item: PurchaseRequest, actor: User) -> PurchaseRequest:
    normalized = item.category.strip().lower()
    available = BUDGETS.get(item.cost_center.upper(), 0)
    category_ok = normalized in APPROVED_CATEGORIES
    budget_ok = item.estimated_amount <= available
    item.budget_available = available
    if category_ok and budget_ok:
        item.status = RequestStatus.SOURCING
        item.policy_result = f"PASS: Policy {POLICY_VERSION}; category approved; budget available {available:,.0f} VND."
        audit(db, item, actor, "policy_passed", "Policy and budget checks passed. Workflow moved to sourcing.")
    else:
        item.status = RequestStatus.NEEDS_INFO
        causes = []
        if not category_ok: causes.append("category requires policy exception")
        if not budget_ok: causes.append("estimated amount exceeds available budget")
        item.policy_result = f"NEEDS_INFO: {'; '.join(causes)}."
        audit(db, item, actor, "policy_blocked", item.policy_result)
    return item


def generate_quotes(db: Session, item: PurchaseRequest, actor: User) -> list[Quote]:
    if item.status != RequestStatus.SOURCING:
        raise HTTPException(status_code=409, detail="Request must pass policy review before sourcing")
    if item.quotes:
        return item.quotes
    factor = max(item.quantity / 12, 0.4)
    templates = [
        ("Nexa Office", 282_000_000, 7, 36, "approved", 92),
        ("Aurora Tech", 276_000_000, 14, 24, "approved", 86),
        ("Delta Systems", 264_000_000, 21, 12, "review_required", 71),
    ]
    quotes = [Quote(request_id=item.id, vendor_name=name, total_amount=round(amount * factor), delivery_days=days,
                    warranty_months=warranty, compliance_status=compliance, score=score)
              for name, amount, days, warranty, compliance, score in templates]
    db.add_all(quotes)
    audit(db, item, actor, "rfq_completed", "RFQ completed for Nexa Office, Aurora Tech and Delta Systems. Three quotes normalized.")
    db.flush()
    return quotes


def select_quote(db: Session, item: PurchaseRequest, quote_id: int, actor: User) -> PurchaseRequest:
    if item.status != RequestStatus.SOURCING:
        raise HTTPException(status_code=409, detail="Request is not ready for quote selection")
    quote = next((q for q in item.quotes if q.id == quote_id), None)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote does not belong to this request")
    if quote.compliance_status != "approved":
        raise HTTPException(status_code=409, detail="Selected vendor requires compliance review")
    for candidate in item.quotes: candidate.is_selected = candidate.id == quote.id
    item.selected_quote_id = quote.id
    item.status = RequestStatus.PENDING_APPROVAL
    audit(db, item, actor, "quote_selected", f"{quote.vendor_name} selected with score {quote.score:.0f}/100. Sent for approval.")
    return item


def decision(db: Session, item: PurchaseRequest, approved: bool, comment: str, actor: User) -> PurchaseRequest:
    if item.status != RequestStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Request is not pending approval")
    if approved:
        item.status = RequestStatus.PR_CREATED
        item.pr_number = f"PR-{datetime.utcnow():%Y}-{uuid4().hex[:6].upper()}"
        audit(db, item, actor, "approved", f"Approved. {item.pr_number} created in ERP simulation. Comment: {comment}")
    else:
        item.status = RequestStatus.REJECTED
        audit(db, item, actor, "rejected", f"Rejected by approver. Comment: {comment}")
    return item


def audit_out(db: Session, item: PurchaseRequest) -> list[AuditOut]:
    events = db.execute(select(AuditEvent).options(joinedload(AuditEvent.actor)).where(AuditEvent.request_id == item.id).order_by(AuditEvent.created_at.desc())).scalars().all()
    return [AuditOut(id=e.id, event_type=e.event_type, message=e.message, created_at=e.created_at, actor_name=e.actor.name if e.actor else "System") for e in events]
