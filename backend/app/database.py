import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .schemas import CorrectionPayload, CorrectionResponse


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "./engtutor.sqlite3"))


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                natural_alternative TEXT NOT NULL,
                explanation TEXT NOT NULL,
                changes_json TEXT NOT NULL,
                vocabulary_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_correction(payload: CorrectionPayload) -> CorrectionResponse:
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO corrections (
                original_text,
                corrected_text,
                natural_alternative,
                explanation,
                changes_json,
                vocabulary_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload.original_text,
                payload.corrected_text,
                payload.natural_alternative,
                payload.explanation,
                json.dumps([item.model_dump() for item in payload.changes]),
                json.dumps([item.model_dump() for item in payload.vocabulary_suggestions]),
            ),
        )
        row = connection.execute(
            "SELECT * FROM corrections WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return row_to_response(row)


def list_corrections(limit: int = 50) -> list[CorrectionResponse]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM corrections ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [row_to_response(row) for row in rows]


def clear_corrections() -> None:
    with get_connection() as connection:
        connection.execute("DELETE FROM corrections")


def row_to_response(row: sqlite3.Row) -> CorrectionResponse:
    return CorrectionResponse(
        id=row["id"],
        original_text=row["original_text"],
        corrected_text=row["corrected_text"],
        natural_alternative=row["natural_alternative"],
        explanation=row["explanation"],
        changes=json.loads(row["changes_json"]),
        vocabulary_suggestions=json.loads(row["vocabulary_json"]),
        created_at=row["created_at"],
    )
