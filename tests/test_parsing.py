from datetime import date

import pytest

from apps.candidates.parsing import (
    ResumeParsingError,
    extract_experience_years,
    extract_skills,
    extract_text,
    parse_resume,
)

from .conftest import SAMPLE_CV, make_docx, make_pdf

TAXONOMY = {
    "Python": ["py"],
    "Django": ["drf"],
    "Docker": [],
    "React": ["react.js", "reactjs"],
    "PostgreSQL": ["postgres"],
    "C++": ["cpp"],
    "Go": ["golang"],
    "Kubernetes": ["k8s"],
}


def test_extract_text_pdf():
    text = extract_text(make_pdf("Python Django\nDocker"), "cv.pdf")
    assert "Python" in text and "Docker" in text


def test_extract_text_docx_includes_tables():
    text = extract_text(make_docx("Python\n\n\nDjango"), "cv.docx")
    assert "Django" in text and "Kubernetes" in text
    assert "\n\n" not in text


def test_extract_text_txt():
    assert extract_text(b"Bonjour   monde", "cv.txt") == "Bonjour monde"


def test_extract_text_unsupported_format():
    with pytest.raises(ResumeParsingError, match="non supporté"):
        extract_text(b"x", "cv.odt")


def test_extract_text_corrupted_pdf():
    with pytest.raises(ResumeParsingError, match="Impossible"):
        extract_text(b"not a pdf", "cv.pdf")


def test_extract_text_empty():
    with pytest.raises(ResumeParsingError, match="Aucun texte"):
        extract_text(b"   ", "cv.txt")


def test_extract_skills_exact_alias_and_fuzzy():
    found = extract_skills("Je maîtrise Pyhton, ReactJS et postgres. Pas de Golang.", TAXONOMY)
    assert found == ["Go", "PostgreSQL", "Python", "React"]


def test_extract_skills_word_boundaries():
    # "Go" ne doit pas matcher "Google", ni "C++" sans le terme
    assert extract_skills("J'ai travaillé chez Google en C", TAXONOMY) == []
    assert extract_skills("Expert C++ et k8s", TAXONOMY) == ["C++", "Kubernetes"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("5 ans d'expérience en développement", 5),
        ("Over 7 years of experience", 7),
        ("Janvier 2018 - Décembre 2020\n2021 - aujourd'hui", 9),
        ("03/2015 - 03/2017 puis 2016 - 2018", 3),  # chevauchement fusionné
        ("Aucune date ici", 0),
    ],
)
def test_extract_experience_years(text, expected):
    assert extract_experience_years(text, today=date(2026, 11, 1)) == expected


def test_parse_resume_full():
    parsed = parse_resume(SAMPLE_CV, TAXONOMY, today=date(2026, 11, 1))
    assert parsed.email == "awa.diop@example.com"
    assert parsed.phone.startswith("+221")
    assert {"Python", "Django", "Docker", "PostgreSQL", "React"} <= set(parsed.skills)
    assert parsed.experience_years == 9
    assert parsed.to_dict()["word_count"] > 10


def test_extract_skills_dotted_suffix_is_not_an_alias():
    # "React.js" ne doit pas déclencher l'alias "js" de JavaScript
    taxonomy = {"React": ["react.js"], "JavaScript": ["js"], "Node.js": ["nodejs"]}
    assert extract_skills("React.js et Node.js", taxonomy) == ["Node.js", "React"]
    assert extract_skills("JS, TypeScript", taxonomy) == ["JavaScript"]
