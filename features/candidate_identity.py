"""One definition of "who is this candidate" for every part of Teleautomation.

The system grew four separate answers to that question:

* ``candidate_identity_links`` — derived once per backend start by migration 010
  from phone, personal email, mailbox email and explicit relationships.
* ``candidate_store.candidate_identity_ids`` — the application resolver, which
  also collapses rows by canonical *name* through ``_CANDIDATE_NAME_ALIASES``.
* ``_collapse_profile_candidates`` — the Candidates page display winner, which
  is what a mailbox is attached to at OAuth-connect time.
* ``bgv_register.profile_key`` — ``name|phone``, in a JSON file.

Reconciliation used the first one alone, through a single ``COALESCE`` hop.
That is unsafe for three independent reasons, all provable from the migration
SQL rather than from any particular row:

1. **Buckets, not components.** Migration 010 groups by phone, then by personal
   email, then by mailbox email, assigning ``min(id)`` inside each group
   separately.  A person whose rows are joined by phone *and* by mailbox can
   land in two different buckets, because the groups are never unioned.
2. **Same-priority updates are skipped.**  Every rule ends with
   ``WHERE EXCLUDED.match_priority < candidate_identity_links.match_priority``.
   Re-deriving ``VERIFIED_PHONE`` over an existing ``VERIFIED_PHONE`` row is
   ``3 < 3`` → false, so a row keeps a stale canonical forever once a
   lexicographically smaller id joins its group.
3. **No transitivity guarantee.**  Nothing makes
   ``canonical(canonical(x)) == canonical(x)``, so one hop can stop halfway
   along a chain.

This module answers the question by computing the *connected component* over
every relationship the system knows about, so the answer is transitive and
idempotent by construction.

Deliberate non-goal: this module does not decide which record should survive a
merge.  ``cluster_representative`` returns a stable *label*, never an identity
ruling, and nothing here merges, rewrites or deletes candidate data.  Deciding
a surviving record is a data decision that needs human evidence.
"""

from __future__ import annotations

from typing import Any, Iterable

from features import candidate_store


# One cluster can legitimately span a person's profile row plus every interview
# clone. It cannot legitimately span the whole table: that would mean the
# closure has joined unrelated people through a shared blank key, so refuse
# rather than silently treat everyone as one candidate.
MAX_CLUSTER_SIZE = 64


class IdentityClusterTooLarge(RuntimeError):
    """The closure joined implausibly many rows — refuse rather than guess."""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _phone_key(value: Any) -> str:
    return candidate_store.candidate_phone_identity(value)


def _email_key(value: Any) -> str:
    key = _clean(value).casefold()
    return key if "@" in key else ""


def _name_key(value: Any) -> str:
    """Canonical-name key, so "Reddy Charan M S" and "Ram Charan M S" agree."""
    canonical = candidate_store.canonical_candidate_name(_clean(value))
    return candidate_store._normalise_candidate_name_key(canonical)


def _is_profile_row(row: dict[str, Any]) -> bool:
    return (
        candidate_store._normalise_service_type(row.get("service_type"), row)
        != "round_wise"
    )


def _fetch_links(cur, ids: Iterable[str]) -> list[tuple[str, str]]:
    """Every link row touching these ids, in both directions."""
    values = [str(value) for value in ids if str(value or "")]
    if not values:
        return []
    cur.execute(
        """SELECT alias_candidate_id,canonical_candidate_id
           FROM candidate_identity_links
           WHERE alias_candidate_id=ANY(%s) OR canonical_candidate_id=ANY(%s)""",
        (values, values),
    )
    return [(str(row[0] or ""), str(row[1] or "")) for row in cur.fetchall()]


def _fetch_mailbox_peers(cur, ids: Iterable[str]) -> list[tuple[str, str]]:
    """Candidate ids sharing a mailbox address with any of these ids."""
    values = [str(value) for value in ids if str(value or "")]
    if not values:
        return []
    cur.execute(
        """SELECT candidate_id,lower(email_address)
           FROM candidate_mailboxes
           WHERE lower(email_address) IN (
             SELECT lower(email_address) FROM candidate_mailboxes
             WHERE candidate_id=ANY(%s))""",
        (values,),
    )
    return [(str(row[0] or ""), str(row[1] or "")) for row in cur.fetchall()]


def _fetch_candidate_rows(cur) -> list[dict[str, Any]]:
    """Identity columns for every candidate row.

    Name matching runs through ``_CANDIDATE_NAME_ALIASES``, which SQL cannot
    express, so the rows come back to Python. This is the same working set
    ``candidate_store._load()`` already materializes on every list call.
    """
    cur.execute(
        """SELECT id,
                  payload->>'name',
                  payload->>'phone',
                  payload->>'email',
                  payload->>'service_type',
                  payload->>'canonical_candidate_id',
                  payload->>'profile_candidate_id'
           FROM candidates_store"""
    )
    return [
        {
            "id": str(row[0] or ""),
            "name": row[1],
            "phone": row[2],
            "email": row[3],
            "service_type": row[4],
            "canonical_candidate_id": row[5],
            "profile_candidate_id": row[6],
        }
        for row in cur.fetchall()
    ]


def identity_cluster(cur, candidate_id: str) -> frozenset[str]:
    """Every candidate id that provably belongs to the same person.

    The closure runs to a fixpoint over links, explicit relationships, phone,
    personal email, mailbox address and canonical name, so the result is the
    same whichever member it starts from — which is what makes it transitive
    and idempotent, unlike a single ``candidate_identity_links`` hop.
    """
    seed = _clean(candidate_id)
    if not seed:
        return frozenset()

    rows = {row["id"]: row for row in _fetch_candidate_rows(cur) if row["id"]}

    # Index the identity keys once; the closure loop then only does lookups.
    by_phone: dict[str, set[str]] = {}
    by_email: dict[str, set[str]] = {}
    by_name: dict[str, set[str]] = {}
    for row in rows.values():
        phone = _phone_key(row.get("phone"))
        if phone:
            by_phone.setdefault(phone, set()).add(row["id"])
        email = _email_key(row.get("email"))
        if email:
            by_email.setdefault(email, set()).add(row["id"])
        # Round-wise support rows repeat a name without being that person's
        # profile, so they never join a cluster by name alone. This mirrors
        # candidate_store.candidate_identity_ids.
        if _is_profile_row(row):
            name = _name_key(row.get("name"))
            if name:
                by_name.setdefault(name, set()).add(row["id"])

    cluster = {seed}
    frontier = {seed}
    while frontier:
        found: set[str] = set()

        for alias, canonical in _fetch_links(cur, frontier):
            if alias in cluster or canonical in cluster:
                found.update({alias, canonical})

        for peer, _email in _fetch_mailbox_peers(cur, frontier):
            found.add(peer)

        for cid in frontier:
            row = rows.get(cid)
            if not row:
                continue
            phone = _phone_key(row.get("phone"))
            if phone:
                found.update(by_phone.get(phone, ()))
            email = _email_key(row.get("email"))
            if email:
                found.update(by_email.get(email, ()))
            if _is_profile_row(row):
                name = _name_key(row.get("name"))
                if name:
                    found.update(by_name.get(name, ()))
            explicit = _clean(row.get("canonical_candidate_id")) or _clean(
                row.get("profile_candidate_id")
            )
            if explicit:
                found.add(explicit)

        # A row naming this one as its profile belongs here too.
        for row in rows.values():
            explicit = _clean(row.get("canonical_candidate_id")) or _clean(
                row.get("profile_candidate_id")
            )
            if explicit and explicit in frontier:
                found.add(row["id"])

        found = {value for value in found if value}
        frontier = found - cluster
        cluster |= frontier
        if len(cluster) > MAX_CLUSTER_SIZE:
            raise IdentityClusterTooLarge(
                f"Identity closure for {seed} exceeded {MAX_CLUSTER_SIZE} rows; "
                "a blank or shared identity key has joined unrelated candidates."
            )

    return frozenset(cluster)


def same_identity(cur, left: str, right: str) -> bool:
    """True when both ids provably describe one person.

    Sharing a single member is enough: the closure is transitive, so two
    clusters that intersect are the same component reached from two seeds.
    """
    if _clean(left) == _clean(right):
        return bool(_clean(left))
    left_cluster = identity_cluster(cur, left)
    if not left_cluster:
        return False
    return _clean(right) in left_cluster


def cluster_representative(cur, cluster: Iterable[str]) -> str:
    """A stable label for one cluster — *not* a ruling on which record wins.

    An explicit relationship recorded by a human wins, because that is the one
    signal in the data that someone actually asserted. Otherwise the lowest id
    is used purely so the label does not move between calls; it carries no
    evidential weight and must never be read as "this is the surviving record".
    """
    members = sorted({_clean(value) for value in cluster if _clean(value)})
    if not members:
        return ""
    rows = {row["id"]: row for row in _fetch_candidate_rows(cur)}
    declared = {
        _clean(rows[cid].get("canonical_candidate_id"))
        or _clean(rows[cid].get("profile_candidate_id"))
        for cid in members
        if cid in rows
    }
    declared = {value for value in declared if value and value in members}
    if len(declared) == 1:
        return next(iter(declared))
    return members[0]
