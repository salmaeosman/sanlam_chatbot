from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
import unicodedata


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
                "Numero de police d assurance principal quand le PV n en mentionne qu un seul "
                "ou quand un seul peut etre rattache de facon fiable. En cas de plusieurs "
                "vehicules avec plusieurs polices, renseigner aussi numero_police dans chaque "
                "objet vehicule."
            ),
        },
        "numero_pv": {
            "type": "string",
            "description": (
                "Numero du proces-verbal lui-meme, souvent note numero PV, N du PV "
                "ou عدد المحضر. Ne pas confondre avec le numero de police."
            ),
        },
        "date_survenance": {
            "type": "string",
            "description": "Date de l accident au format YYYY-MM-DD",
        },
        "heure_survenance": {
            "type": "string",
            "description": "Heure de l accident au format HH:MM ou HH:MM:SS",
        },
        "numero_permis_conducteur": {
            "type": "string",
            "description": (
                "Numero du permis de conduire du conducteur quand il est visible dans le PV"
            ),
        },
        "classe_permis_conducteur": {
            "type": "string",
            "description": (
                "Classe ou categorie du permis de conduire du conducteur, par exemple "
                "A, B, C, D ou categorie equivalente"
            ),
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
                    "cin": {
                        "type": "string",
                        "description": (
                            "Numero de CIN ou numero de la carte d identite nationale "
                            "de la victime, quand il est present dans le PV"
                        ),
                    },
                    "etat_apres_accident": {
                        "type": "string",
                        "description": (
                            "Etat de la victime apres l accident en francais, par exemple "
                            "Blessee, Decedee, Indemne"
                        ),
                    },
                    "qualite_victime": {
                        "type": "string",
                        "description": (
                            "Qualite de la victime en francais, par exemple Pieton, "
                            "Passager, Conducteur"
                        ),
                    },
                    "date_naissance": {
                        "type": "string",
                        "description": (
                            "Date de naissance de la victime au format YYYY-MM-DD quand elle "
                            "est visible dans le PV"
                        ),
                    },
                    "telephone": {
                        "type": "string",
                        "description": (
                            "Numero de telephone de la victime quand il est visible dans le PV"
                        ),
                    },
                    "itt": {
                        "type": "string",
                        "description": (
                            "Duree de l ITT de la victime en jours, par exemple 30 pour 30 jours"
                        ),
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
                    "compagnie_assurance": {
                        "type": "string",
                        "description": (
                            "Nom de la compagnie d assurance rattachee a ce vehicule quand elle "
                            "est visible dans le PV, par exemple Saham Assurance, Sanlam "
                            "ou une compagnie adverse"
                        ),
                    },
                    "numero_police": {
                        "type": "string",
                        "description": (
                            "Numero de police d assurance rattache a ce vehicule quand il est "
                            "visible dans le PV"
                        ),
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

_ARABIC_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_CIN_TOKEN_PATTERN = re.compile(r"(?i)([A-Z]{1,3}\s*[-/]?\s*\d{4,12}|\d{5,12})")
_TIME_TOKEN_PATTERN = re.compile(r"(?<!\d)(\d{1,2})[:hH](\d{2})(?::(\d{2}))?(?!\d)")
_DATE_YMD_PATTERN = re.compile(r"(?<!\d)(\d{4})[\/.\-](\d{1,2})[\/.\-](\d{1,2})(?!\d)")
_DATE_DMY_PATTERN = re.compile(r"(?<!\d)(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{4})(?!\d)")
_DATE_DMY_2Y_PATTERN = re.compile(r"(?<!\d)(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2})(?!\d)")
_CIN_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\bc\.?\s*i\.?\s*n\.?\b)"
    r"|(?:\bnum(?:ero)?\b)"
    r"|(?:\bn[°ºo]\b)"
    r"|(?:carte\s+d['’]?identit(?:e|é)\s+nationale)"
    r"|(?:national\s+identity\s+card)"
    r"|(?:رقم\s*)?بطاقة\s*التعريف\s*الوطنية"
)
_POLICY_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\bnumero\s+de\s+police\b)"
    r"|(?:\bn[°ºo]\s*de\s*police\b)"
    r"|(?:\bpolice\s+d['’]?assurance\b)"
    r"|(?:\bpolicy\s+number\b)"
    r"|(?:رقم\s*بوليصة(?:\s*التأمين)?)"
    r"|(?:رقم\s*الوثيقة)"
)
_PERMIT_NUMBER_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\bnumero\s+du\s+permis\b)"
    r"|(?:\bnumero\s+de\s+permis\b)"
    r"|(?:\bn[°ºo]\s*du\s*permis\b)"
    r"|(?:\bn[°ºo]\s*de\s*permis\b)"
    r"|(?:\bpermis\s+de\s+conduire\b)"
    r"|(?:\bdriver'?s?\s+license\s+number\b)"
    r"|(?:رقم\s*رخصة\s*السياقة)"
    r"|(?:رقم\s*الرخصة)"
)
_PERMIT_CLASS_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\bclasse\s+du\s+permis\b)"
    r"|(?:\bcategorie\s+du\s+permis\b)"
    r"|(?:\bclasse\s+permis\b)"
    r"|(?:\bcategorie\s+permis\b)"
    r"|(?:\bpermis\s+classe\b)"
    r"|(?:\bpermis\s+categorie\b)"
    r"|(?:صنف\s*رخصة\s*السياقة)"
    r"|(?:فئة\s*رخصة\s*السياقة)"
    r"|(?:صنف\s*الرخصة)"
    r"|(?:فئة\s*الرخصة)"
)
_INSURANCE_COMPANY_PREFIX_PATTERN = re.compile(
    r"(?i)^\s*(?:"
    r"compagnie\s+d['’]?assurance"
    r"|compagnie\s+adverse"
    r"|assure(?:e|s)?\s+par"
    r"|insured\s+by"
    r"|insurance\s+company"
    r"|compagnie"
    r"|شركة\s*التأمين"
    r"|مؤسسة\s*التأمين"
    r")\s*[:\-]?\s*"
)
_PHONE_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\btel(?:ephone)?\.?\b)"
    r"|(?:\bmobile\b)"
    r"|(?:\bgsm\b)"
    r"|(?:\bnumero\s+de\s+telephone\b)"
    r"|(?:\bn[°ºo]\s*de\s*telephone\b)"
    r"|(?:رقم\s*الهاتف)"
    r"|(?:الهاتف)"
    r"|(?:الجوال)"
)
_BIRTH_DATE_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\bdate\s+de\s+naissance\b)"
    r"|(?:\bdate\s+naissance\b)"
    r"|(?:\bnee?\s+le\b)"
    r"|(?:\bne[eé]\s+le\b)"
    r"|(?:\bnaissance\b)"
    r"|(?:تاريخ\s+الازدياد)"
    r"|(?:تاريخ\s+الميلاد)"
    r"|(?:ازدياد)"
    r"|(?:ميلاد)"
)
_ITT_LABEL_PATTERN = re.compile(
    r"(?i)"
    r"(?:\bitt\b)"
    r"|(?:\bincapacite\s+temporaire\s+de\s+travail\b)"
    r"|(?:\bincapacite\s+temporaire\b)"
    r"|(?:\bjours?\b)"
    r"|(?:\bjrs?\b)"
    r"|(?:\bdays?\b)"
    r"|(?:عجز(?:\s*مؤقت)?(?:\s*عن\s*العمل)?)"
    r"|(?:ايام)"
    r"|(?:أيام)"
    r"|(?:يوما?)"
)
_SUMMARY_VICTIM_BLOCK_START_PATTERN = re.compile(
    r"(?i)(?:victime|victim|الضحية|المصاب(?:ة)?)\s*(\d+)?\s*[:\-]"
)
_SUMMARY_VICTIM_COUNT_PATTERNS = (
    re.compile(r"(?i)\bnombre\s+de\s+victimes?\s*[:\-]?\s*(\d{1,2})\b"),
    re.compile(r"(?i)\btotal\s+de\s+victimes?\s*[:\-]?\s*(\d{1,2})\b"),
    re.compile(r"(?i)\b(\d{1,2})\s+victimes?\b"),
    re.compile(r"(?i)(?:عدد|مجموع)\s+(?:الضحايا|المصابين)\s*[:\-]?\s*(\d{1,2})\b"),
)
_SUMMARY_VICTIM_COUNT_WORDS = {
    "une": 1,
    "un": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
}
_SUMMARY_NAME_PATTERNS = (
    re.compile(r"(?i)\bnom\b\s*[:\-]\s*([^\n,;|]+)"),
    re.compile(r"(?i)الاسم(?:\s+العائلي)?\s*[:\-]\s*([^\n,;|]+)"),
)
_SUMMARY_FIRST_NAME_PATTERNS = (
    re.compile(r"(?i)\bpr[eé]nom\b\s*[:\-]\s*([^\n,;|]+)"),
    re.compile(r"(?i)الاسم\s+الشخصي\s*[:\-]\s*([^\n,;|]+)"),
)
_SUMMARY_BIRTH_DATE_PATTERNS = (
    re.compile(
        r"(?i)(?:date\s+de\s+naissance|date\s+naissance|n[ée]e?\s+le|ne[eé]\s+le)\s*[:\-]?\s*([^\n,;|]+)"
    ),
    re.compile(
        r"(?i)(?:تاريخ\s+الازدياد|تاريخ\s+الميلاد)\s*[:\-]?\s*([^\n,;|]+)"
    ),
)
_SUMMARY_PHONE_PATTERNS = (
    re.compile(
        r"(?i)(?:tel(?:ephone)?\.?|numero\s+de\s+telephone|n[°ºo]\s*de\s*telephone)\s*[:\-]?\s*([+()\d][\d\s()./-]{6,24})"
    ),
    re.compile(
        r"(?i)(?:رقم\s*الهاتف|الهاتف|الجوال)\s*[:\-]?\s*([+()\d][\d\s()./-]{6,24})"
    ),
)
_SUMMARY_ITT_PATTERNS = (
    re.compile(
        r"(?i)(?:itt|incapacite\s+temporaire(?:\s+de\s+travail)?)\s*[:\-]?\s*([^\n,;|]+)"
    ),
    re.compile(
        r"(?i)(?:عجز(?:\s*مؤقت)?(?:\s*عن\s*العمل)?)\s*[:\-]?\s*([^\n,;|]+)"
    ),
)
_SUMMARY_FULL_NAME_PATTERNS = (
    re.compile(
        r"(?is)(?:victime|victim)\s*\d*\s*[:\-]\s*([^\n;,]+)"
    ),
    re.compile(
        r"(?is)(?:الضحية|المصاب(?:ة)?)\s*\d*\s*[:\-]\s*([^\n;,]+)"
    ),
)
_SUMMARY_STATE_PATTERNS = (
    (re.compile(r"(?i)\bd[eé]c[eé]d[eé]e?\b|\bmorte?\b|متوف(?:اة)?|وفاة"), "Decedee"),
    (re.compile(r"(?i)\bindemne\b|sans\s+blessure|غير\s+مصاب|سليم"), "Indemne"),
    (re.compile(r"(?i)\bbless[eé]e?\b|\bbless[eé]\b|مصاب(?:ة)?"), "Blessee"),
)
_SUMMARY_QUALITY_PATTERNS = (
    (re.compile(r"(?i)\bp[ié]eton(?:ne)?\b|راجل(?:ة)?"), "Pieton"),
    (re.compile(r"(?i)\bpassager(?:e)?\b|راكب(?:ة)?"), "Passager"),
    (re.compile(r"(?i)\bconduct(?:eur|rice)\b|سائق(?:ة)?"), "Conducteur"),
    (re.compile(r"(?i)\bmotocycliste\b|دراجة\s+نارية"), "Motocycliste"),
    (re.compile(r"(?i)\bcycliste\b|دراجة\s+هوائية"), "Cycliste"),
)
_SUMMARY_FIELD_STOP_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"n[ée]e?\s+le|ne[eé]\s+le|date\s+de\s+naissance|date\s+naissance|"
    r"cin|carte\s+d['’]?identit(?:e|é)\s+nationale|telephone|tel(?:ephone)?|"
    r"itt|p[ié]eton(?:ne)?|passager(?:e)?|conducteur(?:rice)?|"
    r"bless[eé]e?|d[eé]c[eé]d[eé]e?|indemne|"
    r"تاريخ\s+الازدياد|تاريخ\s+الميلاد|رقم\s*الهاتف|بطاقة\s*التعريف\s*الوطنية|"
    r"مصاب(?:ة)?|متوف(?:اة)?|سائق(?:ة)?|راكب(?:ة)?|راجل(?:ة)?)\b"
)


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


def normalize_cin_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _CIN_LABEL_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace(":", " ").replace(";", " ").replace("#", " ")
    cleaned = " ".join(cleaned.split()).strip()
    if not cleaned:
        return None

    match = _CIN_TOKEN_PATTERN.search(cleaned.upper())
    candidate = match.group(1) if match else cleaned
    normalized = re.sub(r"[^A-Z0-9]", "", candidate.upper())
    return normalized or None


def normalize_pv_number(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
    )
    normalized = " ".join(cleaned.split()).strip()
    return normalized or None


def normalize_policy_number(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _POLICY_LABEL_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace(":", " ").replace(";", " ").replace("#", " ")
    normalized = " ".join(cleaned.split()).strip()
    return normalized or None


def normalize_time_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    match = _TIME_TOKEN_PATTERN.search(cleaned)
    if not match:
        return None

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3)) if match.group(3) is not None else None

    if hours > 23 or minutes > 59 or (seconds is not None and seconds > 59):
        return None

    return f"{hours:02d}:{minutes:02d}" + (f":{seconds:02d}" if seconds is not None else "")


def normalize_driver_permit_number(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _PERMIT_NUMBER_LABEL_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace(":", " ").replace(";", " ").replace("#", " ")
    normalized = " ".join(cleaned.split()).strip()
    return normalized or None


def normalize_driver_permit_class(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _PERMIT_CLASS_LABEL_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace(":", " ").replace(";", " ").replace("#", " ")
    normalized = " ".join(cleaned.split()).strip()
    return normalized.upper() or None


def normalize_insurance_company(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _INSURANCE_COMPANY_PREFIX_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace(":", " ").replace(";", " ").replace("#", " ")
    cleaned = re.sub(r"\s*\(([^)]*)\)\s*$", "", cleaned).strip()
    normalized = " ".join(cleaned.split()).strip()
    if not normalized:
        return None

    normalized_key = normalized.casefold()
    if "saham" in normalized_key:
        return "Saham Assurance"
    if "sanlam" in normalized_key:
        return "Sanlam"

    return normalized


def normalize_birth_date(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _BIRTH_DATE_LABEL_PATTERN.sub(" ", cleaned)
    cleaned = cleaned.replace(":", " ").replace(";", " ").replace(",", " ")
    cleaned = " ".join(cleaned.split()).strip()
    if not cleaned:
        return None

    match = _DATE_YMD_PATTERN.search(cleaned)
    if match:
        year, month, day = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    else:
        match = _DATE_DMY_PATTERN.search(cleaned)
        if match:
            day, month, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        else:
            match = _DATE_DMY_2Y_PATTERN.search(cleaned)
            if not match:
                return None
            day = int(match.group(1))
            month = int(match.group(2))
            short_year = int(match.group(3))
            year = 1900 + short_year if short_year >= 30 else 2000 + short_year

    try:
        normalized_date = date(year, month, day)
    except ValueError:
        return None

    return normalized_date.isoformat()


def normalize_phone_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _PHONE_LABEL_PATTERN.sub(" ", cleaned)
    normalized = " ".join(cleaned.split()).strip()
    if not normalized:
        return None

    match = re.search(r"(\+?\d(?:[\s()./-]*\d){7,17})", normalized)
    candidate = match.group(1) if match else normalized
    has_plus = candidate.lstrip().startswith("+")
    digits_only = re.sub(r"\D", "", candidate)

    if len(digits_only) < 8 or len(digits_only) > 15:
        return None

    return f"+{digits_only}" if has_plus else digits_only


def normalize_itt_days_value(value: object) -> str | None:
    if value is None:
        return None

    if isinstance(value, int):
        return str(value) if value >= 0 else None

    if isinstance(value, float):
        if value.is_integer() and value >= 0:
            return str(int(value))
        return None

    if not isinstance(value, str):
        return None

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .strip()
    )
    if not cleaned:
        return None

    cleaned = _ITT_LABEL_PATTERN.sub(" ", cleaned)
    normalized = " ".join(cleaned.split()).strip()
    if not normalized:
        return None

    match = re.search(r"(?<!\d)(\d{1,4})(?!\d)", normalized)
    if not match:
        return None

    days = int(match.group(1))
    return str(days) if days >= 0 else None


def _is_missing_scalar_value(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _collapse_spaces(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_identity_token(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = _collapse_spaces(
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
    )
    if not cleaned:
        return None

    normalized = unicodedata.normalize("NFKD", cleaned.casefold())
    without_diacritics = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    compact = re.sub(r"[^\w\u0600-\u06FF]+", " ", without_diacritics, flags=re.UNICODE)
    return _collapse_spaces(compact) or None


def _pick_preferred_string_value(*values: str) -> str:
    candidates = [
        _collapse_spaces(value)
        for value in values
        if isinstance(value, str) and _collapse_spaces(value)
    ]
    if not candidates:
        return ""

    return min(
        candidates,
        key=lambda candidate: (
            -len(_normalize_identity_token(candidate) or ""),
            -len(candidate),
            candidate.casefold(),
        ),
    )


def _merge_victim_records(existing: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
    merged = dict(existing)

    for key, incoming_value in incoming.items():
        existing_value = merged.get(key)

        if _is_missing_scalar_value(existing_value):
            if not _is_missing_scalar_value(incoming_value):
                merged[key] = incoming_value
            continue

        if _is_missing_scalar_value(incoming_value):
            continue

        if isinstance(existing_value, str) and isinstance(incoming_value, str):
            merged[key] = _pick_preferred_string_value(existing_value, incoming_value)

    return merged


def _build_victim_identity_keys(candidate: dict[str, object]) -> list[str]:
    cin_keys = (
        "cin",
        "numero_cin",
        "numeroCin",
        "numero_carte_nationale",
        "numeroCarteNationale",
        "carte_nationale",
        "carteNationale",
        "national_id",
        "nationalId",
        "identity_card_number",
        "identityCardNumber",
    )
    cin_value = next(
        (
            normalized
            for key in cin_keys
            if (normalized := normalize_cin_value(candidate.get(key))) is not None
        ),
        None,
    )

    nom_fr = _normalize_identity_token(candidate.get("nom_fr") or candidate.get("nomFr") or candidate.get("nom"))
    prenom_fr = _normalize_identity_token(
        candidate.get("prenom_fr") or candidate.get("prenomFr") or candidate.get("prenom")
    )
    nom_ar = _normalize_identity_token(candidate.get("nom_ar") or candidate.get("nomAr"))
    prenom_ar = _normalize_identity_token(candidate.get("prenom_ar") or candidate.get("prenomAr"))
    birth_date = normalize_birth_date(
        candidate.get("date_naissance")
        or candidate.get("dateNaissance")
        or candidate.get("date_de_naissance")
        or candidate.get("dateDeNaissance")
    )
    phone_number = normalize_phone_value(
        candidate.get("telephone")
        or candidate.get("numero_telephone")
        or candidate.get("numeroTelephone")
        or candidate.get("phone")
        or candidate.get("phone_number")
        or candidate.get("phoneNumber")
    )

    keys: list[str] = []
    if cin_value:
        keys.append(f"cin:{cin_value}")
    if nom_fr and prenom_fr and birth_date:
        keys.append(f"fr-birth:{nom_fr}|{prenom_fr}|{birth_date}")
    if nom_ar and prenom_ar and birth_date:
        keys.append(f"ar-birth:{nom_ar}|{prenom_ar}|{birth_date}")
    if nom_fr and prenom_fr and phone_number:
        keys.append(f"fr-phone:{nom_fr}|{prenom_fr}|{phone_number}")
    if nom_ar and prenom_ar and phone_number:
        keys.append(f"ar-phone:{nom_ar}|{prenom_ar}|{phone_number}")
    if nom_fr and prenom_fr:
        keys.append(f"fr-name:{nom_fr}|{prenom_fr}")
    if nom_ar and prenom_ar:
        keys.append(f"ar-name:{nom_ar}|{prenom_ar}")
    if phone_number and birth_date:
        keys.append(f"phone-birth:{phone_number}|{birth_date}")

    return list(dict.fromkeys(keys))


def _deduplicate_victims(victims: list[object]) -> list[object]:
    deduplicated_victims: list[object] = []
    identity_index: dict[str, int] = {}

    for item in victims:
        if not isinstance(item, dict):
            deduplicated_victims.append(item)
            continue

        identity_keys = _build_victim_identity_keys(item)
        matched_index = next(
            (identity_index[key] for key in identity_keys if key in identity_index),
            None,
        )

        if matched_index is None:
            deduplicated_victims.append(dict(item))
            matched_index = len(deduplicated_victims) - 1
        else:
            existing_item = deduplicated_victims[matched_index]
            if isinstance(existing_item, dict):
                deduplicated_victims[matched_index] = _merge_victim_records(existing_item, item)
            else:
                deduplicated_victims[matched_index] = item

        merged_item = deduplicated_victims[matched_index]
        if isinstance(merged_item, dict):
            for key in _build_victim_identity_keys(merged_item):
                identity_index[key] = matched_index

    return deduplicated_victims


def _normalize_summary_text(value: object) -> str:
    if not isinstance(value, str):
        return ""

    cleaned = (
        value.translate(_ARABIC_DIGIT_TRANSLATION)
        .replace("\u200f", " ")
        .replace("\u200e", " ")
        .replace("\xa0", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_summary_victim_count(summary_text: str) -> int:
    normalized_text = _normalize_summary_text(summary_text)
    if not normalized_text:
        return 0

    counts: list[int] = []
    for pattern in _SUMMARY_VICTIM_COUNT_PATTERNS:
        for match in pattern.finditer(normalized_text):
            for group in match.groups():
                if group and group.isdigit():
                    counts.append(int(group))

    lower_text = normalized_text.casefold()
    for word, count in _SUMMARY_VICTIM_COUNT_WORDS.items():
        if re.search(rf"\b{word}\s+victimes?\b", lower_text):
            counts.append(count)

    block_indexes = [
        int(match.group(1))
        for match in _SUMMARY_VICTIM_BLOCK_START_PATTERN.finditer(normalized_text)
        if match.group(1) and match.group(1).isdigit()
    ]
    if block_indexes:
        counts.append(max(block_indexes))

    return max(counts, default=0)


def _extract_summary_named_value(patterns: tuple[re.Pattern[str], ...], text: str) -> str | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            candidate = _collapse_spaces(match.group(1)).strip(" ,;:-")
            if candidate:
                return candidate
    return None


def _split_full_name_candidate(value: str) -> tuple[str | None, str | None]:
    cleaned = _collapse_spaces(value.strip(" ,;:-"))
    if not cleaned:
        return None, None

    cleaned = re.sub(r"\([^)]*\)", " ", cleaned)
    stop_match = _SUMMARY_FIELD_STOP_PATTERN.search(cleaned)
    if stop_match:
        cleaned = cleaned[: stop_match.start()]
    cleaned = _collapse_spaces(cleaned.strip(" ,;:-"))
    if not cleaned:
        return None, None

    tokens = [token for token in re.split(r"\s+", cleaned) if token]
    if len(tokens) < 2 or len(tokens) > 5:
        return None, None
    if any(re.search(r"\d", token) for token in tokens):
        return None, None

    first_token = tokens[0]
    remaining_tokens = tokens[1:]
    if first_token == first_token.upper() and first_token != first_token.lower():
        return first_token, " ".join(remaining_tokens)

    return " ".join(remaining_tokens), first_token


def _extract_state_from_summary_block(block: str) -> str | None:
    for pattern, value in _SUMMARY_STATE_PATTERNS:
        if pattern.search(block):
            return value
    return None


def _extract_quality_from_summary_block(block: str) -> str | None:
    for pattern, value in _SUMMARY_QUALITY_PATTERNS:
        if pattern.search(block):
            return value
    return None


def _extract_victim_candidate_from_summary_block(block: str) -> dict[str, object] | None:
    candidate: dict[str, object] = {}

    nom = _extract_summary_named_value(_SUMMARY_NAME_PATTERNS, block)
    prenom = _extract_summary_named_value(_SUMMARY_FIRST_NAME_PATTERNS, block)
    if not nom or not prenom:
        for pattern in _SUMMARY_FULL_NAME_PATTERNS:
            match = pattern.search(block)
            if not match:
                continue
            inferred_nom, inferred_prenom = _split_full_name_candidate(match.group(1))
            nom = nom or inferred_nom
            prenom = prenom or inferred_prenom
            if nom and prenom:
                break

    if nom:
        candidate["nom_fr"] = nom
    if prenom:
        candidate["prenom_fr"] = prenom

    if (cin_value := normalize_cin_value(block)) is not None:
        candidate["cin"] = cin_value

    birth_date_source = _extract_summary_named_value(_SUMMARY_BIRTH_DATE_PATTERNS, block) or block
    if (birth_date := normalize_birth_date(birth_date_source)) is not None:
        candidate["date_naissance"] = birth_date

    phone_source = _extract_summary_named_value(_SUMMARY_PHONE_PATTERNS, block) or block
    if (phone_number := normalize_phone_value(phone_source)) is not None:
        candidate["telephone"] = phone_number

    itt_source = _extract_summary_named_value(_SUMMARY_ITT_PATTERNS, block) or block
    if (itt_days := normalize_itt_days_value(itt_source)) is not None:
        candidate["itt"] = itt_days

    if (state := _extract_state_from_summary_block(block)) is not None:
        candidate["etat_apres_accident"] = state

    if (quality := _extract_quality_from_summary_block(block)) is not None:
        candidate["qualite_victime"] = quality

    return candidate or None


def _extract_victim_candidates_from_summary(summary_text: str) -> list[dict[str, object]]:
    normalized_text = _normalize_summary_text(summary_text)
    if not normalized_text:
        return []

    matches = list(_SUMMARY_VICTIM_BLOCK_START_PATTERN.finditer(normalized_text))
    if not matches:
        return []

    victims: list[dict[str, object]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized_text)
        block = normalized_text[start:end].strip(" \n;,.")
        if not block:
            continue

        candidate = _extract_victim_candidate_from_summary_block(block)
        if candidate:
            victims.append(candidate)

    return victims


def _normalize_victim_candidate(candidate: dict[str, object]) -> dict[str, object]:
    normalized_candidate = dict(candidate)
    cin_keys = (
        "cin",
        "numero_cin",
        "numeroCin",
        "numero_carte_nationale",
        "numeroCarteNationale",
        "carte_nationale",
        "carteNationale",
        "national_id",
        "nationalId",
        "identity_card_number",
        "identityCardNumber",
    )
    cin_value = next(
        (
            normalized
            for key in cin_keys
            if (normalized := normalize_cin_value(normalized_candidate.get(key))) is not None
        ),
        None,
    )
    if cin_value:
        normalized_candidate["cin"] = cin_value
    else:
        normalized_candidate.pop("cin", None)

    normalized_birth_date = normalize_birth_date(
        normalized_candidate.get("date_naissance")
        or normalized_candidate.get("dateNaissance")
        or normalized_candidate.get("date_de_naissance")
        or normalized_candidate.get("dateDeNaissance")
    )
    if normalized_birth_date:
        normalized_candidate["date_naissance"] = normalized_birth_date
    else:
        normalized_candidate.pop("date_naissance", None)

    normalized_phone_number = normalize_phone_value(
        normalized_candidate.get("telephone")
        or normalized_candidate.get("numero_telephone")
        or normalized_candidate.get("numeroTelephone")
        or normalized_candidate.get("phone")
        or normalized_candidate.get("phone_number")
        or normalized_candidate.get("phoneNumber")
    )
    if normalized_phone_number:
        normalized_candidate["telephone"] = normalized_phone_number
    else:
        normalized_candidate.pop("telephone", None)

    normalized_itt = normalize_itt_days_value(normalized_candidate.get("itt"))
    if normalized_itt:
        normalized_candidate["itt"] = normalized_itt
    else:
        normalized_candidate.pop("itt", None)

    return normalized_candidate


def _find_matching_victim_index(victims: list[object], candidate: dict[str, object]) -> int | None:
    candidate_keys = set(_build_victim_identity_keys(candidate))
    if not candidate_keys:
        return None

    for index, item in enumerate(victims):
        if not isinstance(item, dict):
            continue
        if candidate_keys.intersection(_build_victim_identity_keys(item)):
            return index

    return None


def _can_append_summary_victim(candidate: dict[str, object]) -> bool:
    if _build_victim_identity_keys(candidate):
        return True
    return bool(candidate.get("nom_fr") and candidate.get("prenom_fr"))


def _enrich_victims_from_summaries(
    payload: dict[str, object],
    victims: list[object],
) -> tuple[list[object], int]:
    summary_texts = [
        payload.get("texte_brut_fr"),
        payload.get("texte_brut_ar"),
        payload.get("texteBrut"),
        payload.get("texteBrutAr"),
    ]

    normalized_victims = [dict(item) if isinstance(item, dict) else item for item in victims]
    summary_count = 0
    parsed_summary_victims: list[dict[str, object]] = []

    for summary_text in summary_texts:
        if not isinstance(summary_text, str) or not summary_text.strip():
            continue
        summary_count = max(summary_count, _extract_summary_victim_count(summary_text))
        parsed_summary_victims.extend(_extract_victim_candidates_from_summary(summary_text))

    summary_count = max(summary_count, len(parsed_summary_victims))

    for index, raw_candidate in enumerate(parsed_summary_victims):
        candidate = _normalize_victim_candidate(raw_candidate)
        if not candidate:
            continue

        matched_index = _find_matching_victim_index(normalized_victims, candidate)
        if matched_index is not None:
            existing_item = normalized_victims[matched_index]
            if isinstance(existing_item, dict):
                normalized_victims[matched_index] = _merge_victim_records(existing_item, candidate)
            continue

        if index < len(normalized_victims):
            existing_item = normalized_victims[index]
            if isinstance(existing_item, dict):
                existing_keys = _build_victim_identity_keys(existing_item)
                candidate_keys = _build_victim_identity_keys(candidate)
                if not candidate_keys or not existing_keys:
                    normalized_victims[index] = _merge_victim_records(existing_item, candidate)
                    continue

        if _can_append_summary_victim(candidate):
            normalized_victims.append(candidate)

    deduplicated_victims = _deduplicate_victims(normalized_victims)
    return deduplicated_victims, max(summary_count, len(deduplicated_victims))


def normalize_extracted_pv_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload

    next_payload = dict(payload)

    if (normalized_policy_number := normalize_policy_number(payload.get("numero_police"))) is not None:
        next_payload["numero_police"] = normalized_policy_number
    else:
        next_payload.pop("numero_police", None)

    if (normalized_pv_number := normalize_pv_number(payload.get("numero_pv"))) is not None:
        next_payload["numero_pv"] = normalized_pv_number

    normalized_time = normalize_time_value(payload.get("heure_survenance"))
    if normalized_time is not None:
        next_payload["heure_survenance"] = normalized_time

    normalized_permit_number = normalize_driver_permit_number(
        payload.get("numero_permis_conducteur")
        or payload.get("numeroPermisConducteur")
        or payload.get("numero_permis")
        or payload.get("numeroPermis")
    )
    if normalized_permit_number is not None:
        next_payload["numero_permis_conducteur"] = normalized_permit_number

    normalized_permit_class = normalize_driver_permit_class(
        payload.get("classe_permis_conducteur")
        or payload.get("classePermisConducteur")
        or payload.get("categorie_permis_conducteur")
        or payload.get("categoriePermisConducteur")
        or payload.get("classe_permis")
        or payload.get("categorie_permis")
    )
    if normalized_permit_class is not None:
        next_payload["classe_permis_conducteur"] = normalized_permit_class

    vehicules = payload.get("vehicules")
    if isinstance(vehicules, list):
        normalized_vehicules = []
        vehicle_policy_numbers: list[str] = []

        for item in vehicules:
            if not isinstance(item, dict):
                normalized_vehicules.append(item)
                continue

            candidate = dict(item)
            normalized_vehicle_policy = normalize_policy_number(
                candidate.get("numero_police")
                or candidate.get("numeroPolice")
            )
            normalized_insurance_company = normalize_insurance_company(
                candidate.get("compagnie_assurance")
                or candidate.get("compagnieAssurance")
                or candidate.get("compagnie")
                or candidate.get("assurance")
            )

            if normalized_vehicle_policy:
                candidate["numero_police"] = normalized_vehicle_policy
                vehicle_policy_numbers.append(normalized_vehicle_policy)
            else:
                candidate.pop("numero_police", None)

            if normalized_insurance_company:
                candidate["compagnie_assurance"] = normalized_insurance_company
            else:
                candidate.pop("compagnie_assurance", None)

            normalized_vehicules.append(candidate)

        next_payload["vehicules"] = normalized_vehicules

        if "numero_police" not in next_payload:
            unique_vehicle_policy_numbers = list(dict.fromkeys(vehicle_policy_numbers))
            if len(unique_vehicle_policy_numbers) == 1:
                next_payload["numero_police"] = unique_vehicle_policy_numbers[0]

    victimes = payload.get("victimes")
    if not isinstance(victimes, list):
        return next_payload

    normalized_victimes = []

    for item in victimes:
        if not isinstance(item, dict):
            normalized_victimes.append(item)
            continue

        normalized_victimes.append(_normalize_victim_candidate(item))

    enriched_victimes, normalized_count = _enrich_victims_from_summaries(next_payload, normalized_victimes)
    next_payload["victimes"] = enriched_victimes
    next_payload["nombre_victimes"] = normalized_count
    return next_payload
