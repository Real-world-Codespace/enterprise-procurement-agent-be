from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PurchaseRequest, RequestStatus, Role, User
from .security import hash_password
from .services import audit, reference, run_policy_check


def seed(db: Session):
    if db.execute(select(User)).first():
        return
    password = hash_password("demo-password")
    requester = User(name="Mai Nguyen", email="mai.nguyen@acme.local", password_hash=password, role=Role.REQUESTER, department="Product")
    procurement = User(name="Minh Tran", email="minh.tran@acme.local", password_hash=password, role=Role.PROCUREMENT, department="Procurement")
    approver = User(name="Lan Pham", email="lan.pham@acme.local", password_hash=password, role=Role.APPROVER, department="Finance")
    db.add_all([requester, procurement, approver]); db.flush()
    item = PurchaseRequest(reference=reference(), title="Laptop onboarding - Product", category="laptop", quantity=8,
                           estimated_amount=190_000_000, cost_center="PRODUCT", business_justification="Trang bị thiết bị cho nhân sự Product mới.",
                           status=RequestStatus.POLICY_REVIEW, requester_id=requester.id)
    db.add(item); db.flush(); audit(db, item, requester, "created", "Purchase request created by requester."); run_policy_check(db, item, procurement)
    db.commit()
