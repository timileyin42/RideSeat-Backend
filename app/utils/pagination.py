"""Pagination helpers."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def normalize_pagination(limit: int | None, offset: int | None, max_limit: int = 100) -> Pagination:
    resolved_limit = 50 if limit is None else limit
    resolved_offset = 0 if offset is None else offset
    if resolved_limit < 1 or resolved_offset < 0:
        raise ValueError("Invalid pagination values")
    if resolved_limit > max_limit:
        resolved_limit = max_limit
    return Pagination(limit=resolved_limit, offset=resolved_offset)
