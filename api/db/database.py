import os
import json
import libsql_client

_COLUMNS = [
    "id", "received_at", "source", "requester_email", "request_text", "type",
    "urgency", "confidence", "summary", "department", "draft_response", "sources",
    "actions_taken", "needs_approval", "approved", "sla_deadline", "status",
]

_client = None


def _get_client():
    global _client
    if _client is None:
        # The websocket (libsql://) protocol fails its handshake against this
        # Turso instance; the HTTP protocol works, so force it regardless of
        # which scheme is configured in the environment.
        url = os.environ["TURSO_DATABASE_URL"].replace("libsql://", "https://")
        _client = libsql_client.create_client_sync(
            url=url,
            auth_token=os.environ["TURSO_AUTH_TOKEN"],
        )
    return _client


def init_db():
    _get_client().execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id TEXT PRIMARY KEY,
            received_at TEXT NOT NULL,
            source TEXT NOT NULL,
            requester_email TEXT,
            request_text TEXT NOT NULL,
            type TEXT NOT NULL,
            urgency TEXT NOT NULL,
            confidence REAL NOT NULL,
            summary TEXT,
            department TEXT,
            draft_response TEXT,
            sources TEXT,
            actions_taken TEXT NOT NULL,
            needs_approval INTEGER NOT NULL,
            approved INTEGER,
            sla_deadline TEXT,
            status TEXT NOT NULL
        )
        """
    )
    for column, coltype in [("sources", "TEXT"), ("requester_email", "TEXT")]:
        try:
            _get_client().execute(f"ALTER TABLE cases ADD COLUMN {column} {coltype}")
        except Exception:
            pass  # column already exists on a table created before this field was added


def _row_to_case(row) -> dict:
    case = dict(zip(_COLUMNS, row))
    case["actions_taken"] = json.loads(case["actions_taken"])
    case["sources"] = json.loads(case["sources"]) if case["sources"] is not None else None
    case["needs_approval"] = bool(case["needs_approval"])
    case["approved"] = None if case["approved"] is None else bool(case["approved"])
    return case


def insert_case(case: dict):
    values = [
        case["id"], case["received_at"], case["source"], case.get("requester_email"),
        case["request_text"], case["type"], case["urgency"], case["confidence"],
        case.get("summary"), case.get("department"), case.get("draft_response"),
        None if case.get("sources") is None else json.dumps(case["sources"]),
        json.dumps(case["actions_taken"]), int(case["needs_approval"]),
        None if case.get("approved") is None else int(case["approved"]),
        case.get("sla_deadline"), case["status"],
    ]
    _get_client().execute(
        f"INSERT INTO cases ({', '.join(_COLUMNS)}) "
        f"VALUES ({', '.join(['?'] * len(_COLUMNS))})",
        values,
    )


def list_cases() -> list[dict]:
    rs = _get_client().execute(
        f"SELECT {', '.join(_COLUMNS)} FROM cases ORDER BY received_at DESC"
    )
    return [_row_to_case(row) for row in rs.rows]


def get_case(case_id: str) -> dict | None:
    rs = _get_client().execute(
        f"SELECT {', '.join(_COLUMNS)} FROM cases WHERE id = ?", [case_id]
    )
    return _row_to_case(rs.rows[0]) if rs.rows else None


def update_approval(case_id: str, approved: bool):
    status = "resolved" if approved else "rejected"
    _get_client().execute(
        "UPDATE cases SET approved = ?, needs_approval = 0, status = ? WHERE id = ?",
        [int(approved), status, case_id],
    )


def update_draft_response(case_id: str, draft_response: str):
    _get_client().execute(
        "UPDATE cases SET draft_response = ? WHERE id = ?",
        [draft_response, case_id],
    )
