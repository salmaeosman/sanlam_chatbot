from app.config import PROJECT_ROOT, Settings
from app.legal_reference_service import (
    LegalReferenceService,
    ReferenceChunk,
    expand_reference_tokens,
    normalize_reference_text,
    tokenize_reference_text,
)


def _build_chunk(page_number: int, text: str) -> ReferenceChunk:
    normalized = normalize_reference_text(text)
    return ReferenceChunk(
        page_number=page_number,
        text=text,
        normalized_text=normalized,
        search_tokens=expand_reference_tokens(tokenize_reference_text(normalized)),
    )


def test_search_matches_french_query_against_arabic_chunks():
    service = LegalReferenceService(Settings(LEGAL_REFERENCE_PATHS="c:/fake.pdf"))
    service._chunks = [
        _build_chunk(4, "المادة الثانية تشمل استرجاع مصاريف العلاج والاستشفاء."),
        _build_chunk(5, "المادة الثالثة يشمل التعويض عن العجز المؤقت وفقد الأجر."),
    ]

    snippets = service.search("Que dit l'article 3 sur l'indemnisation en cas d'incapacité temporaire ?")

    assert snippets
    assert snippets[0]["page_number"] == 5
    assert "العجز المؤقت" in str(snippets[0]["excerpt"])


def test_search_prioritizes_exact_article_reference():
    service = LegalReferenceService(Settings(LEGAL_REFERENCE_PATHS="c:/fake.pdf"))
    service._chunks = [
        _build_chunk(5, "المادة الثالثة يشمل التعويض عن العجز المؤقت وفقد الأجر."),
        _build_chunk(7, "الشواهد الطبية تتضمن المدة المحتملة للعجز المؤقت عن العمل."),
    ]

    snippets = service.search("Que dit l'article 3 sur l'incapacite temporaire ?")

    assert snippets
    assert snippets[0]["page_number"] == 5


def test_search_matches_arabic_query_against_arabic_chunks():
    service = LegalReferenceService(Settings(LEGAL_REFERENCE_PATHS="c:/fake.pdf"))
    service._chunks = [
        _build_chunk(4, "المادة الثانية تشمل استرجاع مصاريف العلاج والاستشفاء."),
    ]

    snippets = service.search("ما هي المصاريف التي يتم تعويضها؟")

    assert snippets
    assert snippets[0]["page_number"] == 4


def test_search_returns_first_pages_for_broad_summary_questions():
    service = LegalReferenceService(Settings(LEGAL_REFERENCE_PATHS="c:/fake.pdf"))
    service._chunks = [
        _build_chunk(1, "ظهير شريف يتعلق بتعويض المصابين في حوادث السير."),
        _build_chunk(7, "مقتضيات اخرى متعلقة بالخبرة."),
    ]

    snippets = service.search("Resumer ce dahir")

    assert snippets
    assert snippets[0]["page_number"] == 1


def test_relative_legal_reference_path_is_resolved_from_project_root():
    settings = Settings(LEGAL_REFERENCE_PATHS="references/legal/Dahir.pdf")

    resolved_path = settings.legal_reference_paths[0]

    assert resolved_path.is_absolute()
    assert resolved_path == PROJECT_ROOT / "references" / "legal" / "Dahir.pdf"
