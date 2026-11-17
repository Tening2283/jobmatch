from unittest import mock

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_health_ok(api_client):
    with mock.patch("apps.core.views._check_redis", return_value=True):
        res = api_client.get(reverse("health"))
    assert res.status_code == 200
    assert res.data == {"status": "ok", "checks": {"database": True, "redis": True}}


def test_health_degraded(api_client, settings):
    settings.REDIS_URL = "redis://127.0.0.1:1/0"
    res = api_client.get(reverse("health"))
    assert res.status_code == 503
    assert res.data["checks"]["redis"] is False


def test_health_db_failure(api_client):
    with mock.patch("apps.core.views.connection.cursor", side_effect=Exception("down")):
        from apps.core.views import _check_db

        assert _check_db() is False


def test_openapi_schema(api_client):
    res = api_client.get(reverse("schema"))
    assert res.status_code == 200
    assert b"/api/v1/recommendations/" in res.content


def test_error_format(api_client):
    res = api_client.get(reverse("recommendations"))
    assert res.status_code == 401
    assert res.data["error"]["status"] == 401


def test_model_str(candidate_profile):
    from .factories import JobOfferFactory, ResumeFactory

    job = JobOfferFactory()
    assert "@" in str(job)
    assert str(job.company) == job.company.name
    assert "Profil" in str(candidate_profile)
    assert "CV" in str(ResumeFactory(candidate=candidate_profile))
