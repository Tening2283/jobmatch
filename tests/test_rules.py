from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.choices import RemoteMode
from apps.matching.services import rules


def test_skills_score():
    assert rules.skills_score({1, 2}, set(), set()) == rules.NEUTRAL
    assert rules.skills_score({1, 2}, {1, 2}, set()) == 1.0
    assert rules.skills_score({1}, {1, 2}, {3}) == pytest.approx(2 / 5)
    assert rules.skills_score({3}, {1}, {3}) == pytest.approx(1 / 3)


@pytest.mark.parametrize(
    ("cand", "req", "exp"), [(5, 0, 1.0), (5, 3, 1.0), (1, 4, 0.25), (0, 2, 0.0)]
)
def test_experience_score(cand, req, exp):
    assert rules.experience_score(cand, req) == exp


@pytest.mark.parametrize(
    ("cand_loc", "cand_remote", "job_loc", "job_remote", "expected"),
    [
        ("Dakar", RemoteMode.HYBRID, "Paris", RemoteMode.REMOTE, 1.0),
        ("Dakar", RemoteMode.ONSITE, "dakar, Sénégal", RemoteMode.ONSITE, 1.0),
        ("Dakar", RemoteMode.ONSITE, "Thiès", RemoteMode.HYBRID, 0.3),
        ("Dakar", RemoteMode.ONSITE, "Thiès", RemoteMode.ONSITE, 0.0),
        ("", RemoteMode.ONSITE, "Thiès", RemoteMode.ONSITE, 0.5),
        ("Dakar", RemoteMode.REMOTE, "Dakar", RemoteMode.ONSITE, 0.5),
        ("Dakar", RemoteMode.REMOTE, "Dakar", RemoteMode.HYBRID, 0.8),
    ],
)
def test_location_score(cand_loc, cand_remote, job_loc, job_remote, expected):
    assert rules.location_score(cand_loc, cand_remote, job_loc, job_remote) == pytest.approx(
        expected
    )


def test_salary_score():
    assert rules.salary_score(None, 100, 200) == rules.NEUTRAL
    assert rules.salary_score(1000, None, None) == rules.NEUTRAL
    assert rules.salary_score(1000, 800, 1200) == 1.0
    assert rules.salary_score(1000, 900, None) == pytest.approx(0.8)
    assert rules.salary_score(1000, 100, 400) == 0.0


def test_freshness_score():
    now = timezone.now()
    assert rules.freshness_score(now, now, 60) == 1.0
    assert rules.freshness_score(now - timedelta(days=30), now, 60) == pytest.approx(0.5)
    assert rules.freshness_score(now - timedelta(days=90), now, 60) == 0.0


def test_combine():
    assert rules.combine({"a": 1.0, "b": 0.0}, {"a": 3, "b": 1}) == 0.75
    assert rules.combine({"a": 1.0}, {}) == 0.0
