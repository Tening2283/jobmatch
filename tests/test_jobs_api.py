import pytest
from django.urls import reverse

from apps.jobs.models import JobOffer

from .factories import CompanyFactory, JobOfferFactory, RecruiterFactory

pytestmark = pytest.mark.django_db


def _payload(company, skills):
    return {
        "title": "Développeur Django",
        "description": "API REST Python",
        "company": company.id,
        "contract_type": "cdi",
        "remote": "hybrid",
        "location": "Dakar",
        "salary_min": 500,
        "salary_max": 900,
        "skills_input": [
            {"skill": skills["Python"].id, "required": True},
            {"skill": skills["Docker"].id, "required": False},
        ],
    }


def test_recruiter_creates_job_and_embedding_is_computed(
    recruiter_client, company, skills, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        res = recruiter_client.post(reverse("job-list"), _payload(company, skills), format="json")
    assert res.status_code == 201, res.data
    assert {s["name"]: s["required"] for s in res.data["skills"]} == {
        "Python": True,
        "Docker": False,
    }
    job = JobOffer.objects.get(pk=res.data["id"])
    assert job.recruiter == recruiter_client.user
    assert job.embedding is not None and job.embedding_updated_at is not None


def test_job_validation(recruiter_client, company, skills):
    data = _payload(company, skills) | {"salary_min": 1000, "salary_max": 10}
    res = recruiter_client.post(reverse("job-list"), data, format="json")
    assert res.status_code == 400
    other_company = CompanyFactory()
    res = recruiter_client.post(reverse("job-list"), _payload(other_company, skills), format="json")
    assert res.status_code == 400


def test_candidate_cannot_create_job(candidate_client, company, skills):
    res = candidate_client.post(reverse("job-list"), _payload(company, skills), format="json")
    assert res.status_code == 403


def test_public_list_hides_inactive_and_filters(api_client, skills):
    JobOfferFactory(title="Data analyst", contract_type="cdd", required_skills=[skills["Excel"]])
    JobOfferFactory(title="Backend", required_skills=[skills["Python"]])
    JobOfferFactory(title="Old", is_active=False)
    res = api_client.get(reverse("job-list"))
    assert res.status_code == 200
    assert res.data["count"] == 2
    res = api_client.get(reverse("job-list"), {"skill": "python"})
    assert [j["title"] for j in res.data["results"]] == ["Backend"]
    res = api_client.get(reverse("job-list"), {"contract_type": "cdd"})
    assert res.data["count"] == 1
    res = api_client.get(reverse("job-list"), {"search": "analyst"})
    assert res.data["count"] == 1


def test_recruiter_sees_only_own_inactive_offers(recruiter_client):
    own_inactive = JobOfferFactory(
        company=CompanyFactory(owner=recruiter_client.user), is_active=False
    )
    other_inactive = JobOfferFactory(is_active=False)
    active = JobOfferFactory()
    ids = {j["id"] for j in recruiter_client.get(reverse("job-list")).data["results"]}
    assert ids == {own_inactive.id, active.id}
    url = reverse("job-detail", args=[other_inactive.id])
    assert recruiter_client.get(url).status_code == 404


def test_only_owner_can_update_or_delete(recruiter_client, skills):
    own = JobOfferFactory(company=CompanyFactory(owner=recruiter_client.user))
    other = JobOfferFactory(company=CompanyFactory(owner=RecruiterFactory()))
    url = reverse("job-detail", args=[own.id])
    res = recruiter_client.patch(
        url, {"title": "Nouveau", "skills_input": [{"skill": skills["React"].id}]}, format="json"
    )
    assert res.status_code == 200
    assert res.data["title"] == "Nouveau"
    assert [s["name"] for s in res.data["skills"]] == ["React"]
    assert (
        recruiter_client.patch(reverse("job-detail", args=[other.id]), {"title": "x"}).status_code
        == 403
    )
    assert recruiter_client.delete(url).status_code == 204


def test_companies_and_skills(recruiter_client, api_client):
    res = recruiter_client.post(reverse("company-list"), {"name": "Sonatel", "location": "Dakar"})
    assert res.status_code == 201
    assert res.data["owner"] == recruiter_client.user.id
    assert api_client.get(reverse("company-list")).data["count"] == 1
    res = api_client.get(reverse("skill-list"), {"search": "pyth"})
    assert any(s["name"] == "Python" for s in res.data)


def test_deactivate_expired_offers_task():
    from datetime import timedelta

    from django.utils import timezone

    from apps.jobs.tasks import deactivate_expired_offers

    expired = JobOfferFactory(expires_at=timezone.now() - timedelta(days=1))
    alive = JobOfferFactory(expires_at=timezone.now() + timedelta(days=1))
    assert deactivate_expired_offers() == 1
    expired.refresh_from_db()
    alive.refresh_from_db()
    assert not expired.is_active and alive.is_active
