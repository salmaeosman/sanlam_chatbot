from app.prompts import build_suggestions, build_system_prompt


def test_build_suggestions_prefers_role_specific_items():
    suggestions = build_suggestions(["AVOCAT"], "avocatdashboardpage")
    assert suggestions
    assert any("reclamation" in item.lower() for item in suggestions)


def test_build_system_prompt_contains_live_stats():
    prompt = build_system_prompt(
        {
            "user": {
                "username": "asmae",
                "roles": ["GESTIONNAIRE_JUDICIAIRE"],
                "dashboard": {"key": "judiciaire"},
            },
            "page_id": "judiciairedashboardpage",
            "current_path": "/dashboard/judiciaire",
            "reclamations": {
                "stats": {
                    "total": 10,
                    "openCount": 4,
                    "awaitingCount": 2,
                    "inProgressCount": 2,
                    "resolvedCount": 4,
                    "rejectedCount": 1,
                    "closedCount": 1,
                    "averageResolutionHours": 12.5,
                },
                "recent": [{"id": 1, "status": "EN_ATTENTE", "claimNumber": "C-001"}],
            },
        },
    )

    assert "Reclamations live:" in prompt
    assert "total: 10" in prompt
    assert "claimNumber=C-001" in prompt
