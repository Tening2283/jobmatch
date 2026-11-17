import io

import pytest
from rest_framework.test import APIClient

from apps.jobs.models import Skill
from apps.matching.services.embedder import embed_text

from .factories import CandidateProfileFactory, CompanyFactory, RecruiterFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def candidate_profile(db):
    return CandidateProfileFactory()


@pytest.fixture
def candidate_client(candidate_profile):
    client = APIClient()
    client.force_authenticate(candidate_profile.user)
    client.profile = candidate_profile
    return client


@pytest.fixture
def recruiter(db):
    return RecruiterFactory()


@pytest.fixture
def recruiter_client(recruiter):
    client = APIClient()
    client.force_authenticate(recruiter)
    client.user = recruiter
    return client


@pytest.fixture
def company(recruiter):
    return CompanyFactory(owner=recruiter)


@pytest.fixture
def skills(db):
    """Compétences seedées par la migration 0002."""
    names = ["Python", "Django", "Docker", "React", "PostgreSQL", "Comptabilité", "Excel"]
    return {s.name: s for s in Skill.objects.filter(name__in=names)}


@pytest.fixture
def embed():
    return embed_text


def make_pdf(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in text.splitlines():
        c.drawString(40, y, line)
        y -= 16
    c.save()
    return buf.getvalue()


def make_docx(text: str) -> bytes:
    import docx

    document = docx.Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    table = document.add_table(rows=1, cols=1)
    table.rows[0].cells[0].text = "Kubernetes"
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


SAMPLE_CV = """Awa Diop
awa.diop@example.com  +221 77 123 45 67
Développeuse Backend
Expérience
Janvier 2018 - Décembre 2020 : Développeuse Python chez Orange
2021 - aujourd'hui : Lead dev Django, Docker, PostgreSQL
Compétences : Pyhton, React.js, Git, Anglais
"""
