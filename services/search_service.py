# services/search_service.py
"""
Global Search Engine.

Supports:
  - Fuzzy / substring matching across all collections
  - Field-weighted scoring (title > description > customer name > comments)
  - Type filtering (SRs only, users only, or all)
  - Highlighted match snippets

Usage:
    from services.search_service import search
    results = search("installation failed", types=["sr", "user"])
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional


SearchType = Literal["sr", "user", "task", "all"]

FIELD_WEIGHTS = {
    # SR fields
    "title":            10,
    "customer_name":    8,
    "customer_phone":   7,
    "sr_number":        9,
    "description":      5,
    "status":           3,
    "sr_type":          4,
    "assigned_to_name": 6,
    # User fields
    "name":             10,
    "email":            8,
    "role":             3,
    # Task fields
    "task_title":       10,
}


class SearchResult:
    def __init__(self, doc_type: str, doc: dict, score: float, snippet: str):
        self.doc_type = doc_type   # "sr" | "user" | "task"
        self.doc      = doc
        self.score    = score
        self.snippet  = snippet    # highlighted match context

    def to_dict(self) -> dict:
        return {
            "type":    self.doc_type,
            "doc":     self.doc,
            "score":   self.score,
            "snippet": self.snippet,
        }


def search(
    query: str,
    types: Optional[List[SearchType]] = None,
    max_results: int = 50,
) -> List[SearchResult]:
    """
    Search across local records.
    Returns a list of SearchResult sorted by score descending.
    Always runs synchronously — wrap in QThread if calling from UI.
    """
    if not query or not query.strip():
        return []

    query     = query.strip().lower()
    types     = types or ["all"]
    include_all = "all" in types

    results: List[SearchResult] = []

    try:
        from services.local_storage_service import local_storage

        # ── SRs ──────────────────────────────────────────────────────────────
        if include_all or "sr" in types:
            for sr in local_storage.get_collection("service_requests"):
                score, snippet = _score_doc(query, sr, _sr_text_fields(sr))
                if score > 0:
                    results.append(SearchResult("sr", sr, score, snippet))

        # ── Users ─────────────────────────────────────────────────────────────
        if include_all or "user" in types:
            for user in local_storage.get_collection("users"):
                score, snippet = _score_doc(query, user, _user_text_fields(user))
                if score > 0:
                    results.append(SearchResult("user", user, score, snippet))

        # ── Tasks ─────────────────────────────────────────────────────────────
        if include_all or "task" in types:
            for task in local_storage.get_collection("tasks"):
                score, snippet = _score_doc(query, task, _task_text_fields(task))
                if score > 0:
                    results.append(SearchResult("task", task, score, snippet))

    except Exception:
        return []

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:max_results]


def _sr_text_fields(doc: dict) -> Dict[str, str]:
    return {
        "sr_number":    str(doc.get("sr_number", "")),
        "title":        str(doc.get("title", "")),
        "description":  str(doc.get("description", "")),
        "customer_name":str(doc.get("customer_name", doc.get("customer", ""))),
        "customer_phone":str(doc.get("customer_phone", "")),
        "status":       str(doc.get("status", "")),
        "sr_type":      str(doc.get("sr_type", "")),
    }


def _user_text_fields(doc: dict) -> Dict[str, str]:
    return {
        "name":  str(doc.get("name", "")),
        "email": str(doc.get("email", "")),
        "role":  str(doc.get("role", "")),
    }


def _task_text_fields(doc: dict) -> Dict[str, str]:
    return {
        "task_title":  str(doc.get("title", doc.get("task_title", ""))),
        "description": str(doc.get("description", "")),
        "status":      str(doc.get("status", "")),
    }


def _score_doc(
    query: str,
    doc: dict,
    fields: Dict[str, str],
) -> tuple[float, str]:
    """
    Score a document against a query string.
    Returns (score, best_snippet).
    score=0 means no match.
    """
    best_score   = 0.0
    best_snippet = ""
    tokens = query.split()

    for field_name, field_value in fields.items():
        if not field_value:
            continue
        field_lower = field_value.lower()
        weight = FIELD_WEIGHTS.get(field_name, 2)

        # Exact phrase match — highest score
        if query in field_lower:
            pos     = field_lower.find(query)
            snippet = _extract_snippet(field_value, pos, len(query))
            score   = weight * 3.0
            if score > best_score:
                best_score   = score
                best_snippet = snippet
            continue

        # All tokens present — good match
        if all(t in field_lower for t in tokens):
            score = weight * 2.0
            if score > best_score:
                best_score   = score
                best_snippet = _extract_snippet(field_value, 0, len(field_value))
            continue

        # Partial — at least one token
        matched_tokens = [t for t in tokens if t in field_lower]
        if matched_tokens:
            score = weight * (len(matched_tokens) / len(tokens))
            if score > best_score:
                pos     = field_lower.find(matched_tokens[0])
                snippet = _extract_snippet(field_value, pos, len(matched_tokens[0]))
                best_score   = score
                best_snippet = snippet

    return best_score, best_snippet


def _extract_snippet(text: str, match_pos: int, match_len: int,
                     context: int = 40) -> str:
    """Extract a snippet of text around the match position."""
    start = max(0, match_pos - context)
    end   = min(len(text), match_pos + match_len + context)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet
