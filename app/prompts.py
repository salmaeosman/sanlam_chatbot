from __future__ import annotations

from collections import Counter


APP_OVERVIEW = """
Application cible:
- Bawaba de Sanlam est le portail principal utilise par les utilisateurs.
- Les services backend internes alimentent les donnees et les parcours du portail.
- Le produit gere l'authentification JWT, les utilisateurs, les roles, les dashboards par role, les affectations avocat, les reclamations, les documents et les notifications.
- Les reclamations concernent surtout les roles AVOCAT, MEDECIN et GESTIONNAIRE_JUDICIAIRE.
- Les roles MANAGER gerent surtout les utilisateurs et les roles.
- Le chatbot est un assistant de support applicatif et de navigation: il n'ecrit pas en base et ne doit jamais pretendre avoir modifie des donnees.
""".strip()


PAGE_LABELS = {
    "userlistepage": "Plateforme Manager / gestion des utilisateurs",
    "lawyerassignementpage": "Gestion des affectations avocat",
    "ouverturedashboardpage": "Dashboard ouverture",
    "judiciairedashboardpage": "Dashboard judiciaire",
    "avocatdashboardpage": "Dashboard avocat",
    "medecindashboardpage": "Dashboard medecin",
}


ROLE_CAPABILITIES = {
    "MANAGER": [
        "expliquer la gestion des utilisateurs",
        "decrire les roles et dashboards",
        "aider a comprendre l'affectation des droits",
    ],
    "GESTIONNAIRE_JUDICIAIRE": [
        "resumer les reclamations a traiter",
        "expliquer les statuts et les commentaires de gestion",
        "guider sur les pieces et les notifications",
    ],
    "GESTIONNAIRE_OUVERTURE": [
        "expliquer le dashboard ouverture",
        "aider a orienter l'utilisateur vers le bon ecran",
    ],
    "AVOCAT": [
        "aider a creer une reclamation",
        "expliquer les champs obligatoires avocat",
        "suivre les retours du gestionnaire judiciaire",
    ],
    "MEDECIN": [
        "aider a creer une reclamation medecin",
        "expliquer le suivi des dossiers et les documents",
        "guider sur les notifications et le traitement",
    ],
}


ROLE_SUGGESTIONS = {
    "MANAGER": [
        "Resume la plateforme manager pour moi",
        "Comment attribuer un role a un utilisateur ?",
        "Quelle difference entre les dashboards disponibles ?",
    ],
    "GESTIONNAIRE_JUDICIAIRE": [
        "Resume mes reclamations en attente",
        "Explique les statuts de traitement",
        "Comment demander des documents complementaires ?",
    ],
    "GESTIONNAIRE_OUVERTURE": [
        "A quoi sert mon dashboard ouverture ?",
        "Quel ecran dois-je utiliser pour retrouver un dossier ?",
        "Explique le role ouverture dans l'application",
    ],
    "AVOCAT": [
        "Comment creer une nouvelle reclamation ?",
        "Quels documents dois-je fournir ?",
        "Explique les statuts de mes reclamations",
    ],
    "MEDECIN": [
        "Comment creer une reclamation medecin ?",
        "Quels documents sont utiles pour un dossier ?",
        "Comment suivre mes reclamations en cours ?",
    ],
}


DEFAULT_SUGGESTIONS = [
    "Resume ce que je peux faire dans l'application",
    "Explique le role de mon dashboard actuel",
    "Guide-moi vers le bon ecran",
]


def build_suggestions(roles: list[str], page_id: str | None) -> list[str]:
    suggestions: list[str] = []
    for role in roles:
        suggestions.extend(ROLE_SUGGESTIONS.get(role.upper(), []))

    if page_id and page_id in PAGE_LABELS:
        suggestions.append(f"Que puis-je faire sur {PAGE_LABELS[page_id]} ?")

    ordered: list[str] = []
    for item in suggestions + DEFAULT_SUGGESTIONS:
        if item not in ordered:
            ordered.append(item)
    return ordered[:4]


def build_session_title(user: dict) -> str:
    dashboard = user.get("dashboard") or {}
    role = dashboard.get("role") or (user.get("roles") or ["Utilisateur"])[0]
    return f"Assistant IA - {role}"


def build_welcome_message(user: dict, page_id: str | None) -> str:
    full_name = " ".join(
        part for part in [user.get("first_name"), user.get("last_name")] if part
    ).strip() or user.get("username") or "Utilisateur"
    roles = ", ".join(user.get("roles") or ["UTILISATEUR"])
    page_label = PAGE_LABELS.get(page_id or "", "votre espace courant")
    return (
        f"Bonjour {full_name}. Je suis votre assistant IA pour Bawaba de Sanlam.\n\n"
        f"Vous etes connecte avec le(s) role(s): {roles}.\n"
        f"Page actuelle: {page_label}.\n\n"
        "Je peux vous aider a comprendre l'application, les reclamations, les roles, "
        "les notifications et le bon parcours a suivre dans votre dashboard."
    )


def build_system_prompt(context: dict) -> str:
    user = context["user"]
    roles = [role.upper() for role in user.get("roles", [])]
    page_id = context.get("page_id")
    page_label = PAGE_LABELS.get(page_id or "", "Page non definie")
    capabilities = collect_capabilities(roles)
    sections = [
        "Tu es l'assistant applicatif expert de Bawaba de Sanlam.",
        "Reponds toujours en francais.",
        "Sois concret, fiable et oriente support produit.",
        "N'invente jamais des donnees, des compteurs, des actions executees ou des ecrans inexistants.",
        "Si une information live est absente, dis-le clairement.",
        "Le chatbot est en lecture seule: il explique, guide et resume mais ne modifie pas les donnees.",
        "Quand tu parles du produit, appelle-le toujours 'Bawaba de Sanlam' et jamais par un nom de dossier technique.",
        APP_OVERVIEW,
        "Contexte utilisateur live:",
        f"- utilisateur: {format_user_label(user)}",
        f"- roles: {', '.join(roles) if roles else 'aucun role remonte'}",
        f"- dashboard: {(user.get('dashboard') or {}).get('key') or 'non remonte'}",
        f"- homePage: {(user.get('dashboard') or {}).get('homePage') or 'non remonte'}",
        f"- page actuelle: {page_label}",
        f"- chemin courant: {context.get('current_path') or 'non remonte'}",
        "Capacites a privilegier pour cet utilisateur:",
        *[f"- {item}" for item in capabilities],
        *render_live_sections(context),
        "Regles de reponse:",
        "- donne des reponses courtes et operationnelles",
        "- si l'utilisateur demande quoi faire, indique l'ecran ou le parcours le plus logique",
        "- si l'utilisateur demande une action non supportee par ce chatbot, explique les etapes manuelles dans l'application",
        "- quand tu cites des chiffres live, utilise uniquement ceux presents dans le contexte ci-dessous",
    ]
    return "\n".join(sections)


def collect_capabilities(roles: list[str]) -> list[str]:
    merged: list[str] = []
    for role in roles:
        for item in ROLE_CAPABILITIES.get(role, []):
            if item not in merged:
                merged.append(item)
    return merged or ["expliquer la navigation de l'application"]


def render_live_sections(context: dict) -> list[str]:
    sections: list[str] = []

    notifications = context.get("notifications")
    if notifications:
        sections.extend(
            [
                "Notifications live:",
                f"- unreadCount: {notifications.get('unreadCount', 0)}",
            ],
        )

        latest = notifications.get("latest", [])
        if latest:
            sections.append("- dernieres notifications:")
            for item in latest:
                sections.append(
                    f"  - [{item.get('type', 'INFO')}] {item.get('title', 'Sans titre')}",
                )

    reclamations = context.get("reclamations")
    if reclamations:
        stats = reclamations.get("stats") or {}
        sections.extend(
            [
                "Reclamations live:",
                f"- total: {stats.get('total', 0)}",
                f"- openCount: {stats.get('openCount', 0)}",
                f"- awaitingCount: {stats.get('awaitingCount', 0)}",
                f"- inProgressCount: {stats.get('inProgressCount', 0)}",
                f"- resolvedCount: {stats.get('resolvedCount', 0)}",
                f"- rejectedCount: {stats.get('rejectedCount', 0)}",
                f"- closedCount: {stats.get('closedCount', 0)}",
                f"- averageResolutionHours: {stats.get('averageResolutionHours', 'n/a')}",
            ],
        )

        recent = reclamations.get("recent", [])
        if recent:
            sections.append("- reclamations recentes visibles:")
            for row in recent:
                sections.append(
                    "  - "
                    f"id={row.get('id')} status={row.get('status')} "
                    f"claimNumber={row.get('claimNumber') or 'n/a'} "
                    f"policyNumber={row.get('policyNumber') or 'n/a'} "
                    f"category={row.get('category') or 'n/a'}",
                )

    manager = context.get("manager")
    if manager:
        sections.extend(
            [
                "Vue manager live:",
                f"- userCount: {manager.get('userCount', 0)}",
                f"- visibleRoles: {', '.join(manager.get('visibleRoles', [])) or 'aucun'}",
            ],
        )
        top_roles = manager.get("topRoles", [])
        if top_roles:
            sections.append("- repartition des roles:")
            for item in top_roles:
                sections.append(f"  - {item['role']}: {item['total']}")

    return sections


def build_manager_summary(users: list[dict], roles: list[dict]) -> dict:
    role_counter: Counter[str] = Counter()
    for user in users:
        for role in user.get("roles", []):
            role_counter[role] += 1

    top_roles = [
        {"role": role, "total": total}
        for role, total in role_counter.most_common(6)
    ]

    return {
        "userCount": len(users),
        "visibleRoles": [row.get("title", "") for row in roles if row.get("title")],
        "topRoles": top_roles,
    }


def format_user_label(user: dict) -> str:
    full_name = " ".join(
        part for part in [user.get("first_name"), user.get("last_name")] if part
    ).strip()
    if full_name:
        return f"{full_name} (@{user.get('username', 'unknown')})"
    return user.get("username", "Utilisateur")
