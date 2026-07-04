from pydantic import BaseModel
from typing import Optional, List


class ProcessResponse(BaseModel):
    id: str
    received_at: str
    source: str
    requester_email: Optional[str] = None
    type: str
    urgency: str
    confidence: float
    summary: Optional[str] = None
    department: Optional[str] = None
    draft_response: Optional[str] = None
    sources: Optional[List[dict]] = None
    actions_taken: List[str]
    needs_approval: bool
    approved: Optional[bool] = None
    sla_deadline: Optional[str] = None
    status: str


class ApprovalRequest(BaseModel):
    approved: bool
    edited_draft: Optional[str] = None
