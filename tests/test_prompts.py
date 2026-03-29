from app.prompts import build_suggestions, build_system_prompt, build_welcome_message


def test_build_suggestions_prefers_role_specific_items():
    suggestions = build_suggestions(
        ["AVOCAT"],
        "avocatdashboardpage",
        "/dashboard/avocat/pv-ia",
    )
    assert suggestions
    assert any("pv ia" in item.lower() for item in suggestions)


def test_build_welcome_message_uses_current_route_title():
    message = build_welcome_message(
        {
            "username": "asmae",
            "roles": ["AVOCAT"],
            "first_name": "Asmae",
            "last_name": "B",
        },
        "avocatdashboardpage",
        "/dashboard/avocat/pv-ia",
    )

    assert "Page actuelle: Agent PV IA." in message


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


def test_build_system_prompt_describes_pv_ia_module():
    prompt = build_system_prompt(
        {
            "user": {
                "username": "asmae",
                "roles": ["AVOCAT"],
                "dashboard": {"key": "avocat", "homePage": "avocatdashboardpage"},
            },
            "page_id": "avocatdashboardpage",
            "current_path": "/dashboard/avocat/pv-ia",
            "pv_extractions": {
                "stats": {
                    "total": 5,
                    "enCoursCount": 2,
                    "termineCount": 2,
                    "erreurCount": 1,
                    "withVictimsCount": 3,
                },
                "recent": [
                    {
                        "id": "pv-1",
                        "statut": "termine",
                        "documentName": "pv-test.pdf",
                        "numeroPolice": "P-001",
                        "ville": "Casablanca",
                        "nombreVictimes": 2,
                    }
                ],
            },
        },
    )

    assert "page actuelle: Agent PV IA" in prompt
    assert "Cette vue permet a l'avocat de deposer un proces-verbal" in prompt
    assert "charger un PV au format PDF, JPG, PNG ou WEBP" in prompt
    assert "PV IA live:" in prompt
    assert "withVictimsCount: 3" in prompt
    assert "documentName=pv-test.pdf" in prompt


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
