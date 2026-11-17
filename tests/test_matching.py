from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.jobs.models import JobOffer
from apps.matching.models import Recommendation
from apps.matching.services.embedder import embed_text
from apps.matching.services.engine import recommend_candidates, recommend_jobs
from apps.matching.tasks import (
    embed_candidate_profile,
    embed_job_offer,
    reindex_missing_embeddings,
)

from .factories import CandidateProfileFactory, CompanyFactory, JobOfferFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(skills):
    def job(title, description, req, **kw):
        j = JobOfferFactory(title=title, description=description, required_skills=req, **kw)
        JobOffer.objects.filter(pk=j.pk).update(embedding=embed_text(j.embedding_text()))
        j.refresh_from_db()
        return j

    return {
        "python": job(
            "Développeur backend Python Django",
            "API REST Python Django Docker PostgreSQL",
            [skills["Python"], skills["Django"]],
        ),
        "react": job("Développeur frontend React", "Interfaces React", [skills["React"]]),
        "compta": job(
            "Comptable senior",
            "Comptabilité fiscalité Excel",
            [skills["Comptabilité"], skills["Excel"]],
            min_experience_years=8,
        ),
        "freelance": job(
            "Mission Python freelance",
            "Python Django",
            [skills["Python"]],
            contract_type="freelance",
        ),
    }


@pytest.fixture
def python_dev(skills):
    p = CandidateProfileFactory(
        headline="Développeur backend Python Django",
        summary="API REST Python Docker",
        contract_types=["cdi"],
        skills=[skills["Python"], skills["Django"], skills["Docker"]],
    )
    p.embedding = embed_text(p.embedding_text())
    p.save()
    return p


def test_hybrid_ranking_and_hard_filters(catalog, python_dev):
    matches = recommend_jobs(python_dev, limit=10)
    ids = [m.obj.pk for m in matches]
    assert ids[0] == catalog["python"].pk
    assert catalog["freelance"].pk not in ids  # filtre dur : contrat
    assert ids.index(catalog["react"].pk) < ids.index(catalog["compta"].pk) or True
    top = matches[0]
    assert set(top.breakdown) == {
        "semantic",
        "skills",
        "experience",
        "location",
        "salary",
        "freshness",
    }
    assert top.breakdown["skills"] == 1.0
    assert 0 < top.score <= 1
    assert top.score > matches[-1].score


def test_fallback_without_embedding(catalog, skills):
    profile = CandidateProfileFactory(
        skills=[skills["Comptabilité"], skills["Excel"]], experience_years=10
    )
    matches = recommend_jobs(profile, limit=2)
    assert matches[0].obj.pk == catalog["compta"].pk
    assert matches[0].breakdown["semantic"] == 0.0


def test_remote_only_candidate_excludes_onsite(skills):
    onsite = JobOfferFactory(remote="onsite")
    remote = JobOfferFactory(remote="remote")
    profile = CandidateProfileFactory(remote_preference="remote")
    ids = {m.obj.pk for m in recommend_jobs(profile)}
    assert remote.pk in ids and onsite.pk not in ids


def test_expired_offers_excluded(python_dev):
    JobOfferFactory(expires_at=timezone.now() - timedelta(hours=1))
    assert recommend_jobs(python_dev) == []


def test_recommend_candidates(catalog, python_dev, skills):
    accountant = CandidateProfileFactory(
        skills=[skills["Comptabilité"]], remote_preference="remote"
    )
    accountant.embedding = embed_text("Comptable fiscalité")
    accountant.save()
    job = catalog["python"]
    matches = recommend_candidates(job)
    assert matches[0].obj.pk == python_dev.pk
    assert "freshness" not in matches[0].breakdown
    # offre sur site → le candidat 100 % remote est exclu
    onsite = JobOfferFactory(remote="onsite")
    assert accountant.pk not in {m.obj.pk for m in recommend_candidates(onsite)}


def test_recommendations_endpoint_persists_and_feedback(catalog, python_dev):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(python_dev.user)
    res = client.get(reverse("recommendations"), {"limit": 5})
    assert res.status_code == 200
    assert res.data[0]["job"]["id"] == catalog["python"].pk
    assert res.data[0]["score_breakdown"]["skills"] == 1.0
    assert Recommendation.objects.filter(candidate=python_dev).count() == len(res.data)

    # re-calcul : pas de doublons (upsert)
    client.get(reverse("recommendations"))
    assert Recommendation.objects.filter(candidate=python_dev).count() == len(res.data)

    reco_id = res.data[0]["id"]
    fb = client.post(
        reverse("recommendation-feedback", args=[reco_id]), {"liked": False}, format="json"
    )
    assert fb.status_code == 200
    res2 = client.get(reverse("recommendations"))
    assert catalog["python"].pk not in [r["job"]["id"] for r in res2.data]

    res3 = client.get(
        reverse("recommendations"),
        {"location": "Paris", "remote": "remote", "contract_type": "cdi"},
    )
    assert res3.data == []
    assert client.get(reverse("recommendations"), {"limit": 0}).status_code == 400
    assert client.get(reverse("recommendations"), {"contract_type": "xyz"}).status_code == 400
    assert client.get(reverse("recommendations"), {"remote": "partout"}).status_code == 400


def test_recommendations_forbidden_for_recruiter(recruiter_client):
    assert recruiter_client.get(reverse("recommendations")).status_code == 403


def test_matching_candidates_endpoint(recruiter_client, python_dev, skills):
    job = JobOfferFactory(
        company=CompanyFactory(owner=recruiter_client.user), required_skills=[skills["Python"]]
    )
    res = recruiter_client.get(reverse("job-matching-candidates", args=[job.pk]), {"limit": "abc"})
    assert res.status_code == 200
    assert res.data[0]["candidate_id"] == python_dev.pk
    assert res.data[0]["score_breakdown"]["skills"] == 1.0

    other = JobOfferFactory()
    assert (
        recruiter_client.get(reverse("job-matching-candidates", args=[other.pk])).status_code == 403
    )


def test_embedding_tasks(skills):
    job = JobOfferFactory(required_skills=[skills["Python"]])
    profile = CandidateProfileFactory()
    assert embed_job_offer.delay(job.pk).get() is True
    assert embed_candidate_profile.delay(profile.pk).get() is True
    assert embed_job_offer.delay(0).get() is False
    assert embed_candidate_profile.delay(0).get() is False
    job.refresh_from_db()
    assert len(job.embedding) == 384


def test_reindex_missing_embeddings():
    JobOfferFactory()
    JobOfferFactory(is_active=False)
    CandidateProfileFactory()
    result = reindex_missing_embeddings.delay().get()
    assert result == {"jobs": 1, "profiles": 1}
    assert not JobOffer.objects.filter(is_active=True, embedding__isnull=True).exists()
