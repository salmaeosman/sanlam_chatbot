from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ModuleNotFoundError:
    PdfReader = None


MAX_SUMMARY_LENGTH = 4000


class LocalPvExtractor:
    def extract(self, source_path: Path, filename: str) -> dict[str, Any]:
        raw_text = self._extract_text(source_path).strip()
        cleaned_text = self._clean_text(raw_text)

        victimes = self._extract_victimes(cleaned_text)
        vehicules = self._extract_vehicules(cleaned_text)

        fallback_text = (
            cleaned_text[:MAX_SUMMARY_LENGTH]
            if cleaned_text
            else (
                "Aucun texte exploitable n'a ete extrait localement. "
                "Branchez PV_REMOTE_INGEST_URL pour deleguer l'OCR/IA a un autre service Python."
            )
        )

        return {
            "document_name": filename,
            "numero_police": self._find_first(cleaned_text, self._numero_police_patterns()),
            "date_survenance": self._extract_date(cleaned_text),
            "ville": self._find_first(cleaned_text, self._ville_patterns()),
            "ville_ar": self._find_first(cleaned_text, self._ville_ar_patterns()),
            "adresse": self._find_first(cleaned_text, self._adresse_patterns()),
            "adresse_ar": self._find_first(cleaned_text, self._adresse_ar_patterns()),
            "victimes": victimes,
            "nombre_victimes": len(victimes),
            "vehicules": vehicules,
            "texte_brut": fallback_text,
            "texte_brut_ar": None,
            "statut": "termine",
        }

    def _extract_text(self, source_path: Path) -> str:
        suffix = source_path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf_text(source_path)

        if suffix in {".txt", ".csv", ".json"}:
            try:
                return source_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return source_path.read_text(encoding="latin-1", errors="ignore")

        return ""

    def _extract_pdf_text(self, source_path: Path) -> str:
        if PdfReader is None:
            return ""

        try:
            reader = PdfReader(str(source_path))
        except Exception:
            return ""

        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages)

    def _clean_text(self, value: str) -> str:
        value = value.replace("\x00", " ")
        value = re.sub(r"[ \t]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()

    def _extract_date(self, text: str) -> str | None:
        if not text:
            return None

        for pattern in (
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b\d{2}[/-]\d{2}[/-]\d{4}\b",
        ):
            match = re.search(pattern, text)
            if not match:
                continue

            value = match.group(0)
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(value, fmt).date().isoformat()
                except ValueError:
                    continue

        return None

    def _extract_victimes(self, text: str) -> list[dict[str, str | None]]:
        victims: list[dict[str, str | None]] = []
        seen: set[tuple[str, str]] = set()

        for pattern in (
            r"Victime(?:s)?\s*[:\-]\s*(?P<name>[^\n\r]+)",
            r"Nom de la victime\s*[:\-]\s*(?P<name>[^\n\r]+)",
            r"الضحية\s*[:\-]\s*(?P<name>[^\n\r]+)",
        ):
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                parsed = self._to_victim(match.group("name"))
                if not parsed:
                    continue
                key = (parsed["prenom_fr"], parsed["nom_fr"])
                if key in seen:
                    continue
                seen.add(key)
                victims.append(parsed)

        return victims

    def _extract_vehicules(self, text: str) -> list[dict[str, str | None]]:
        vehicles: list[dict[str, str | None]] = []
        seen: set[str] = set()

        for line in text.splitlines():
            normalized = line.strip()
            if not normalized:
                continue
            if not re.search(r"(vehicule|véhicule|plaque|immatriculation|المركبة)", normalized, re.IGNORECASE):
                continue

            plaque_match = re.search(r"\b([A-Z0-9]{2,}-?[A-Z0-9-]{2,})\b", normalized, flags=re.IGNORECASE)
            plaque = plaque_match.group(1).upper() if plaque_match else "INCONNUE"
            if plaque in seen:
                continue

            seen.add(plaque)
            vehicles.append(
                {
                    "type_fr": self._find_vehicle_type(normalized),
                    "type_ar": None,
                    "marque": self._find_vehicle_brand(normalized),
                    "plaque": plaque,
                }
            )

        return vehicles

    def _to_victim(self, raw_name: str) -> dict[str, str | None] | None:
        cleaned = re.split(r"[|,/;]", raw_name, maxsplit=1)[0].strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) < 3:
            return None

        parts = cleaned.split(" ")
        if len(parts) == 1:
            prenom_fr, nom_fr = parts[0], parts[0]
        else:
            prenom_fr = parts[0]
            nom_fr = " ".join(parts[1:])

        return {
            "nom_fr": nom_fr,
            "prenom_fr": prenom_fr,
            "nom_ar": None,
            "prenom_ar": None,
        }

    def _find_first(self, text: str, patterns: tuple[str, ...]) -> str | None:
        if not text:
            return None

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            value = match.group("value").strip()
            return re.sub(r"\s+", " ", value)

        return None

    def _find_vehicle_type(self, line: str) -> str:
        for label in ("voiture", "camion", "moto", "bus", "taxi", "vehicule", "véhicule"):
            if label in line.lower():
                return label.capitalize()
        return "Vehicule"

    def _find_vehicle_brand(self, line: str) -> str:
        for label in ("Renault", "Peugeot", "Dacia", "Hyundai", "Toyota", "Fiat", "Citroen", "Mercedes"):
            if label.lower() in line.lower():
                return label
        return "Inconnue"

    def _numero_police_patterns(self) -> tuple[str, ...]:
        return (
            r"(?:N[°o]\s*Police|Numero\s*de\s*police|رقم\s*الشرطة)\s*[:\-]?\s*(?P<value>[A-Z0-9/-]+)",
        )

    def _ville_patterns(self) -> tuple[str, ...]:
        return (
            r"(?:Ville|Lieu)\s*[:\-]\s*(?P<value>[^\n\r]+)",
        )

    def _ville_ar_patterns(self) -> tuple[str, ...]:
        return (
            r"(?:المدينة|المكان)\s*[:\-]\s*(?P<value>[^\n\r]+)",
        )

    def _adresse_patterns(self) -> tuple[str, ...]:
        return (
            r"Adresse\s*[:\-]\s*(?P<value>[^\n\r]+)",
        )

    def _adresse_ar_patterns(self) -> tuple[str, ...]:
        return (
            r"العنوان\s*[:\-]\s*(?P<value>[^\n\r]+)",
        )


def normalize_upstream_record(payload: dict[str, Any], filename: str) -> dict[str, Any]:
    def string_value(*keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def array_value(key: str) -> list[Any]:
        value = payload.get(key)
        return value if isinstance(value, list) else []

    victimes = []
    for victim in array_value("victimes"):
        if not isinstance(victim, dict):
            continue
        nom_fr = string_value_from(victim, "nom_fr", "nomFr")
        prenom_fr = string_value_from(victim, "prenom_fr", "prenomFr")
        if not nom_fr or not prenom_fr:
            continue
        victimes.append(
            {
                "nom_fr": nom_fr,
                "prenom_fr": prenom_fr,
                "nom_ar": string_value_from(victim, "nom_ar", "nomAr"),
                "prenom_ar": string_value_from(victim, "prenom_ar", "prenomAr"),
            }
        )

    vehicules = []
    for vehicle in array_value("vehicules"):
        if not isinstance(vehicle, dict):
            continue
        type_fr = string_value_from(vehicle, "type_fr", "typeFr")
        marque = string_value_from(vehicle, "marque")
        plaque = string_value_from(vehicle, "plaque")
        if not type_fr or not marque or not plaque:
            continue
        vehicules.append(
            {
                "type_fr": type_fr,
                "type_ar": string_value_from(vehicle, "type_ar", "typeAr"),
                "marque": marque,
                "plaque": plaque,
            }
        )

    return {
        "document_name": string_value("document_name", "documentName") or filename,
        "numero_police": string_value("numero_police", "numeroPolice"),
        "date_survenance": string_value("date_survenance", "dateSurvenance"),
        "ville": string_value("ville"),
        "ville_ar": string_value("ville_ar", "villeAr"),
        "adresse": string_value("adresse"),
        "adresse_ar": string_value("adresse_ar", "adresseAr"),
        "victimes": victimes,
        "nombre_victimes": payload.get("nombre_victimes", payload.get("nombreVictimes", len(victimes))),
        "vehicules": vehicules,
        "texte_brut": string_value("texte_brut", "texteBrut"),
        "texte_brut_ar": string_value("texte_brut_ar", "texteBrutAr"),
        "statut": string_value("statut") or "termine",
    }


def string_value_from(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
