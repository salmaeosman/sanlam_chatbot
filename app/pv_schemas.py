from __future__ import annotations

from dataclasses import dataclass


PV_ALLOWED_ROLES = {
    "AVOCAT",
    "GESTIONNAIRE_OUVERTURE",
    "MANAGER",
}

PV_ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}

PV_EXTRACTION_RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "numero_police": {
            "type": "string",
            "description": (
                "Numero de police d assurance. Ne pas confondre avec le numero du PV."
            ),
        },
        "date_survenance": {
            "type": "string",
            "description": "Date de l accident au format YYYY-MM-DD",
        },
        "ville_fr": {
            "type": "string",
            "description": "Ville de l accident en francais",
        },
        "ville_ar": {
            "type": "string",
            "description": "Ville de l accident en arabe",
        },
        "adresse_fr": {
            "type": "string",
            "description": "Adresse exacte de l accident en francais",
        },
        "adresse_ar": {
            "type": "string",
            "description": "Adresse exacte de l accident en arabe",
        },
        "victimes": {
            "type": "array",
            "description": "Liste des victimes avec nom et prenom en francais et arabe",
            "items": {
                "type": "object",
                "properties": {
                    "nom_fr": {
                        "type": "string",
                        "description": "Nom de famille en francais",
                    },
                    "nom_ar": {
                        "type": "string",
                        "description": "Nom de famille en arabe",
                    },
                    "prenom_fr": {
                        "type": "string",
                        "description": "Prenom en francais",
                    },
                    "prenom_ar": {
                        "type": "string",
                        "description": "Prenom en arabe",
                    },
                },
                "required": ["nom_fr", "prenom_fr"],
            },
        },
        "nombre_victimes": {
            "type": "integer",
            "description": "Nombre total de victimes",
        },
        "vehicules": {
            "type": "array",
            "description": "Liste des vehicules impliques",
            "items": {
                "type": "object",
                "properties": {
                    "type_fr": {
                        "type": "string",
                        "description": "Type du vehicule en francais",
                    },
                    "type_ar": {
                        "type": "string",
                        "description": "Type du vehicule en arabe",
                    },
                    "marque": {
                        "type": "string",
                        "description": "Marque du vehicule",
                    },
                    "plaque": {
                        "type": "string",
                        "description": "Plaque d immatriculation",
                    },
                },
                "required": ["type_fr", "marque", "plaque"],
            },
        },
        "texte_brut_fr": {
            "type": "string",
            "description": "Resume textuel du contenu en francais",
        },
        "texte_brut_ar": {
            "type": "string",
            "description": "Resume textuel du contenu en arabe",
        },
    },
    "required": ["victimes", "vehicules"],
}


@dataclass(frozen=True, slots=True)
class NormalizedPvUpload:
    original_name: str
    mime_type: str
    size: int
    buffer: bytes


def normalize_role_title(role: str | None) -> str:
    return str(role or "").strip().replace(" ", "_").upper()


def sanitize_displayed_file_name(value: str) -> str:
    candidate = value.replace("\\", "/").split("/")[-1].strip()
    without_controls = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in candidate)
    normalized = " ".join(without_controls.split()).strip()
    return (normalized or "document")[:255]


def sniff_mime_type(buffer: bytes) -> str | None:
    if buffer.startswith(b"%PDF-"):
        return "application/pdf"

    if buffer.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    if buffer.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    if len(buffer) >= 12 and buffer[:4] == b"RIFF" and buffer[8:12] == b"WEBP":
        return "image/webp"

    return None


def normalize_mime_type(value: str | None) -> str:
    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()
