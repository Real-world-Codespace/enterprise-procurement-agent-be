from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PurchaseRequest, RequestStatus, Role, User
from ..agent import answer_procurement_question
from ..config import OPENAI_MODEL
from ..schemas import AgentMessageInput, AgentResponseOut, AuditOut, CreateRequestInput, DecisionInput, QuoteOut, RequestOut, SelectQuoteInput
from ..security import current_user, require_roles
from ..services import (audit, audit_out, generate_quotes, reference, run_policy_check, select_quote, to_request_out, visible_request, decision)

router = APIRouter(prefix="/requests", tags=["purchase requests"])


@router.get("", response_model=list[RequestOut])
def list_requests(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(PurchaseRequest)
    if user.role == Role.REQUESTER:
        query = query.where(PurchaseRequest.requester_id == user.id)
    items = db.execute(query.order_by(PurchaseRequest.updated_at.desc())).scalars().all()
    return [to_request_out(visible_request(db, item.id, user)) for item in items]


@router.post("", response_model=RequestOut, status_code=201)
def create_request(payload: CreateRequestInput, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.REQUESTER))):
    item = PurchaseRequest(reference=reference(), **payload.model_dump(), status=RequestStatus.POLICY_REVIEW, requester_id=user.id)
    db.add(item); db.flush(); audit(db, item, user, "created", "Purchase request submitted for policy review."); db.commit()
    return to_request_out(visible_request(db, item.id, user))


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return to_request_out(visible_request(db, request_id, user))


@router.post("/{request_id}/agent", response_model=AgentResponseOut)
def ask_agent(request_id: int, payload: AgentMessageInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = visible_request(db, request_id, user)
    answer, tools_used = answer_procurement_question(item, user, payload.message)
    audit(db, item, user, "agent_consulted", f"AI Procurement Agent consulted request data using: {', '.join(tools_used) or 'no tools'}.")
    db.commit()
    return AgentResponseOut(answer=answer, model=OPENAI_MODEL, tools_used=tools_used)


@router.post("/{request_id}/policy-check", response_model=RequestOut)
def policy_check(request_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.PROCUREMENT))):
    item = visible_request(db, request_id, user); run_policy_check(db, item, user); db.commit(); return to_request_out(visible_request(db, item.id, user))


@router.post("/{request_id}/quotes", response_model=list[QuoteOut])
def create_quotes(request_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.PROCUREMENT))):
    item = visible_request(db, request_id, user); quotes = generate_quotes(db, item, user); db.commit(); return quotes


@router.post("/{request_id}/select-quote", response_model=RequestOut)
def choose_quote(request_id: int, payload: SelectQuoteInput, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.PROCUREMENT))):
    item = visible_request(db, request_id, user); select_quote(db, item, payload.quote_id, user); db.commit(); return to_request_out(visible_request(db, item.id, user))


@router.post("/{request_id}/approve", response_model=RequestOut)
def approve(request_id: int, payload: DecisionInput, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.APPROVER))):
    item = visible_request(db, request_id, user); decision(db, item, True, payload.comment, user); db.commit(); return to_request_out(visible_request(db, item.id, user))


@router.post("/{request_id}/reject", response_model=RequestOut)
def reject(request_id: int, payload: DecisionInput, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.APPROVER))):
    item = visible_request(db, request_id, user); decision(db, item, False, payload.comment, user); db.commit(); return to_request_out(visible_request(db, item.id, user))


@router.get("/{request_id}/audit", response_model=list[AuditOut])
def get_audit(request_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = visible_request(db, request_id, user); return audit_out(db, item)
