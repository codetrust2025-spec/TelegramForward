from features import candidate_store


def test_profile_collapse_keeps_proof_owner_for_edit_actions():
    rows = [
        {
            "id": "active",
            "name": "Kaleshwar",
            "service_type": "profile_service",
            "updated_at": "2026-07-15T00:00:00+00:00",
            "payment": 10000,
            "proofs": [],
        },
        {
            "id": "legacy",
            "name": "KALESHWAR",
            "service_type": "profile_service",
            "updated_at": "2026-05-26T00:00:00+00:00",
            "payment": 9000,
            "proofs": [{"id": "proof-1", "url": "/candidates/legacy/proofs/proof-1"}],
        },
    ]

    merged = candidate_store._collapse_profile_candidates(rows)[0]

    assert merged["id"] == "active"
    assert merged["proof_count"] == 1
    assert merged["proofs"][0]["candidate_id"] == "legacy"


def test_profile_rename_propagates_across_same_phone_legacy_rows(monkeypatch):
    rows = [
        {
            **candidate_store._normalise(
            {
                "name": "KALESHWAR",
                "phone": "8977294695",
                "technology": "React JS",
                "service_type": "profile_service",
            },
            ),
            "id": "active",
        },
        {
            **candidate_store._normalise(
            {
                "name": "KALESHWAR",
                "phone": "8977294695",
                "technology": "React JS",
                "service_type": "profile_service",
                "proofs": [{"id": "proof-1"}],
            },
            ),
            "id": "legacy",
            "proofs": [{"id": "proof-1"}],
        },
    ]
    data = {"candidates": rows}
    monkeypatch.setattr(candidate_store, "_load", lambda: data)
    monkeypatch.setattr(candidate_store, "_save", lambda updated: data.update(updated))

    candidate_store.update_candidate(
        "active",
        {
            "name": "Alluru Kaleswar",
            "email": "allurukali@gmail.com",
            "technology": "Java Full Stack",
        },
    )

    assert {row["name"] for row in data["candidates"]} == {"Alluru Kaleswar"}
    assert {row["email"] for row in data["candidates"]} == {"allurukali@gmail.com"}
    assert {row["technology"] for row in data["candidates"]} == {"Java Full Stack"}
    assert data["candidates"][1]["proofs"][0]["id"] == "proof-1"
