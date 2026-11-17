import pytest
from django.urls import reverse

from apps.candidates.models import CandidateProfile

pytestmark = pytest.mark.django_db


def test_register_candidate_creates_profile_and_login(api_client):
    payload = {"email": "awa@example.com", "username": "awa", "password": "Tr3s-solide!"}
    res = api_client.post(reverse("register"), payload, format="json")
    assert res.status_code == 201
    assert res.data["role"] == "candidate"
    assert CandidateProfile.objects.filter(user__email="awa@example.com").exists()

    token = api_client.post(
        reverse("token_obtain_pair"), {"email": "awa@example.com", "password": "Tr3s-solide!"}
    )
    assert token.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.data['access']}")
    me = api_client.get(reverse("me"))
    assert me.data["email"] == "awa@example.com"

    refresh = api_client.post(reverse("token_refresh"), {"refresh": token.data["refresh"]})
    assert "access" in refresh.data


def test_register_recruiter_has_no_profile(api_client):
    payload = {
        "email": "rh@example.com",
        "username": "rh",
        "password": "Tr3s-solide!",
        "role": "recruiter",
    }
    res = api_client.post(reverse("register"), payload, format="json")
    assert res.status_code == 201
    assert not CandidateProfile.objects.filter(user__email="rh@example.com").exists()


def test_register_rejects_weak_password_and_admin_role(api_client):
    res = api_client.post(
        reverse("register"),
        {"email": "a@b.co", "username": "a", "password": "12345678"},
        format="json",
    )
    assert res.status_code == 400
    assert "error" in res.data
    res = api_client.post(
        reverse("register"),
        {"email": "x@b.co", "username": "x", "password": "Tr3s-solide!", "role": "admin"},
        format="json",
    )
    assert res.status_code == 400


def test_me_requires_auth(api_client):
    assert api_client.get(reverse("me")).status_code == 401


def test_me_update(candidate_client):
    res = candidate_client.patch(
        reverse("me"), {"first_name": "Awa", "role": "admin"}, format="json"
    )
    assert res.status_code == 200
    assert res.data["first_name"] == "Awa"
    assert res.data["role"] == "candidate"
