import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.candidates.models import Resume
from apps.candidates.tasks import analyze_resume

from .conftest import SAMPLE_CV, make_pdf
from .factories import ResumeFactory

pytestmark = pytest.mark.django_db


def _upload(client, content: bytes, name="cv.pdf", content_type="application/pdf"):
    return client.post(
        reverse("resume-list"),
        {"file": SimpleUploadedFile(name, content, content_type=content_type)},
        format="multipart",
    )


def test_upload_pdf_is_analyzed_asynchronously(
    candidate_client, skills, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        res = _upload(candidate_client, make_pdf(SAMPLE_CV))
    assert res.status_code == 202
    assert res.data["status"] == "pending"

    detail = candidate_client.get(reverse("resume-detail", args=[res.data["id"]]))
    assert detail.data["status"] == "done"
    assert "Python" in detail.data["parsed_data"]["skills"]

    profile = candidate_client.profile
    profile.refresh_from_db()
    assert {"Python", "Django", "Docker"} <= set(profile.skills.values_list("name", flat=True))
    assert profile.experience_years >= 8
    assert profile.embedding is not None


def test_corrupted_file_marks_failed(candidate_client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        res = _upload(candidate_client, b"%PDF-broken")
    resume = Resume.objects.get(pk=res.data["id"])
    assert resume.status == Resume.Status.FAILED
    assert resume.error


def test_upload_validation(candidate_client, settings):
    res = _upload(candidate_client, b"x", name="cv.exe", content_type="application/x-msdownload")
    assert res.status_code == 400
    settings.RESUME_MAX_UPLOAD_MB = 0
    assert (
        _upload(candidate_client, b"abc", name="cv.txt", content_type="text/plain").status_code
        == 400
    )


def test_recruiter_cannot_upload(recruiter_client):
    assert _upload(recruiter_client, b"x").status_code == 403


def test_list_only_own_resumes_and_delete(candidate_client):
    mine = ResumeFactory(candidate=candidate_client.profile)
    ResumeFactory()
    res = candidate_client.get(reverse("resume-list"))
    assert [r["id"] for r in res.data["results"]] == [mine.id]
    assert candidate_client.delete(reverse("resume-detail", args=[mine.id])).status_code == 204


def test_resume_payload_hides_media_path(candidate_client):
    resume = ResumeFactory(candidate=candidate_client.profile)
    data = candidate_client.get(reverse("resume-detail", args=[resume.id])).data
    assert "file" not in data
    assert data["filename"].endswith(".txt")
    assert data["download_url"].endswith(reverse("resume-download", args=[resume.id]))


def test_download_own_resume_only(candidate_client):
    mine = ResumeFactory(candidate=candidate_client.profile)
    other = ResumeFactory()
    res = candidate_client.get(reverse("resume-download", args=[mine.id]))
    assert res.status_code == 200
    assert res["Content-Disposition"].startswith("attachment")
    assert b"".join(res.streaming_content) == b"Python Django Docker 5 ans d'experience"
    assert candidate_client.get(reverse("resume-download", args=[other.id])).status_code == 404


def test_download_delegates_to_nginx_in_production(candidate_client, settings):
    settings.RESUME_X_ACCEL_REDIRECT = True
    resume = ResumeFactory(candidate=candidate_client.profile)
    res = candidate_client.get(reverse("resume-download", args=[resume.id]))
    assert res.status_code == 200
    assert res["X-Accel-Redirect"] == f"/media/{resume.file.name}"
    assert res["Content-Type"] == "text/plain"
    assert res.content == b""


def test_analyze_missing_resume():
    assert analyze_resume.delay(999999).get() == "missing"


def test_analyze_does_not_decrease_experience(candidate_profile):
    candidate_profile.experience_years = 20
    candidate_profile.save()
    resume = ResumeFactory(candidate=candidate_profile)
    assert analyze_resume.delay(resume.pk).get() == "done"
    candidate_profile.refresh_from_db()
    assert candidate_profile.experience_years == 20


def test_analyze_retries_on_io_error(candidate_profile, mocker=None):
    from unittest import mock

    resume = ResumeFactory(candidate=candidate_profile)
    with mock.patch("django.db.models.fields.files.FieldFile.open", side_effect=OSError("disk")):
        result = analyze_resume.apply(args=[resume.pk])
    assert result.failed()
    assert isinstance(result.result, OSError)


def test_candidate_profile_update_triggers_embedding(
    candidate_client, skills, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        res = candidate_client.patch(
            reverse("candidate-me"),
            {
                "headline": "Data engineer",
                "skill_ids": [skills["Python"].id],
                "contract_types": ["cdi", "freelance"],
            },
            format="json",
        )
    assert res.status_code == 200
    assert [s["name"] for s in res.data["skills"]] == ["Python"]
    candidate_client.profile.refresh_from_db()
    assert candidate_client.profile.embedding is not None


def test_candidate_me_forbidden_for_recruiter(recruiter_client):
    assert recruiter_client.get(reverse("candidate-me")).status_code == 403
