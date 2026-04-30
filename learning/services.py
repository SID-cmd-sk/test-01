from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SimilarityDecision:
    computed_similarity: float
    threshold: float
    accepted: bool
    overlap_tokens: list[str]
    source_tokens: list[str]
    target_tokens: list[str]


class LearningService:
    """
    Explicit, deterministic learning service.

    Design goals:
    - explainable behavior via token-overlap similarity (Jaccard)
    - no opaque/statistical model calls
    - full CRUD for rule_history records
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def bootstrap_schema(self, schema_path: str | Path) -> None:
        schema = Path(schema_path).read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(schema)

    # ---- Corrections + review suggestion ----
    def create_correction(
        self,
        pattern_signature: str,
        correction_payload: dict[str, Any],
        confidence_before: float,
        confidence_after: float,
        context_metadata: dict[str, Any],
        rule_type: str,
        optional_notes: str | None = None,
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO corrections (
                    pattern_signature, correction_payload,
                    confidence_before, confidence_after,
                    context_metadata, rule_type, optional_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern_signature,
                    json.dumps(correction_payload, sort_keys=True),
                    confidence_before,
                    confidence_after,
                    json.dumps(context_metadata, sort_keys=True),
                    rule_type,
                    optional_notes,
                ),
            )
            return int(cur.lastrowid)

    def suggest_low_confidence_items(
        self,
        max_confidence_before: float = 0.5,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM corrections
                WHERE confidence_before <= ?
                ORDER BY confidence_before ASC, created_at DESC
                LIMIT ?
                """,
                (max_confidence_before, limit),
            ).fetchall()
            return [self._decode_row(r) for r in rows]

    # ---- Explainable reuse/fix-to-similar ----
    def apply_fix_to_similar_cases(
        self,
        correction_id: int,
        target_pattern_signature: str,
        similarity_threshold: float,
        context_metadata: dict[str, Any] | None = None,
        optional_notes: str | None = None,
    ) -> SimilarityDecision:
        with self.connect() as conn:
            source = conn.execute(
                "SELECT pattern_signature FROM corrections WHERE id = ?",
                (correction_id,),
            ).fetchone()
            if not source:
                raise ValueError(f"correction_id={correction_id} not found")

            decision = self._similarity_decision(
                source["pattern_signature"],
                target_pattern_signature,
                similarity_threshold,
            )

            outcome_reason = (
                "accepted: similarity meets or exceeds threshold"
                if decision.accepted
                else "rejected: similarity below threshold"
            )

            self.record_rule_application_outcome(
                correction_id=correction_id,
                target_pattern_signature=target_pattern_signature,
                similarity_threshold=similarity_threshold,
                computed_similarity=decision.computed_similarity,
                reuse_success=decision.accepted,
                outcome_reason=outcome_reason,
                context_metadata=context_metadata or {},
                optional_notes=optional_notes,
                conn=conn,
            )
            return decision

    def record_rule_application_outcome(
        self,
        correction_id: int,
        target_pattern_signature: str,
        similarity_threshold: float,
        computed_similarity: float,
        reuse_success: bool,
        outcome_reason: str,
        context_metadata: dict[str, Any],
        optional_notes: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> int:
        owns_conn = conn is None
        connection = conn or self.connect()
        try:
            cur = connection.execute(
                """
                INSERT INTO rule_history (
                    correction_id,
                    target_pattern_signature,
                    similarity_threshold,
                    computed_similarity,
                    reuse_success,
                    outcome_reason,
                    context_metadata,
                    optional_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction_id,
                    target_pattern_signature,
                    similarity_threshold,
                    computed_similarity,
                    int(reuse_success),
                    outcome_reason,
                    json.dumps(context_metadata, sort_keys=True),
                    optional_notes,
                ),
            )
            if owns_conn:
                connection.commit()
            return int(cur.lastrowid)
        finally:
            if owns_conn:
                connection.close()

    # ---- rule_history CRUD for UI ----
    def create_rule_history(self, payload: dict[str, Any]) -> int:
        return self.record_rule_application_outcome(
            correction_id=int(payload["correction_id"]),
            target_pattern_signature=str(payload["target_pattern_signature"]),
            similarity_threshold=float(payload["similarity_threshold"]),
            computed_similarity=float(payload["computed_similarity"]),
            reuse_success=bool(payload["reuse_success"]),
            outcome_reason=str(payload["outcome_reason"]),
            context_metadata=dict(payload.get("context_metadata", {})),
            optional_notes=payload.get("optional_notes"),
        )

    def list_rule_history(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM rule_history ORDER BY applied_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [self._decode_row(r) for r in rows]

    def get_rule_history(self, history_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM rule_history WHERE id = ?",
                (history_id,),
            ).fetchone()
            return self._decode_row(row) if row else None

    def update_rule_history(self, history_id: int, fields: dict[str, Any]) -> bool:
        if not fields:
            return False

        mutable = {
            "target_pattern_signature",
            "similarity_threshold",
            "computed_similarity",
            "reuse_success",
            "outcome_reason",
            "context_metadata",
            "optional_notes",
        }
        sets: list[str] = []
        values: list[Any] = []
        for k, v in fields.items():
            if k not in mutable:
                continue
            sets.append(f"{k} = ?")
            if k == "context_metadata":
                values.append(json.dumps(v, sort_keys=True))
            elif k == "reuse_success":
                values.append(int(bool(v)))
            else:
                values.append(v)

        if not sets:
            return False

        values.append(history_id)
        with self.connect() as conn:
            cur = conn.execute(
                f"UPDATE rule_history SET {', '.join(sets)} WHERE id = ?",
                tuple(values),
            )
            return cur.rowcount > 0

    def delete_rule_history(self, history_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM rule_history WHERE id = ?", (history_id,))
            return cur.rowcount > 0

    # ---- helpers ----
    def _decode_row(self, row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        out = dict(row)
        for key in ("correction_payload", "context_metadata"):
            if key in out and isinstance(out[key], str):
                out[key] = json.loads(out[key])
        if "reuse_success" in out:
            out["reuse_success"] = bool(out["reuse_success"])
        return out

    def _similarity_decision(
        self,
        source_signature: str,
        target_signature: str,
        threshold: float,
    ) -> SimilarityDecision:
        source_tokens = sorted(self._tokenize(source_signature))
        target_tokens = sorted(self._tokenize(target_signature))
        source_set = set(source_tokens)
        target_set = set(target_tokens)
        overlap = sorted(source_set.intersection(target_set))
        union_size = len(source_set.union(target_set))
        similarity = 1.0 if union_size == 0 else (len(overlap) / union_size)
        return SimilarityDecision(
            computed_similarity=round(similarity, 6),
            threshold=threshold,
            accepted=similarity >= threshold,
            overlap_tokens=overlap,
            source_tokens=source_tokens,
            target_tokens=target_tokens,
        )

    def _tokenize(self, signature: str) -> set[str]:
        normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in signature)
        return {tok for tok in normalized.split() if tok}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
