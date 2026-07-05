import os
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from formatting import format_local

load_dotenv()

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

URGENCY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
STATUS_ORDER = {"awaiting_approval": 0, "pending": 1, "resolved": 2, "rejected": 3}

URGENCY_BADGE = {
    "critical": ("CRITICAL", "red"),
    "high": ("HIGH", "orange"),
    "medium": ("MEDIUM", "blue"),
    "low": ("LOW", "gray"),
}
STATUS_BADGE = {
    "awaiting_approval": ("AWAITING APPROVAL", "orange"),
    "pending": ("PENDING", "blue"),
    "resolved": ("RESOLVED", "green"),
    "rejected": ("REJECTED", "red"),
}
URGENCY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
STATUS_ICON = {"awaiting_approval": "⏳", "pending": "🔵", "resolved": "✅", "rejected": "❌"}

st.set_page_config(page_title="Console", page_icon="📋", layout="wide")
st.title("Case Console")


@st.cache_data(ttl=5)
def fetch_cases():
    resp = requests.get(f"{API_BASE_URL}/console/cases", timeout=10)
    resp.raise_for_status()
    return resp.json()


def submit_approval(case_id: str, approved: bool, edited_draft: str | None = None):
    requests.post(
        f"{API_BASE_URL}/console/cases/{case_id}/approve",
        json={"approved": approved, "edited_draft": edited_draft},
        timeout=10,
    )
    st.cache_data.clear()


def approve_reject_buttons(case: dict, edited_draft: str | None = None):
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Approve", key=f"approve_{case['id']}", type="primary", width="stretch"):
            submit_approval(case["id"], True, edited_draft)
            st.rerun()
    with col2:
        if st.button("Reject", key=f"reject_{case['id']}", width="stretch"):
            submit_approval(case["id"], False, edited_draft)
            st.rerun()


def render_request_details(case: dict):
    st.markdown("##### 1 · Request Details")
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        col1.write("**Source**")
        col1.write(case["source"])
        col2.write("**Customer email**")
        col2.write(case.get("requester_email") or "Not provided")
        col3.write("**Received**")
        col3.write(format_local(case["received_at"]))
        st.write("**Request text**")
        st.info(case["request_text"])


def render_classification(case: dict):
    st.markdown("##### 2 · AI Classification")
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write("**Type**")
            st.badge(case["type"].replace("_", " ").upper(), color="violet")
        with col2:
            st.write("**Urgency**")
            label, color = URGENCY_BADGE.get(case["urgency"], (case["urgency"].upper(), "gray"))
            st.badge(label, color=color)
        with col3:
            st.write("**Confidence**")
            st.write(f"{case['confidence']:.0%}")


def render_approval(case: dict):
    st.markdown("##### 3 · Approval")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.write("**SLA deadline**")
        col1.write(format_local(case.get("sla_deadline")))

        col2.write("**Approval status**")
        if not case["needs_approval"]:
            col2.write("Not required")
        elif case["approved"] is None:
            col2.write("Pending review")
        else:
            col2.write("Approved" if case["approved"] else "Rejected")

        pending = case["needs_approval"] and case["approved"] is None
        if pending:
            st.write("**Draft acknowledgement (edit before sending):**")
            edited_draft = st.text_area(
                "Draft acknowledgement",
                value=case["draft_response"] or "",
                key=f"draft_{case['id']}",
                height=140,
                label_visibility="collapsed",
            )
            st.divider()
            approve_reject_buttons(case, edited_draft)
        elif case["needs_approval"]:
            st.write("**Draft acknowledgement sent:**")
            st.info(case["draft_response"] or "(no draft)")


def render_log(case: dict):
    req_type = case["type"]
    st.markdown("##### 4 · Log")
    with st.container(border=True):
        label, color = STATUS_BADGE.get(case["status"], (case["status"].upper(), "gray"))
        st.badge(label, color=color)

        if req_type == "enquiry":
            st.write("**Sub-topic:**", case.get("summary") or "-")
            st.write("**AI response sent to customer:**")
            st.info(case["draft_response"] or "(no draft)")
            if case.get("sources"):
                st.write("**Grounded in:**")
                for s in case["sources"]:
                    st.caption(f"- {s['topic']}: {s['content']}")

        elif req_type == "service_request":
            st.write("**Summary:**", case.get("summary") or "-")
            st.write("**Routed to department:**", case.get("department") or "-")
            st.write("**Confirmation message sent to customer:**")
            st.info(case["draft_response"] or "(no draft)")

        st.write("**Log:**")
        for action in case["actions_taken"]:
            st.write(f"✓ {action}")


def render_case_detail(case: dict):
    st.subheader(f"Case {case['id']}")
    render_request_details(case)
    render_classification(case)
    render_approval(case)
    render_log(case)


tab_submit, tab_cases = st.tabs(["Submit Request", "Cases"])

with tab_submit:
    st.subheader("Submit a new request")

    with st.form("submit_request", clear_on_submit=True):
        uploaded_file = st.file_uploader(
            "Upload file", type=["txt", "eml", "pdf", "docx"],
            help="Requester email is auto-detected from the file's content.",
        )

        submitted = st.form_submit_button("Submit for classification")
        if submitted:
            if not uploaded_file:
                st.error("Provide a file.")
            else:
                data = {"source": "console"}
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                try:
                    resp = requests.post(f"{API_BASE_URL}/process", data=data, files=files, timeout=60)
                    resp.raise_for_status()
                    result = resp.json()
                    st.success(f"Submitted. Your reference case number is **{result['id']}**.")
                    st.write(
                        f"Classified as **{result['type']}** (urgency: {result['urgency']})"
                    )
                    st.cache_data.clear()
                except requests.RequestException as e:
                    detail = None
                    if e.response is not None:
                        try:
                            detail = e.response.json().get("detail")
                        except ValueError:
                            pass
                    st.error(f"Submission failed: {detail or e}")

with tab_cases:
    try:
        cases = fetch_cases()
    except requests.RequestException as e:
        st.error(f"Couldn't reach the API at {API_BASE_URL}: {e}")
        st.stop()

    if not cases:
        st.caption("No requests processed yet.")
    else:
        received_dates = [datetime.fromisoformat(c["received_at"]).date() for c in cases]
        min_date, max_date = min(received_dates), max(received_dates)

        st.markdown("**Filters**")
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            date_range = st.date_input(
                "Received date range", value=(min_date, max_date),
                min_value=min_date, max_value=max_date,
            )
        with col2:
            status_options = sorted(
                {c["status"] for c in cases}, key=lambda s: STATUS_ORDER.get(s, 99)
            )
            status_filter = st.multiselect("Status", status_options, default=status_options)
        with col3:
            urgency_options = sorted(
                {c["urgency"] for c in cases}, key=lambda u: URGENCY_ORDER.get(u, 99)
            )
            urgency_filter = st.multiselect("Urgency", urgency_options, default=urgency_options)

        start_date, end_date = (date_range if len(date_range) == 2 else (min_date, max_date))
        filtered = [
            c for c in cases
            if start_date <= datetime.fromisoformat(c["received_at"]).date() <= end_date
            and c["status"] in status_filter
            and c["urgency"] in urgency_filter
        ]

        # newest-first within each status/urgency group (stable sort: sort by
        # received_at first, then by status/urgency so that ordering survives)
        filtered = sorted(filtered, key=lambda c: c["received_at"], reverse=True)
        filtered = sorted(
            filtered,
            key=lambda c: (STATUS_ORDER.get(c["status"], 99), URGENCY_ORDER.get(c["urgency"], 99)),
        )

        st.subheader(f"Cases ({len(filtered)} of {len(cases)})")
        if not filtered:
            st.caption("No cases match the current filters.")
        else:
            def id_label(c: dict) -> str:
                is_open = c["status"] not in ("resolved", "rejected")
                icons = ""
                if is_open and "Flagged for immediate human attention" in c["actions_taken"]:
                    icons += "🚨 "
                if is_open and c.get("sla_deadline"):
                    icons += "⏱ "
                return f"{icons}{c['id']}" if icons else c["id"]

            table = pd.DataFrame(
                [
                    {
                        "ID": id_label(c),
                        "Received": format_local(c["received_at"]),
                        "Type": c["type"].replace("_", " ").title(),
                        "Urgency": f"{URGENCY_ICON.get(c['urgency'], '')} {c['urgency'].title()}",
                        "Status": f"{STATUS_ICON.get(c['status'], '')} {c['status'].replace('_', ' ').title()}",
                    }
                    for c in filtered
                ]
            )
            event = st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                on_select="rerun",
                selection_mode="single-row",
            )

            selected_rows = event.selection["rows"] if event and event.selection else []
            if selected_rows:
                st.divider()
                render_case_detail(filtered[selected_rows[0]])
            else:
                st.caption("Click a row above to open that case.")
