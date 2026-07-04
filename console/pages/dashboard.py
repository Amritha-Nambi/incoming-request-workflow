import os
from datetime import datetime

import altair as alt
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

from formatting import format_local

load_dotenv()

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

TYPE_ORDER = ["complaint", "enquiry", "service_request", "escalation"]
URGENCY_ORDER = ["low", "medium", "high", "critical"]
STATUS_ORDER = ["pending", "awaiting_approval", "resolved", "rejected"]

TYPE_COLORS = {
    "complaint": "#2a78d6",
    "enquiry": "#1baf7a",
    "service_request": "#eda100",
    "escalation": "#008300",
}
URGENCY_COLORS = {
    "low": "#0ca30c",
    "medium": "#fab219",
    "high": "#ec835a",
    "critical": "#d03b3b",
}
STATUS_COLORS = {
    "pending": "#2a78d6",
    "awaiting_approval": "#fab219",
    "resolved": "#0ca30c",
    "rejected": "#d03b3b",
}

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("Dashboard")


@st.cache_data(ttl=5)
def fetch_cases():
    resp = requests.get(f"{API_BASE_URL}/console/cases", timeout=10)
    resp.raise_for_status()
    return resp.json()


def bar_chart(data: pd.DataFrame, x_field: str, order: list, colors: dict, y_title: str):
    return (
        alt.Chart(data)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=40)
        .encode(
            x=alt.X(f"{x_field}:N", sort=order, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("count:Q", title=y_title),
            color=alt.Color(
                f"{x_field}:N",
                scale=alt.Scale(domain=order, range=[colors[v] for v in order]),
                legend=None,
            ),
            tooltip=[x_field, "count"],
        )
        .properties(height=280)
    )


try:
    cases = fetch_cases()
except requests.RequestException as e:
    st.error(f"Couldn't reach the API at {API_BASE_URL}: {e}")
    st.stop()

if not cases:
    st.caption("No requests processed yet.")
    st.stop()

df = pd.DataFrame(cases)
df["received_at_dt"] = pd.to_datetime(df["received_at"])
df["received_date"] = df["received_at_dt"].dt.date

now = datetime.utcnow()


def is_overdue(row):
    if pd.isna(row["sla_deadline"]) or row["status"] in ("resolved", "rejected"):
        return False
    return datetime.fromisoformat(row["sla_deadline"]) < now


df["overdue"] = df.apply(is_overdue, axis=1)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Cases", len(df))
col2.metric("Awaiting Approval", int((df["status"] == "awaiting_approval").sum()))
col3.metric("Overdue SLA", int(df["overdue"].sum()))
col4.metric("Avg. Confidence", f"{df['confidence'].mean():.0%}")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Cases by Type")
    type_counts = (
        df["type"].value_counts().reindex(TYPE_ORDER, fill_value=0).reset_index()
    )
    type_counts.columns = ["type", "count"]
    st.altair_chart(
        bar_chart(type_counts, "type", TYPE_ORDER, TYPE_COLORS, "Cases"),
        use_container_width=True,
    )

with col2:
    st.subheader("Cases by Urgency")
    urgency_counts = (
        df["urgency"].value_counts().reindex(URGENCY_ORDER, fill_value=0).reset_index()
    )
    urgency_counts.columns = ["urgency", "count"]
    st.altair_chart(
        bar_chart(urgency_counts, "urgency", URGENCY_ORDER, URGENCY_COLORS, "Cases"),
        use_container_width=True,
    )

st.divider()

st.subheader("Case Volume Over Time")
daily_counts = df.groupby("received_date").size().reset_index(name="count")
area_chart = (
    alt.Chart(daily_counts)
    .mark_area(line={"color": "#2a78d6", "strokeWidth": 2}, color="#2a78d633")
    .encode(
        x=alt.X("received_date:T", title=None),
        y=alt.Y("count:Q", title="Cases received"),
        tooltip=["received_date", "count"],
    )
    .properties(height=250)
)
st.altair_chart(area_chart, use_container_width=True)

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("Cases by Status")
    status_counts = (
        df["status"].value_counts().reindex(STATUS_ORDER, fill_value=0).reset_index()
    )
    status_counts.columns = ["status", "count"]
    st.altair_chart(
        bar_chart(status_counts, "status", STATUS_ORDER, STATUS_COLORS, "Cases"),
        use_container_width=True,
    )

with col2:
    st.subheader("Avg. Confidence by Type")
    conf_by_type = (
        df.groupby("type")["confidence"].mean().reindex(TYPE_ORDER, fill_value=0).reset_index()
    )
    confidence_chart = (
        alt.Chart(conf_by_type)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=40, color="#2a78d6")
        .encode(
            x=alt.X("type:N", sort=TYPE_ORDER, title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("confidence:Q", title="Avg. confidence", axis=alt.Axis(format="%")),
            tooltip=["type", alt.Tooltip("confidence:Q", format=".0%")],
        )
        .properties(height=280)
    )
    st.altair_chart(confidence_chart, use_container_width=True)

st.divider()

st.subheader("SLA Timers")
sla_df = df[df["sla_deadline"].notna()].copy()
st.caption(f"{len(sla_df)} of {len(df)} cases have an SLA timer set.")

if sla_df.empty:
    st.caption("No cases currently have an SLA timer.")
else:
    sla_df = sla_df.sort_values("sla_deadline")

    def timer_status(row):
        if row["status"] in ("resolved", "rejected"):
            return "Closed"
        return "Overdue" if row["overdue"] else "On track"

    sla_df["Timer Status"] = sla_df.apply(timer_status, axis=1)
    display_df = pd.DataFrame(
        {
            "ID": sla_df["id"],
            "Type": sla_df["type"].str.replace("_", " ").str.title(),
            "Urgency": sla_df["urgency"].str.title(),
            "Received": sla_df["received_at"].apply(format_local),
            "SLA Deadline": sla_df["sla_deadline"].apply(format_local),
            "Timer Status": sla_df["Timer Status"],
        }
    )
    st.dataframe(display_df, hide_index=True, width="stretch")

with st.expander("View raw case data"):
    raw_df = df.drop(columns=["received_at_dt", "overdue"]).copy()
    raw_df["received_at"] = raw_df["received_at"].apply(format_local)
    raw_df["sla_deadline"] = raw_df["sla_deadline"].apply(
        lambda v: format_local(v) if pd.notna(v) else "-"
    )
    st.dataframe(raw_df, hide_index=True, width="stretch")
