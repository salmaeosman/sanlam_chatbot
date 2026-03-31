from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings

try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    PdfReader = None


ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u0600-\u06FF]+")
WHITESPACE_PATTERN = re.compile(r"\s+")

STOPWORDS = {
    "a",
    "al",
    "au",
    "aux",
    "avec",
    "ce",
    "ces",
    "cette",
    "dans",
    "de",
    "des",
    "du",
    "elle",
    "en",
    "est",
    "et",
    "il",
    "je",
    "la",
    "le",
    "les",
    "leur",
    "leurs",
    "ma",
    "mes",
    "mon",
    "ne",
    "nos",
    "nous",
    "ou",
    "par",
    "pas",
    "pour",
    "que",
    "quel",
    "quelle",
    "quelles",
    "quels",
    "qui",
    "sa",
    "se",
    "ses",
    "son",
    "sur",
    "ta",
    "te",
    "tes",
    "ton",
    "un",
    "une",
    "vos",
    "vous",
    "ما",
    "ماذا",
    "من",
    "في",
    "على",
    "عن",
    "الى",
    "إلى",
    "او",
    "أو",
    "ثم",
    "مع",
    "هذا",
    "هذه",
    "ذلك",
    "تلك",
    "هو",
    "هي",
    "كما",
    "هل",
    "كل",
}

ALIAS_GROUPS = [
    {"dahir", "ظهير"},
    {"loi", "law", "قانون"},
    {"article", "articles", "مادة", "المادة"},
    {"compensation", "compensations", "indemnisation", "indemnisations", "تعويض", "التعويض"},
    {"victime", "victimes", "blesse", "blesses", "مصاب", "المصاب", "المصابين"},
    {"accident", "accidents", "حادث", "الحادث", "الحادثة", "حوادث"},
    {"circulation", "route", "vehicule", "vehicules", "moteur", "مركبة", "مركبات", "محرك"},
    {"assurance", "assureur", "تامين", "التامين"},
    {"responsabilite", "responsable", "مسؤولية", "المسؤولية"},
    {"frais", "depenses", "depense", "remboursement", "remboursements", "مصاريف", "نفقات", "استرجاع"},
    {"soins", "traitement", "hospitalisation", "علاج", "الاستشفاء", "استشفاء"},
    {"invalidite", "incapacite", "incapacite_temporaire", "عجز", "العجز"},
    {"temporaire", "مؤقت"},
    {"permanent", "permanente", "دائم"},
    {"deces", "mort", "funerailles", "وفاة", "جنازة", "الجثمان"},
    {"salaire", "revenu", "gain", "remuneration", "اجر", "الأجر", "كسب", "الكسب", "مهني"},
    {"retraite", "تقاعد"},
    {"profession", "metier", "مهنة"},
    {"etude", "etudes", "دراسة", "الدراسة"},
    {"prejudice", "dommage", "douleur", "ضرر", "الألم", "المعنوي"},
]

REFERENCE_HINT_TOKENS = {
    "dahir",
    "ظهير",
    "loi",
    "law",
    "قانون",
    "article",
    "articles",
    "مادة",
    "المادة",
}

SUMMARY_HINT_TOKENS = {
    "resume",
    "resumer",
    "summary",
    "summarize",
    "explique",
    "expliquer",
    "شرح",
    "اشرح",
    "لخص",
    "ملخص",
}

ARABIC_ARTICLE_ORDINALS = {
    1: "الماده الاولي",
    2: "الماده الثانيه",
    3: "الماده الثالثه",
    4: "الماده الرابعه",
    5: "الماده الخامسه",
    6: "الماده السادسه",
    7: "الماده السابعه",
    8: "الماده الثامنه",
    9: "الماده التاسعه",
    10: "الماده العاشره",
    11: "الماده الحاديه عشره",
    12: "الماده الثانيه عشره",
    13: "الماده الثالثه عشره",
    14: "الماده الرابعه عشره",
    15: "الماده الخامسه عشره",
    16: "الماده السادسه عشره",
    17: "الماده السابعه عشره",
    18: "الماده الثامنه عشره",
    19: "الماده التاسعه عشره",
    20: "الماده العشرون",
}


def normalize_reference_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.lower().replace("ـ", " ")
    normalized = ARABIC_DIACRITICS_PATTERN.sub("", normalized)
    replacements = {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source.lower(), target)
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"[^0-9a-z\u0600-\u06FF]+", " ", normalized)
    return WHITESPACE_PATTERN.sub(" ", normalized).strip()


def tokenize_reference_text(value: str) -> set[str]:
    tokens: set[str] = set()
    for token in TOKEN_PATTERN.findall(value):
        if token in STOPWORDS:
            continue
        if len(token) == 1 and not token.isdigit():
            continue
        tokens.add(token)
        tokens.update(_token_variants(token))
    return tokens


def _token_variants(token: str) -> set[str]:
    variants: set[str] = set()

    if token.isdigit():
        return variants

    if token.startswith("ال") and len(token) > 4:
        variants.add(token[2:])

    for suffix in ("ها", "هم", "هن", "كم", "نا", "ات", "ون", "ين", "ة", "ه"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            variants.add(token[: -len(suffix)])

    if token.endswith("s") and len(token) > 4:
        variants.add(token[:-1])
    if token.endswith("es") and len(token) > 5:
        variants.add(token[:-2])

    return {variant for variant in variants if variant and variant not in STOPWORDS}


def expand_reference_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for group in ALIAS_GROUPS:
        if expanded & group:
            expanded.update(group)
    return expanded


def extract_article_reference_phrases(query: str) -> set[str]:
    normalized_query = normalize_reference_text(query)
    phrases: set[str] = set()
    for match in re.finditer(r"(?:article|articles|الماده)\s+(\d{1,2})", normalized_query):
        number = int(match.group(1))
        phrases.add(f"article {number}")
        phrases.add(f"الماده {number}")
        ordinal = ARABIC_ARTICLE_ORDINALS.get(number)
        if ordinal:
            phrases.add(ordinal)
    return phrases


@dataclass(frozen=True)
class ReferenceChunk:
    page_number: int
    text: str
    normalized_text: str
    search_tokens: set[str]


class LegalReferenceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._chunks: list[ReferenceChunk] | None = None

    @property
    def has_sources(self) -> bool:
        return bool(self.settings.legal_reference_paths)

    def looks_like_reference_question(self, query: str) -> bool:
        tokens = expand_reference_tokens(tokenize_reference_text(normalize_reference_text(query)))
        return bool(tokens & REFERENCE_HINT_TOKENS)

    def search(self, query: str) -> list[dict[str, str | int]]:
        if not query.strip() or not self.has_sources:
            return []

        chunks = self._load_chunks()
        if not chunks:
            return []

        normalized_query = normalize_reference_text(query)
        query_tokens = expand_reference_tokens(tokenize_reference_text(normalized_query))
        if not query_tokens:
            return []

        article_reference_phrases = extract_article_reference_phrases(normalized_query)
        scores: list[tuple[float, ReferenceChunk]] = []
        numeric_tokens = {token for token in query_tokens if token.isdigit()}
        for chunk in chunks:
            overlap = query_tokens & chunk.search_tokens
            if not overlap:
                continue

            score = float(len(overlap))
            if numeric_tokens:
                score += 1.5 * len(numeric_tokens & chunk.search_tokens)
            if article_reference_phrases and any(
                phrase in chunk.normalized_text for phrase in article_reference_phrases
            ):
                score += 8.0
            if self._query_requests_summary(query_tokens):
                score += max(0.0, 2.0 - (chunk.page_number * 0.05))

            scores.append((score, chunk))

        if not scores and self._query_requests_summary(query_tokens):
            scores = [(1.0, chunk) for chunk in chunks[: self.settings.legal_reference_max_snippets]]

        if not scores:
            return []

        scores.sort(key=lambda item: (-item[0], item[1].page_number))
        snippets: list[dict[str, str | int]] = []
        seen_pages: set[int] = set()
        for _, chunk in scores:
            if chunk.page_number in seen_pages:
                continue
            seen_pages.add(chunk.page_number)
            snippets.append(
                {
                    "page_number": chunk.page_number,
                    "excerpt": chunk.text,
                }
            )
            if len(snippets) >= self.settings.legal_reference_max_snippets:
                break
        return snippets

    def _load_chunks(self) -> list[ReferenceChunk]:
        if self._chunks is not None:
            return self._chunks

        chunks: list[ReferenceChunk] = []
        for path in self.settings.legal_reference_paths:
            chunks.extend(self._load_chunks_from_pdf(path))
        self._chunks = chunks
        return chunks

    def _load_chunks_from_pdf(self, path: Path) -> list[ReferenceChunk]:
        if PdfReader is None or not path.exists():
            return []

        try:
            reader = PdfReader(str(path))
        except Exception:
            return []

        chunks: list[ReferenceChunk] = []
        for page_number, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                text = ""
            if not text:
                continue
            for chunk_text in self._split_text(text):
                normalized_text = normalize_reference_text(chunk_text)
                if not normalized_text:
                    continue
                tokens = expand_reference_tokens(tokenize_reference_text(normalized_text))
                if not tokens:
                    continue
                chunks.append(
                    ReferenceChunk(
                        page_number=page_number,
                        text=chunk_text,
                        normalized_text=normalized_text,
                        search_tokens=tokens,
                    )
                )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        text = WHITESPACE_PATTERN.sub(" ", text).strip()
        if not text:
            return []

        max_size = max(400, self.settings.legal_reference_chunk_size)
        overlap = min(max(50, self.settings.legal_reference_chunk_overlap), max_size // 2)
        if len(text) <= max_size:
            return [text]

        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + max_size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + max_size // 2, end)
                if boundary > start:
                    end = boundary
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks

    @staticmethod
    def _query_requests_summary(tokens: set[str]) -> bool:
        return bool(tokens & REFERENCE_HINT_TOKENS) and bool(tokens & SUMMARY_HINT_TOKENS)
