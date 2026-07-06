import os, json
from datetime import datetime, timedelta
from google import genai
from google.genai import types
from services.rag import retrieve

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.1-flash-lite"

DEPARTMENTS = [
    "Billing",
    "Technical Support",
    "SIM & Number Porting",
    "Plan Changes",
    "Network Operations",
]


def _draft_json(prompt: str) -> dict:
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text.strip())


def generate_branch_output(text: str, classification: dict) -> dict:
    # each request type gets handled differently: enquiries are answered straight
    # away from the knowledge base, service requests get routed and confirmed,
    # complaints and escalations only get a drafted response that a human has to approve
    req_type = classification["type"]

    if req_type == "enquiry":
        sources = retrieve(text)
        context = "\n".join(f"- [{s['topic']}] {s['content']}" for s in sources)
        draft = _draft_json(
            "You are drafting a response to a telecom subscriber's enquiry, using ONLY the "
            "knowledge base excerpts below as your source of truth. Do not invent plan details, "
            "prices, or policies that are not present in the excerpts. If the excerpts don't "
            "answer the enquiry, say the subscriber will be followed up with rather than guessing.\n\n"
            f"Knowledge base excerpts:\n{context}\n\n"
            f"Enquiry:\n\"\"\"{text}\"\"\"\n\n"
            "Respond with ONLY valid JSON, no other text:\n"
            '{"subtopic": "4-8 words naming the sub-topic, e.g. plan details, coverage, billing cycle, data usage", '
            '"response": "a short, helpful 2-3 sentence answer to the subscriber, grounded in the excerpts"}'
        )
        subtopic = draft["subtopic"]
        ai_response = draft["response"]
        return {
            "summary": subtopic,
            "department": None,
            "draft_response": ai_response,
            "sources": sources,
            "actions_taken": [
                f"Classified sub-topic: {subtopic}",
                "AI response generated and sent",
                "Logged as resolved",
            ],
            "needs_approval": False,
            "approved": None,
            "sla_deadline": None,
            "status": "resolved",
        }

    if req_type == "service_request":
        department_list = ", ".join(DEPARTMENTS)
        draft = _draft_json(
            "You are triaging a telecom service request for an ops team.\n\n"
            f"Request:\n\"\"\"{text}\"\"\"\n\n"
            "Respond with ONLY valid JSON, no other text:\n"
            '{"summary": "1-2 sentence summary of the request for the ops team", '
            f'"department": "the single best department to route this to, choosing EXACTLY '
            f'one of these strings verbatim: {department_list}", '
            '"confirmation": "a short confirmation message to the subscriber naming that department"}'
        )
        summary = draft["summary"]
        department = draft["department"]
        if department not in DEPARTMENTS:
            # model sometimes drifts from the exact department strings we asked for,
            # so fall back to a safe default rather than routing to a bad value
            department = "Technical Support"
        confirmation = draft["confirmation"]
        return {
            "summary": summary,
            "department": department,
            "draft_response": confirmation,
            "sources": None,
            "actions_taken": [
                "Case summarized",
                f"Routed to {department}",
                "Confirmation sent to requester",
                "4h SLA timer set",
            ],
            "needs_approval": False,
            "approved": None,
            "sla_deadline": (datetime.utcnow() + timedelta(hours=4)).isoformat(),
            "status": "pending",
        }

    if req_type == "complaint":
        draft = _draft_json(
            "Write an empathetic acknowledgement for this telecom subscriber's complaint "
            "(e.g. dropped calls, poor call quality, slow data, billing dispute). "
            "Do not promise specific outcomes or timelines.\n\n"
            f"Complaint:\n\"\"\"{text}\"\"\"\n\n"
            "Respond with ONLY valid JSON, no other text:\n"
            '{"acknowledgement": "exactly ONE ready-to-send acknowledgement message, 2-4 sentences, '
            'plain text with no greeting, no subject line, no markdown, and no alternate options"}'
        )
        return {
            "summary": None,
            "department": None,
            "draft_response": draft["acknowledgement"],
            "sources": None,
            "actions_taken": [
                "Escalated to senior handler queue",
                "Draft acknowledgement generated",
                "2h SLA reminder set",
            ],
            "needs_approval": True,
            "approved": None,
            "sla_deadline": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
            "status": "awaiting_approval",
        }

    # escalation
    draft = _draft_json(
        "Write an urgent acknowledgement for this critical telecom issue "
        "(e.g. total outage, safety issue, regulatory/legal threat). "
        "Do not promise specific outcomes or timelines.\n\n"
        f"Issue:\n\"\"\"{text}\"\"\"\n\n"
        "Respond with ONLY valid JSON, no other text:\n"
        '{"acknowledgement": "exactly ONE ready-to-send acknowledgement message, 2-4 sentences, '
        'plain text with no greeting, no subject line, no markdown, and no alternate options"}'
    )
    return {
        "summary": None,
        "department": None,
        "draft_response": draft["acknowledgement"],
        "sources": None,
        "actions_taken": [
            "Flagged for immediate human attention",
            "Supervisor notified",
            "Draft acknowledgement generated",
        ],
        "needs_approval": True,
        "approved": None,
        "sla_deadline": None,
        "status": "awaiting_approval",
    }
