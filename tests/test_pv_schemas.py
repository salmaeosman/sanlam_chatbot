from __future__ import annotations

from app.pv_schemas import (
    normalize_birth_date,
    normalize_cin_value,
    normalize_driver_permit_class,
    normalize_driver_permit_number,
    normalize_extracted_pv_payload,
    normalize_itt_days_value,
    normalize_phone_value,
    normalize_policy_number,
    normalize_pv_number,
    normalize_time_value,
)


def test_normalize_cin_value_accepts_identity_card_labels() -> None:
    assert normalize_cin_value("CIN N° AB 123456") == "AB123456"
    assert normalize_cin_value("رقم بطاقة التعريف الوطنية : cd-987654") == "CD987654"


def test_normalize_extracted_pv_payload_adds_cin_per_victim() -> None:
    payload = {
        "numero_pv": "عدد المحضر ١٢٣/٢٠٢٦",
        "heure_survenance": "١٤:٣٥",
        "numero_permis_conducteur": "Numero du permis: P-123456",
        "classe_permis_conducteur": "Categorie du permis: b",
        "assure": {
            "type": "Personne morale",
            "nomSociete": "  Alpha  Conseil  ",
        },
        "vehicules": [
            {
                "type_fr": "Voiture",
                "marque": "Dacia",
                "plaque": "123-A-45",
                "compagnie_assurance": "Compagnie d'assurance: SAHAM assurances",
                "numero_police": "Numero de police: POL 123",
            },
            {
                "type_fr": "Camion",
                "marque": "Isuzu",
                "plaque": "456-B-78",
                "compagnie_assurance": "شركة التأمين: AXA Assurance",
                "numero_police": "رقم بوليصة التأمين ٤٥٦/٢٠٢٦",
            },
        ],
        "victimes": [
            {
                "nom_fr": "Doe",
                "prenom_fr": "Jane",
                "cin": "CIN N° AB 123456",
                "etat_apres_accident": "Blessee",
                "qualite_victime": "Pieton",
                "date_naissance": "12/09/1960",
                "telephone": "Tel: 06 30 664 609",
                "itt": "ITT 30 jours",
            },
            {
                "nom_fr": "Roe",
                "prenom_fr": "John",
                "numero_carte_nationale": "بطاقة التعريف الوطنية cd-987654",
                "date_naissance": "٢٠٠١-٠٥-٠٣",
                "telephone": "رقم الهاتف ٠٦ ١٢ ٣٤ ٥٦ ٧٨",
                "itt": "العجز المؤقت عن العمل ١٥ يوما",
            },
        ]
    }

    normalized = normalize_extracted_pv_payload(payload)

    assert normalized["numero_pv"] == "عدد المحضر 123/2026"
    assert normalized["heure_survenance"] == "14:35"
    assert normalized["numero_permis_conducteur"] == "P-123456"
    assert normalized["classe_permis_conducteur"] == "B"
    assert normalized["assure"] == {
        "type": "personne_morale",
        "nom_societe": "Alpha Conseil",
    }
    assert "numero_police" not in normalized
    assert normalized["vehicules"][0]["compagnie_assurance"] == "Saham Assurance"
    assert normalized["vehicules"][1]["compagnie_assurance"] == "AXA Assurance"
    assert normalized["vehicules"][0]["numero_police"] == "POL 123"
    assert normalized["vehicules"][1]["numero_police"] == "456/2026"
    assert normalized["victimes"][0]["cin"] == "AB123456"
    assert normalized["victimes"][0]["date_naissance"] == "1960-09-12"
    assert normalized["victimes"][0]["telephone"] == "0630664609"
    assert normalized["victimes"][0]["itt"] == "30"
    assert normalized["victimes"][1]["cin"] == "CD987654"
    assert normalized["victimes"][1]["date_naissance"] == "2001-05-03"
    assert normalized["victimes"][1]["telephone"] == "0612345678"
    assert normalized["victimes"][1]["itt"] == "15"


def test_normalize_time_and_pv_number_keep_structured_values() -> None:
    assert normalize_time_value("09h07") == "09:07"
    assert normalize_pv_number("عدد ١٧/٢٠٢٦") == "عدد 17/2026"
    assert normalize_policy_number("رقم بوليصة التأمين ١٧/٢٠٢٦") == "17/2026"
    assert normalize_driver_permit_number("Numero du permis: P 123456") == "P 123456"
    assert normalize_driver_permit_class("Classe du permis: b") == "B"
    assert normalize_birth_date("12-09-1960") == "1960-09-12"
    assert normalize_birth_date("Nee le: 19/09/91") == "1991-09-19"
    assert normalize_birth_date("تاريخ الازدياد ١٩/٠٩/١٩٩١") == "1991-09-19"
    assert normalize_phone_value("Tel: +212 6 30 66 46 09") == "+212630664609"
    assert normalize_itt_days_value("ITT: 45 jours") == "45"
    assert normalize_itt_days_value("العجز المؤقت عن العمل ١٢ يوما") == "12"


def test_normalize_extracted_pv_payload_deduplicates_victims_and_recomputes_total() -> None:
    payload = {
        "nombre_victimes": 3,
        "victimes": [
            {
                "nom_fr": "Ezzaydi",
                "prenom_fr": "Chabab",
                "cin": "GJ11565",
                "etat_apres_accident": "Blessee",
                "qualite_victime": "Pieton",
            },
            {
                "nom_fr": "Ezzaydi",
                "prenom_fr": "Chabab",
                "cin": "CIN GJ11565",
                "date_naissance": "19/09/1991",
                "telephone": "06 34 88 15 01",
                "itt": "ITT 20 jours",
            },
            {
                "nom_fr": "Rhouny",
                "prenom_fr": "Chaimaa",
                "cin": "BE865779",
            },
        ],
        "vehicules": [],
    }

    normalized = normalize_extracted_pv_payload(payload)

    assert normalized["nombre_victimes"] == 2
    assert len(normalized["victimes"]) == 2
    assert normalized["victimes"][0]["cin"] == "GJ11565"
    assert normalized["victimes"][0]["date_naissance"] == "1991-09-19"
    assert normalized["victimes"][0]["telephone"] == "0634881501"
    assert normalized["victimes"][0]["itt"] == "20"


def test_normalize_extracted_pv_payload_enriches_missing_fields_from_summary() -> None:
    payload = {
        "victimes": [
            {
                "nom_fr": "Ezzaydi",
                "prenom_fr": "Chabab",
                "cin": "GJ11565",
                "date_naissance": "jj/mm/aaaa",
            },
        ],
        "vehicules": [],
        "texte_brut_fr": (
            "Victime 1: Chabab Ezzaydi, nee le 19/09/1991, CIN GJ11565, "
            "telephone 06 34 88 15 01, pieton blessee."
        ),
    }

    normalized = normalize_extracted_pv_payload(payload)

    assert normalized["nombre_victimes"] == 1
    assert normalized["victimes"][0]["cin"] == "GJ11565"
    assert normalized["victimes"][0]["date_naissance"] == "1991-09-19"
    assert normalized["victimes"][0]["telephone"] == "0634881501"
    assert normalized["victimes"][0]["qualite_victime"] == "Pieton"
    assert normalized["victimes"][0]["etat_apres_accident"] == "Blessee"


def test_normalize_extracted_pv_payload_adds_missing_victim_from_summary() -> None:
    payload = {
        "victimes": [
            {
                "nom_fr": "Doe",
                "prenom_fr": "Jane",
                "cin": "AB123456",
            },
        ],
        "vehicules": [],
        "texte_brut_fr": (
            "Le PV mentionne 2 victimes. "
            "Victime 1: Jane Doe, CIN AB123456. "
            "Victime 2: Chaimaa Rhouny, CIN BE865779, nee le 19/09/1991, "
            "telephone 06 32 20 06 37, conductrice blessee."
        ),
    }

    normalized = normalize_extracted_pv_payload(payload)

    assert normalized["nombre_victimes"] == 2
    assert len(normalized["victimes"]) == 2
    assert normalized["victimes"][1]["nom_fr"] == "Rhouny"
    assert normalized["victimes"][1]["prenom_fr"] == "Chaimaa"
    assert normalized["victimes"][1]["cin"] == "BE865779"
    assert normalized["victimes"][1]["date_naissance"] == "1991-09-19"
    assert normalized["victimes"][1]["telephone"] == "0632200637"
    assert normalized["victimes"][1]["qualite_victime"] == "Conducteur"
    assert normalized["victimes"][1]["etat_apres_accident"] == "Blessee"


def test_normalize_extracted_pv_payload_uses_summary_count_when_details_are_partial() -> None:
    payload = {
        "victimes": [
            {
                "nom_fr": "Doe",
                "prenom_fr": "Jane",
                "cin": "AB123456",
            },
        ],
        "vehicules": [],
        "texte_brut_fr": "Le proces-verbal mentionne 2 victimes, mais une seule est detaillee.",
    }

    normalized = normalize_extracted_pv_payload(payload)

    assert len(normalized["victimes"]) == 1
    assert normalized["nombre_victimes"] == 2


def test_normalize_extracted_pv_payload_normalizes_personne_physique_assure() -> None:
    payload = {
        "assure": {
            "assureType": "personne physique",
            "nom_fr": "  El Fassi ",
            "prenom_fr": " Asmae  ",
        },
        "victimes": [],
        "vehicules": [],
    }

    normalized = normalize_extracted_pv_payload(payload)

    assert normalized["assure"] == {
        "type": "personne_physique",
        "nom": "El Fassi",
        "prenom": "Asmae",
    }
