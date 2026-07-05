import os
import re
import uuid
from datetime import datetime
import httpx
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from models.schema import ProcessResponse
from services.classification import classify_request
from services.branch_actions import generate_branch_output
from db.database import insert_case
from utils.file_extraction import extract_text

router = APIRouter()

N8N_PROCESS_WEBHOOK_URL = os.environ.get("N8N_PROCESS_WEBHOOK_URL")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@router.post("/process", response_model=ProcessResponse)
async def process_request(
    source: str = Form(...),
    request_text: str = Form(None),
    requester_email: str = Form(None),
    file: UploadFile = File(None),
):
    if request_text is not None and request_text.strip().lower() in ("", "undefined", "null"):
        request_text = None
    if requester_email is not None and requester_email.strip().lower() in ("", "undefined", "null"):
        requester_email = None

    if file is not None:
        text = await extract_text(file)
    elif request_text:
        text = request_text
    else:
        raise HTTPException(400, "Provide request_text or a file")

    if not requester_email:
        found = EMAIL_PATTERN.search(text)
        requester_email = found.group(0) if found else None

    if not requester_email:
        raise HTTPException(
            400,
            "requester_email is required - provide it directly or ensure it appears in the request text/file",
        )

    classification = classify_request(text)
    branch_output = generate_branch_output(text, classification)

    case = {
        "id": uuid.uuid4().hex[:6].upper(),
        "received_at": datetime.utcnow().isoformat(),
        "source": source,
        "request_text": text,
        "requester_email": requester_email,
        "type": classification["type"],
        "urgency": classification["urgency"],
        "confidence": classification["confidence"],
        **branch_output,
    }
    insert_case(case)

    if N8N_PROCESS_WEBHOOK_URL:
        try:
            httpx.post(N8N_PROCESS_WEBHOOK_URL, json=case, timeout=10)
        except httpx.HTTPError:
            pass  # DB record already saved; delivery is best-effort

    return ProcessResponse(**case)
