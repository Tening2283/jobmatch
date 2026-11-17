"""Règles métier du matching. Fonctions pures, chaque score est dans [0, 1]."""

from __future__ import annotations

from datetime import datetime

from apps.candidates.parsing import normalize
from apps.core.choices import RemoteMode

NEUTRAL = 0.5


def skills_score(candidate: set[int], required: set[int], optional: set[int]) -> float:
    """Couverture des compétences ; les compétences requises comptent double."""
    total = 2 * len(required) + len(optional)
    if total == 0:
        return NEUTRAL
    matched = 2 * len(required & candidate) + len(optional & candidate)
    return matched / total


def experience_score(candidate_years: int, min_years: int) -> float:
    if min_years <= 0 or candidate_years >= min_years:
        return 1.0
    return max(0.0, candidate_years / min_years)


def _same_city(a: str, b: str) -> bool | None:
    a, b = normalize(a or "").strip(), normalize(b or "").strip()
    if not a or not b:
        return None
    return a in b or b in a


def location_score(
    candidate_location: str, candidate_remote: str, job_location: str, job_remote: str
) -> float:
    if job_remote == RemoteMode.REMOTE:
        return 1.0
    same = _same_city(candidate_location, job_location)
    if same is None:
        base = NEUTRAL
    elif same:
        base = 1.0
    else:
        base = 0.3 if job_remote == RemoteMode.HYBRID else 0.0
    if candidate_remote == RemoteMode.REMOTE:
        base *= 0.5 if job_remote == RemoteMode.ONSITE else 0.8
    return base


def salary_score(expected: int | None, salary_min: int | None, salary_max: int | None) -> float:
    top = salary_max or salary_min
    if not expected or not top:
        return NEUTRAL
    if top >= expected:
        return 1.0
    gap = (expected - top) / expected
    return max(0.0, 1.0 - 2 * gap)


def freshness_score(created_at: datetime, now: datetime, horizon_days: int) -> float:
    age_days = max(0.0, (now - created_at).total_seconds() / 86400)
    return max(0.0, 1.0 - age_days / horizon_days)


def combine(scores: dict[str, float], weights: dict[str, float]) -> float:
    total_weight = sum(weights.get(k, 0) for k in scores)
    if total_weight == 0:
        return 0.0
    return sum(scores[k] * weights.get(k, 0) for k in scores) / total_weight
