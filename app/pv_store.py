from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class PvRecordStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pv_records (
                    id TEXT PRIMARY KEY,
                    owner_ref TEXT NOT NULL,
                    document_name TEXT NOT NULL,
                    document_url TEXT,
                    numero_police TEXT,
                    date_survenance TEXT,
                    ville TEXT,
                    ville_ar TEXT,
                    adresse TEXT,
                    adresse_ar TEXT,
                    victimes_json TEXT NOT NULL,
                    nombre_victimes INTEGER NOT NULL,
                    vehicules_json TEXT NOT NULL,
                    texte_brut TEXT,
                    texte_brut_ar TEXT,
                    statut TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    source_document_path TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_pv_records_owner_ref ON pv_records(owner_ref)"
            )

    def list_records(self, owner_ref: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM pv_records
                WHERE owner_ref = ?
                ORDER BY datetime(updated_at) DESC, rowid DESC
                """,
                (owner_ref,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_record(self, owner_ref: str, record_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM pv_records
                WHERE owner_ref = ? AND id = ?
                """,
                (owner_ref, record_id),
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def create_record(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO pv_records (
                    id,
                    owner_ref,
                    document_name,
                    document_url,
                    numero_police,
                    date_survenance,
                    ville,
                    ville_ar,
                    adresse,
                    adresse_ar,
                    victimes_json,
                    nombre_victimes,
                    vehicules_json,
                    texte_brut,
                    texte_brut_ar,
                    statut,
                    created_at,
                    updated_at,
                    source_document_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["id"],
                    record["owner_ref"],
                    record["document_name"],
                    record.get("document_url"),
                    record.get("numero_police"),
                    record.get("date_survenance"),
                    record.get("ville"),
                    record.get("ville_ar"),
                    record.get("adresse"),
                    record.get("adresse_ar"),
                    json.dumps(record.get("victimes", []), ensure_ascii=True),
                    int(record.get("nombre_victimes", 0)),
                    json.dumps(record.get("vehicules", []), ensure_ascii=True),
                    record.get("texte_brut"),
                    record.get("texte_brut_ar"),
                    record.get("statut", "en_cours"),
                    record["created_at"],
                    record["updated_at"],
                    record["source_document_path"],
                ),
            )
        return self.get_record(record["owner_ref"], record["id"]) or record

    def update_record(self, owner_ref: str, record_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        existing = self.get_record(owner_ref, record_id)
        if not existing:
            return None

        merged = {**existing, **changes}
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE pv_records
                SET
                    document_name = ?,
                    document_url = ?,
                    numero_police = ?,
                    date_survenance = ?,
                    ville = ?,
                    ville_ar = ?,
                    adresse = ?,
                    adresse_ar = ?,
                    victimes_json = ?,
                    nombre_victimes = ?,
                    vehicules_json = ?,
                    texte_brut = ?,
                    texte_brut_ar = ?,
                    statut = ?,
                    updated_at = ?
                WHERE owner_ref = ? AND id = ?
                """,
                (
                    merged["document_name"],
                    merged.get("document_url"),
                    merged.get("numero_police"),
                    merged.get("date_survenance"),
                    merged.get("ville"),
                    merged.get("ville_ar"),
                    merged.get("adresse"),
                    merged.get("adresse_ar"),
                    json.dumps(merged.get("victimes", []), ensure_ascii=True),
                    int(merged.get("nombre_victimes", 0)),
                    json.dumps(merged.get("vehicules", []), ensure_ascii=True),
                    merged.get("texte_brut"),
                    merged.get("texte_brut_ar"),
                    merged.get("statut", "en_cours"),
                    merged["updated_at"],
                    owner_ref,
                    record_id,
                ),
            )
        return self.get_record(owner_ref, record_id)

    def delete_record(self, owner_ref: str, record_id: str) -> dict[str, Any] | None:
        existing = self.get_record(owner_ref, record_id)
        if not existing:
            return None

        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM pv_records
                WHERE owner_ref = ? AND id = ?
                """,
                (owner_ref, record_id),
            )
        return existing

    def get_stats(self, owner_ref: str) -> dict[str, int]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN statut = 'termine' THEN 1 ELSE 0 END) AS termine,
                    SUM(CASE WHEN statut = 'erreur' THEN 1 ELSE 0 END) AS erreur,
                    SUM(CASE WHEN statut = 'en_cours' THEN 1 ELSE 0 END) AS en_cours
                FROM pv_records
                WHERE owner_ref = ?
                """,
                (owner_ref,),
            ).fetchone()

        return {
            "total": int(row["total"] or 0),
            "termine": int(row["termine"] or 0),
            "erreur": int(row["erreur"] or 0),
            "en_cours": int(row["en_cours"] or 0),
        }

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "owner_ref": row["owner_ref"],
            "document_name": row["document_name"],
            "document_url": row["document_url"],
            "numero_police": row["numero_police"],
            "date_survenance": row["date_survenance"],
            "ville": row["ville"],
            "ville_ar": row["ville_ar"],
            "adresse": row["adresse"],
            "adresse_ar": row["adresse_ar"],
            "victimes": json.loads(row["victimes_json"]),
            "nombre_victimes": row["nombre_victimes"],
            "vehicules": json.loads(row["vehicules_json"]),
            "texte_brut": row["texte_brut"],
            "texte_brut_ar": row["texte_brut_ar"],
            "statut": row["statut"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "source_document_path": row["source_document_path"],
        }
