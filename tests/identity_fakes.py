"""A cursor double that answers the identity resolver's queries.

Shared by the resolver tests and the reconciliation tests so both drive the
real ``features.candidate_identity`` logic. Only the database is faked.

Dispatch is on a distinctive table name, and an unrecognised query raises
rather than returning an empty result — a resolver query that changes shape
must fail loudly here instead of silently resolving every candidate to itself.
"""

from __future__ import annotations

from typing import Any


class FakeIdentityCursor:
    def __init__(self, *, candidates=(), links=(), mailboxes=()):
        self.candidates = [dict(row) for row in candidates]
        self.links = list(links)
        self.mailboxes = list(mailboxes)
        self._result: list[tuple] = []
        self.queries: list[str] = []

    # context-manager form, matching psycopg2 cursor usage
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, sql: str, params: Any = ()):
        self.queries.append(sql)
        collapsed = " ".join(sql.split())
        if "FROM candidate_identity_links" in collapsed:
            ids = set(params[0]) | set(params[1] if len(params) > 1 else [])
            self._result = [
                (alias, canonical)
                for alias, canonical in self.links
                if alias in ids or canonical in ids
            ]
        elif "FROM candidate_mailboxes" in collapsed:
            ids = set(params[0])
            addresses = {email.lower() for cid, email in self.mailboxes if cid in ids}
            self._result = [
                (cid, email.lower())
                for cid, email in self.mailboxes
                if email.lower() in addresses
            ]
        elif "FROM candidates_store" in collapsed:
            self._result = [
                (
                    row.get("id"),
                    row.get("name"),
                    row.get("phone"),
                    row.get("email"),
                    row.get("service_type"),
                    row.get("canonical_candidate_id"),
                    row.get("profile_candidate_id"),
                )
                for row in self.candidates
            ]
        else:  # pragma: no cover - a new query must be taught to this fake
            raise AssertionError(f"FakeIdentityCursor cannot answer: {collapsed[:160]}")

    def fetchall(self):
        return list(self._result)

    def fetchone(self):
        return self._result[0] if self._result else None


def profile_row(cid: str, name: str, phone: str = "", email: str = "", **extra):
    """A profile-service candidate row as candidates_store stores it."""
    return {
        "id": cid,
        "name": name,
        "phone": phone,
        "email": email,
        "service_type": "profile_service",
        **extra,
    }
