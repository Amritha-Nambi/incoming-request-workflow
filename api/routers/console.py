import os
import httpx
from fastapi import APIRouter, HTTPException
from db.database import list_cases, get_case, update_approval, update_draft_response
from models.schema import ApprovalRequest

router = APIRouter()

N8N_APPROVAL_WEBHOOK_URL = os.environ.get("N8N_APPROVAL_WEBHOOK_URL")


@router.get("/cases")
def get_cases():
    return list_cases()


@router.get("/cases/{case_id}")
def get_case_detail(case_id: str):
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.post("/cases/{case_id}/approve")
def approve_case(case_id: str, body: ApprovalRequest):
    case = get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    # save any manual edit to the draft first, so the approval webhook below
    # sends out the reviewer's version rather than the original AI draft
    if body.edited_draft is not None and body.edited_draft != case.get("draft_response"):
        update_draft_response(case_id, body.edited_draft)
        case["draft_response"] = body.edited_draft

    update_approval(case_id, body.approved)

    if body.approved and N8N_APPROVAL_WEBHOOK_URL:
        try:
            httpx.post(N8N_APPROVAL_WEBHOOK_URL, json=case, timeout=10)
        except httpx.HTTPError:
            pass  # DB approval is already recorded; delivery is best-effort

    return {"status": "ok"}
