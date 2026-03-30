from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PvVictime(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nom_fr: str
    prenom_fr: str
    nom_ar: str | None = None
    prenom_ar: str | None = None


class PvVehicule(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type_fr: str
    marque: str
    plaque: str
    type_ar: str | None = None


class PvRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    document_name: str
    document_url: str | None = None
    numero_police: str | None = None
    date_survenance: str | None = None
    ville: str | None = None
    ville_ar: str | None = None
    adresse: str | None = None
    adresse_ar: str | None = None
    victimes: list[PvVictime] = []
    nombre_victimes: int = 0
    vehicules: list[PvVehicule] = []
    texte_brut: str | None = None
    texte_brut_ar: str | None = None
    statut: str = "en_cours"
    created_at: str
    updated_at: str
    source_document_download_url: str
