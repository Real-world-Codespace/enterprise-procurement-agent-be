from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import PurchaseRequest, RequestStatus, Role, User
from ..schemas import DashboardOut
from ..security import current_user
from ..services import to_request_out, visible_request

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    base = select(PurchaseRequest)
    if user.role == Role.REQUESTER: base = base.where(PurchaseRequest.requester_id == user.id)
    items = db.execute(base.order_by(PurchaseRequest.updated_at.desc())).scalars().all()
    requests = [to_request_out(visible_request(db, item.id, user)) for item in items[:5]]
    open_count = sum(i.status not in {RequestStatus.PR_CREATED, RequestStatus.REJECTED} for i in items)
    pending = sum(i.status == RequestStatus.PENDING_APPROVAL for i in items)
    created = sum(i.status == RequestStatus.PR_CREATED and i.updated_at.month == datetime.utcnow().month for i in items)
    exceptions = sum(i.status == RequestStatus.NEEDS_INFO for i in items)
    return DashboardOut(total_open=open_count, pending_approval=pending, pr_created_this_month=created,
                        policy_exception_rate=round(exceptions / len(items) * 100, 1) if items else 0, recent_requests=requests)
