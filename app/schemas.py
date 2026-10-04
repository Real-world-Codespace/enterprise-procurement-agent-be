from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from .models import RequestStatus, Role


class LoginInput(BaseModel):
    email: str
    password: str


class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    department: str = Field(min_length=2, max_length=80)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    email: str
    role: Role
    department: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class CreateRequestInput(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    category: str = Field(min_length=2, max_length=100)
    quantity: int = Field(gt=0, le=10000)
    estimated_amount: float = Field(gt=0)
    cost_center: str = Field(min_length=2, max_length=80)
    business_justification: str = Field(min_length=10)


class QuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vendor_name: str
    total_amount: float
    delivery_days: int
    warranty_months: int
    compliance_status: str
    score: float
    is_selected: bool


class AuditOut(BaseModel):
    id: int
    event_type: str
    message: str
    created_at: datetime
    actor_name: str | None = None


class RequestOut(BaseModel):
    id: int
    reference: str
    title: str
    category: str
    quantity: int
    estimated_amount: float
    currency: str
    cost_center: str
    business_justification: str
    status: RequestStatus
    policy_result: str | None
    budget_available: float | None
    pr_number: str | None
    requester_name: str
    created_at: datetime
    quotes: list[QuoteOut] = []


class DecisionInput(BaseModel):
    comment: str = Field(min_length=3, max_length=1000)


class SelectQuoteInput(BaseModel):
    quote_id: int


class AgentMessageInput(BaseModel):
    message: str = Field(min_length=3, max_length=3000)


class AgentResponseOut(BaseModel):
    answer: str
    model: str
    tools_used: list[str]


class DashboardOut(BaseModel):
    total_open: int
    pending_approval: int
    pr_created_this_month: int
    policy_exception_rate: float
    recent_requests: list[RequestOut]
