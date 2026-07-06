import os, json
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = "gemini-3.1-flash-lite"

VALID_TYPES = ["complaint", "enquiry", "service_request", "escalation"]
VALID_URGENCY = ["low", "medium", "high", "critical"]

CLASSIFY_PROMPT = """You are classifying an incoming request for a telecom operator's operations team.
Requests come from mobile/broadband subscribers via email, web forms, or a shared support inbox.

Request:
\"\"\"{text}\"\"\"

Classify it into exactly one type: complaint, enquiry, service_request, escalation.
- complaint: subscriber is unhappy with service already received - dropped calls, poor call quality, slow data speeds, incorrect billing/overcharge, bad support experience
- enquiry: general question - plan details, coverage area, billing cycle, data usage, how something works
- service_request: an action the subscriber wants performed - SIM replacement, number porting, plan upgrade/downgrade, new connection, address/KYC update
- escalation: genuinely severe or urgent - total network/service outage, safety-critical issue, explicit threat to leave or pursue legal/regulatory action (e.g. TRAI/consumer forum), repeated unresolved failures, distressed or abusive tone

Assign an urgency: low, medium, high, critical.
- enquiry is normally low urgency
- service_request is normally medium urgency
- complaint is normally high urgency
- escalation is critical urgency (only for genuinely severe cases as described above)

Respond with ONLY valid JSON, no other text:
{{"type": "...", "urgency": "...", "confidence": 0.0}}
"""


def classify_request(text: str) -> dict:
    response = client.models.generate_content(
        model=MODEL,
        contents=CLASSIFY_PROMPT.format(text=text),
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    data = json.loads(response.text.strip())
    # if the model returns something outside our known values, fall back to the
    # safest option instead of letting a bad classification break the request
    if data.get("type") not in VALID_TYPES:
        data["type"] = "enquiry"
    if data.get("urgency") not in VALID_URGENCY:
        data["urgency"] = "low"
    data["confidence"] = float(data.get("confidence", 0.7))
    return data
