from app.prompts import (
    build_suggestions,
    build_system_prompt,
    build_welcome_message,
    infer_response_language,
)


def test_build_welcome_message_uses_current_route_title():
    message = build_welcome_message(
        {
            "username": "asmae",
            "roles": ["AVOCAT"],
            "first_name": "Asmae",
            "last_name": "B",
        },
        "avocatdashboardpage",
        "/dashboard/avocat/reclamations",
    )

    assert "Page actuelle: Suivi des reclamations avocat." in message


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


def test_build_system_prompt_describes_judicial_control_page():
    prompt = build_system_prompt(
        {
            "user": {
                "username": "naima",
                "roles": ["GESTIONNAIRE_JUDICIAIRE"],
                "dashboard": {"key": "judiciaire", "homePage": "judiciairedashboardpage"},
            },
            "page_id": "judiciairedashboardpage",
            "current_path": "/dashboard/judiciaire/reclamations/42/controle",
        },
    )

    assert "page actuelle: Controle de la reclamation" in prompt
    assert "Documents, Dossier sinistre, Intervenants, Details et Echanges" in prompt
    assert "Recu illisible" in prompt
    assert "rejeter ou cloturer la reclamation" in prompt


def test_infer_response_language_switches_to_arabic_when_needed():
    assert infer_response_language("مرحبا، اشرح لي هذه الصفحة") == "ar"
    assert infer_response_language("Bonjour, explique cette page") == "fr"
    assert infer_response_language(None) == "fr"


def test_build_system_prompt_requests_arabic_reply_for_arabic_message():
    prompt = build_system_prompt(
        {
            "user": {
                "username": "asmae",
                "roles": ["AVOCAT"],
                "dashboard": {"key": "avocat", "homePage": "avocatdashboardpage"},
            },
            "page_id": "avocatdashboardpage",
            "current_path": "/dashboard/avocat/reclamations",
        },
        latest_user_message="مرحبا، كيف يعمل هذا القسم؟",
    )

    assert "Reponds en arabe." in prompt


def test_build_system_prompt_includes_legal_reference_snippets():
    prompt = build_system_prompt(
        {
            "user": {
                "username": "asmae",
                "roles": ["AVOCAT"],
                "dashboard": {"key": "avocat"},
            },
            "page_id": "avocatdashboardpage",
            "current_path": "/dashboard/avocat/reclamations",
            "legal_reference_snippets": [
                {
                    "page_number": 5,
                    "excerpt": "المادة الثالثة يشمل التعويض المستحق للمصاب ...",
                }
            ],
        },
        latest_user_message="Que dit l'article 3 ?",
    )

    assert "Reference juridique locale chargee:" in prompt
    assert "page 5: المادة الثالثة" in prompt
