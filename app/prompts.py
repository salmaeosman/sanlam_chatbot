from __future__ import annotations

from collections import Counter


APP_OVERVIEW = """
Application cible:
- Bawaba de Sanlam est le portail principal utilise par les utilisateurs.
- Les services backend internes alimentent les donnees et les parcours du portail.
- Le produit gere l'authentification JWT, les utilisateurs, les roles, les dashboards par role, les affectations avocat, les reclamations, les documents et les notifications.
- Les modules connus incluent la Plateforme Manager, la gestion des affectations avocat, les dashboards Ouverture, Judiciaire, Avocat et Medecin, ainsi que le module PV IA.
- Quand l'utilisateur parle de 'Agent PV IA' ou de 'PV IA', il s'agit d'un ecran metier de Bawaba de Sanlam pour charger un proces-verbal, lancer l'extraction IA et controler les champs detectes. Ce n'est pas un agent autonome separe.
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


PRODUCT_MODULES = [
    "Plateforme Manager: consulter les utilisateurs, trier par nom ou roles, ajouter ou modifier un utilisateur, supprimer un utilisateur et ouvrir la gestion des roles d'un avocat.",
    "Gestion des affectations avocat: rechercher par avocat ou juridiction, consulter les affectations, ouvrir le detail d'un avocat et ajouter, modifier ou supprimer des creneaux de travail.",
    "Dashboard ouverture: espace personnel du gestionnaire ouverture avec recherche par numero de sinistre, numero de mission, assure et date de survenance.",
    "Pre-ouverture assistee par IA: vue ouverture du module PV IA pour revoir les PV extraits, completer les champs utiles et preparer la suite du traitement.",
    "Dashboard judiciaire: espace personnel du gestionnaire judiciaire avec recherche et acces aux files de reclamations.",
    "Reclamations judiciaires: files 'remontes au superviseur', 'en attente', 'clotures' et 'redressements contestes' avec action de controle.",
    "Controle judiciaire d'une reclamation: onglets Documents, Dossier sinistre, Intervenants, Details et Echanges, plus actions Rejeter et Cloturer.",
    "Dashboard avocat: espace personnel avec vue rapide des dossiers, acces au module Agent PV IA et au suivi des reclamations.",
    "Agent PV IA: depot d'un PV PDF/JPG/PNG/WEBP, extraction IA, recherche, filtres, edition des champs, consultation des victimes et vehicules et telechargement de la source.",
    "Reclamations avocat et medecin: suivi des dossiers, filtres par police/sinistre/cabinet/date, detail d'une reclamation, messages et vue synthese.",
    "Creation de reclamation: formulaire avec categorie, type de demande, motif, numero de police, numero de sinistre, date de survenance, commentaire et pieces jointes; la reference cabinet est obligatoire pour l'avocat.",
    "Dashboard medecin: espace personnel de recherche de mission par numero de sinistre, numero de mission ou nom de l'assure.",
]


PAGE_GUIDES = {
    "userlistepage": {
        "title": "Plateforme Manager",
        "summary": "Cet ecran sert a administrer les utilisateurs et a piloter leurs roles visibles dans le portail.",
        "actions": [
            "consulter la liste des utilisateurs",
            "trier les utilisateurs par nom ou par roles",
            "ajouter un utilisateur",
            "modifier ou supprimer un utilisateur",
            "ouvrir la gestion des roles pour un avocat",
        ],
    },
    "lawyerassignementpage": {
        "title": "Gestion des affectations avocat",
        "summary": "Cet ecran sert a gerer les juridictions affectees aux avocats et leurs periodes de travail.",
        "actions": [
            "rechercher un avocat par nom",
            "filtrer par juridiction",
            "ouvrir le detail d'un avocat",
            "ajouter un creneau de travail",
            "modifier ou supprimer une periode deja affectee",
        ],
    },
    "ouverturedashboardpage": {
        "title": "Dashboard ouverture",
        "summary": "Cet espace sert au gestionnaire ouverture pour retrouver un dossier et acceder au parcours de pre-ouverture assistee.",
        "actions": [
            "rechercher par numero de sinistre",
            "rechercher par numero de mission",
            "rechercher par nom de l'assure",
            "ajouter la date de survenance dans les recherches ciblees",
            "ouvrir la vue de pre-ouverture assistee par IA",
        ],
    },
    "judiciairedashboardpage": {
        "title": "Dashboard judiciaire",
        "summary": "Cet espace sert au gestionnaire judiciaire pour retrouver les reclamations et acceder au controle detaille d'un dossier.",
        "actions": [
            "rechercher un dossier par numero de sinistre, mission, assure ou date",
            "ouvrir les files de reclamations judiciaires",
            "identifier les dossiers en attente ou clotures",
            "ouvrir la page de controle d'une reclamation",
        ],
    },
    "avocatdashboardpage": {
        "title": "Dashboard avocat",
        "summary": "Cet espace centralise la vue rapide avocat, les reclamations et le module Agent PV IA.",
        "actions": [
            "consulter une vue rapide des dossiers",
            "ouvrir l'Agent PV IA pour pre-ouvrir un sinistre",
            "suivre les reclamations",
            "creer une nouvelle reclamation",
        ],
    },
    "medecindashboardpage": {
        "title": "Dashboard medecin",
        "summary": "Cet espace sert a retrouver une mission et a acceder au suivi des reclamations medecin.",
        "actions": [
            "rechercher par numero de sinistre",
            "rechercher par numero de mission",
            "rechercher par nom de l'assure",
            "ouvrir le suivi ou la creation de reclamations medecin",
        ],
    },
}


ROUTE_GUIDES = [
    {
        "starts_with": "/dashboard/judiciaire/reclamations/",
        "contains": "/controle",
        "title": "Controle de la reclamation",
        "summary": "Cette vue sert au gestionnaire judiciaire pour controler un dossier, gerer les documents et statuer sur la reclamation.",
        "actions": [
            "consulter les onglets Documents, Dossier sinistre, Intervenants, Details et Echanges",
            "televerser et telecharger des documents du dossier",
            "mettre a jour le statut des documents obligatoires: Recu, Recu illisible, Manquant ou En attente",
            "lire les metadonnees du dossier et les commentaires",
            "rejeter ou cloturer la reclamation",
        ],
        "suggestions": [
            "Que puis-je faire sur le controle de la reclamation ?",
            "Explique les statuts documentaires du controle judiciaire",
            "Quand utiliser Rejeter ou Cloturer ?",
        ],
    },
    {
        "starts_with": "/dashboard/avocat/reclamations/nouvelle",
        "title": "Creation de reclamation avocat",
        "summary": "Cette vue sert a formuler une nouvelle reclamation avocat et a joindre les pieces utiles.",
        "actions": [
            "choisir la categorie de la demande",
            "selectionner le type de demande",
            "renseigner le motif, le numero de police, le numero de sinistre et la date de survenance",
            "saisir la reference cabinet obligatoire pour l'avocat",
            "ajouter un commentaire et televerser des documents",
        ],
        "suggestions": [
            "Quels champs sont obligatoires pour une reclamation avocat ?",
            "Quels documents puis-je joindre a une reclamation ?",
            "A quoi sert la reference cabinet ?",
        ],
    },
    {
        "starts_with": "/dashboard/medecin/reclamations/nouvelle",
        "title": "Creation de reclamation medecin",
        "summary": "Cette vue sert a formuler une nouvelle reclamation medecin et a joindre les pieces utiles.",
        "actions": [
            "choisir la categorie de la demande",
            "selectionner le type de demande",
            "renseigner le motif, le numero de police, le numero de sinistre et la date de survenance",
            "ajouter un commentaire et televerser des documents",
        ],
        "suggestions": [
            "Quels champs sont obligatoires pour une reclamation medecin ?",
            "Quels documents puis-je joindre a une reclamation ?",
            "Comment creer une reclamation medecin ?",
        ],
    },
    {
        "starts_with": "/dashboard/avocat/pv-ia",
        "title": "Agent PV IA",
        "summary": "Cette vue permet a l'avocat de deposer un proces-verbal, lancer l'extraction IA, verifier les champs structures et enregistrer les corrections.",
        "actions": [
            "charger un PV au format PDF, JPG, PNG ou WEBP",
            "lancer l'analyse IA du document",
            "consulter les statistiques PV total, en cours, termines et avec victimes",
            "rechercher un PV par document, numero de police ou ville et filtrer par statut",
            "modifier le statut, le nom du document, le numero de police, la date de survenance, la ville, l'adresse et les resumes FR/AR",
            "consulter les victimes detectees et les vehicules detectes",
            "telecharger le document source et enregistrer les modifications",
        ],
        "suggestions": [
            "Que fait l'Agent PV IA ?",
            "Quels champs sont extraits d'un PV ?",
            "Comment corriger un PV avant enregistrement ?",
        ],
    },
    {
        "starts_with": "/dashboard/ouverture/pv-ia",
        "title": "Pre-ouverture assistee par IA",
        "summary": "Cette vue permet au gestionnaire ouverture de revoir les PV extraits, completer les champs utiles et preparer la pre-ouverture du dossier.",
        "actions": [
            "consulter la liste des PV analyses",
            "relire les champs extraits automatiquement",
            "completer ou corriger les informations utiles",
            "controler les victimes et les vehicules detectes",
            "enregistrer la pre-ouverture",
        ],
        "suggestions": [
            "Que fait la pre-ouverture assistee par IA ?",
            "Comment preparer un dossier depuis un PV extrait ?",
            "Quels champs dois-je verifier avant la pre-ouverture ?",
        ],
    },
    {
        "starts_with": "/dashboard/judiciaire/reclamations",
        "title": "Reclamations judiciaires",
        "summary": "Cette vue sert a parcourir les files de reclamations et a ouvrir le controle detaille d'un dossier.",
        "actions": [
            "basculer entre les files remontees au superviseur, en attente, cloturees et contestees",
            "rechercher par numero de police, numero de sinistre, reference cabinet ou gestionnaire",
            "ajouter la date de survenance pour les recherches par police ou sinistre",
            "ouvrir la page de controle d'une reclamation",
        ],
        "suggestions": [
            "Explique les files de reclamations judiciaires",
            "Comment rechercher un dossier judiciaire ?",
            "Que fait l'action Controler ?",
        ],
    },
    {
        "starts_with": "/dashboard/avocat/reclamations",
        "title": "Suivi des reclamations avocat",
        "summary": "Cette vue sert a suivre les reclamations avocat, filtrer les dossiers et consulter la vue synthese.",
        "actions": [
            "basculer entre suivi des reclamations et vue synthese",
            "filtrer par numero de police, numero de sinistre, reference cabinet ou date de survenance",
            "consulter les statuts envoyee, traitee, rejetee, en attente de complement et cloturee",
            "ouvrir le detail d'une reclamation et envoyer un message",
            "demarrer la creation d'une nouvelle reclamation",
        ],
        "suggestions": [
            "Explique les statuts de mes reclamations",
            "Comment filtrer mes reclamations avocat ?",
            "Comment ouvrir une nouvelle reclamation ?",
        ],
    },
    {
        "starts_with": "/dashboard/medecin/reclamations",
        "title": "Suivi des reclamations medecin",
        "summary": "Cette vue sert a suivre les reclamations medecin, filtrer les dossiers et consulter la vue synthese.",
        "actions": [
            "basculer entre suivi des reclamations et vue synthese",
            "filtrer par numero de police, numero de sinistre, reference cabinet ou date de survenance",
            "consulter les statuts envoyee, traitee, rejetee, en attente de complement et cloturee",
            "ouvrir le detail d'une reclamation et envoyer un message",
            "demarrer la creation d'une nouvelle reclamation",
        ],
        "suggestions": [
            "Explique les statuts de mes reclamations medecin",
            "Comment filtrer mes reclamations medecin ?",
            "Comment ouvrir une nouvelle reclamation medecin ?",
        ],
    },
]


ROLE_CAPABILITIES = {
    "MANAGER": [
        "expliquer la gestion des utilisateurs",
        "decrire les roles et dashboards",
        "aider a comprendre l'affectation des droits",
        "guider sur la plateforme manager et la gestion des roles",
    ],
    "GESTIONNAIRE_JUDICIAIRE": [
        "resumer les reclamations a traiter",
        "expliquer les statuts et les commentaires de gestion",
        "guider sur les pieces et les notifications",
        "expliquer le controle detaille d'une reclamation",
    ],
    "GESTIONNAIRE_OUVERTURE": [
        "expliquer le dashboard ouverture",
        "aider a orienter l'utilisateur vers le bon ecran",
        "expliquer la pre-ouverture assistee par IA",
    ],
    "AVOCAT": [
        "expliquer le module Agent PV IA",
        "decrire les champs extraits depuis un PV",
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
        "Que puis-je faire sur le controle d'une reclamation ?",
    ],
    "GESTIONNAIRE_OUVERTURE": [
        "A quoi sert mon dashboard ouverture ?",
        "Que fait la pre-ouverture assistee par IA ?",
        "Quel ecran dois-je utiliser pour retrouver un dossier ?",
        "Explique le role ouverture dans l'application",
    ],
    "AVOCAT": [
        "Que fait l'Agent PV IA ?",
        "Quels champs sont extraits d'un PV ?",
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


def build_suggestions(
    roles: list[str],
    page_id: str | None,
    current_path: str | None = None,
) -> list[str]:
    suggestions: list[str] = []
    route_guide = resolve_route_guide(current_path)
    if route_guide:
        suggestions.extend(route_guide.get("suggestions", []))

    for role in roles:
        suggestions.extend(ROLE_SUGGESTIONS.get(role.upper(), []))

    current_view_label = resolve_current_view_label(page_id, current_path)
    if current_view_label:
        suggestions.append(f"Que puis-je faire sur {current_view_label} ?")

    ordered: list[str] = []
    for item in suggestions + DEFAULT_SUGGESTIONS:
        if item not in ordered:
            ordered.append(item)
    return ordered[:4]


def build_session_title(user: dict) -> str:
    dashboard = user.get("dashboard") or {}
    role = dashboard.get("role") or (user.get("roles") or ["Utilisateur"])[0]
    return f"Assistant IA - {role}"


def build_welcome_message(
    user: dict,
    page_id: str | None,
    current_path: str | None = None,
) -> str:
    full_name = " ".join(
        part for part in [user.get("first_name"), user.get("last_name")] if part
    ).strip() or user.get("username") or "Utilisateur"
    roles = ", ".join(user.get("roles") or ["UTILISATEUR"])
    page_label = resolve_current_view_label(page_id, current_path) or "votre espace courant"
    route_guide = resolve_route_guide(current_path)
    route_hint = ""
    if route_guide:
        route_hint = f"\n\nVue courante: {route_guide['summary']}"
    return (
        f"Bonjour {full_name}. Je suis votre assistant IA pour Bawaba de Sanlam.\n\n"
        f"Vous etes connecte avec le(s) role(s): {roles}.\n"
        f"Page actuelle: {page_label}.\n\n"
        "Je peux vous aider a comprendre l'application, les reclamations, les roles, "
        "les notifications et le bon parcours a suivre dans votre dashboard."
        f"{route_hint}"
    )


def build_system_prompt(context: dict) -> str:
    user = context["user"]
    roles = [role.upper() for role in user.get("roles", [])]
    page_id = context.get("page_id")
    current_path = context.get("current_path")
    page_label = resolve_current_view_label(page_id, current_path) or "Page non definie"
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
        "Modules connus de l'application:",
        *[f"- {item}" for item in PRODUCT_MODULES],
        "Contexte utilisateur live:",
        f"- utilisateur: {format_user_label(user)}",
        f"- roles: {', '.join(roles) if roles else 'aucun role remonte'}",
        f"- dashboard: {(user.get('dashboard') or {}).get('key') or 'non remonte'}",
        f"- homePage: {(user.get('dashboard') or {}).get('homePage') or 'non remonte'}",
        f"- page actuelle: {page_label}",
        f"- chemin courant: {current_path or 'non remonte'}",
        "Capacites a privilegier pour cet utilisateur:",
        *[f"- {item}" for item in capabilities],
        *render_contextual_knowledge(page_id, current_path),
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


def render_contextual_knowledge(page_id: str | None, current_path: str | None) -> list[str]:
    sections: list[str] = []
    route_guide = resolve_route_guide(current_path)
    page_guide = PAGE_GUIDES.get(page_id or "")

    if route_guide:
        sections.extend(render_guide_section("Vue courante connue:", route_guide))

    if page_guide and (
        not route_guide or page_guide["title"] != route_guide["title"]
    ):
        sections.extend(render_guide_section("Dashboard ou module de rattachement:", page_guide))

    return sections


def render_guide_section(header: str, guide: dict) -> list[str]:
    return [
        header,
        f"- titre: {guide['title']}",
        f"- resume: {guide['summary']}",
        "- actions ou usages a connaitre:",
        *[f"  - {item}" for item in guide.get("actions", [])],
    ]


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

    pv_extractions = context.get("pv_extractions")
    if pv_extractions:
        stats = pv_extractions.get("stats") or {}
        sections.extend(
            [
                "PV IA live:",
                f"- total: {stats.get('total', 0)}",
                f"- enCoursCount: {stats.get('enCoursCount', 0)}",
                f"- termineCount: {stats.get('termineCount', 0)}",
                f"- erreurCount: {stats.get('erreurCount', 0)}",
                f"- withVictimsCount: {stats.get('withVictimsCount', 0)}",
            ],
        )

        recent = pv_extractions.get("recent", [])
        if recent:
            sections.append("- PV recents visibles:")
            for row in recent:
                sections.append(
                    "  - "
                    f"id={row.get('id')} statut={row.get('statut')} "
                    f"documentName={row.get('documentName') or 'n/a'} "
                    f"numeroPolice={row.get('numeroPolice') or 'n/a'} "
                    f"ville={row.get('ville') or 'n/a'} "
                    f"victimes={row.get('nombreVictimes', 0)}",
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


def resolve_current_view_label(page_id: str | None, current_path: str | None) -> str | None:
    route_guide = resolve_route_guide(current_path)
    if route_guide:
        return route_guide["title"]
    return PAGE_LABELS.get(page_id or "")


def resolve_route_guide(current_path: str | None) -> dict | None:
    normalized_path = normalize_current_path(current_path)
    if not normalized_path:
        return None

    for guide in ROUTE_GUIDES:
        prefix = guide.get("starts_with")
        contains = guide.get("contains")
        if prefix and not normalized_path.startswith(prefix):
            continue
        if contains and contains not in normalized_path:
            continue
        return guide
    return None


def normalize_current_path(current_path: str | None) -> str:
    if not current_path:
        return ""

    normalized = current_path.split("?", 1)[0].strip().rstrip("/")
    if not normalized:
        return ""
    return normalized.lower()
