"""Extraction de texte et d'informations structurées à partir d'un CV."""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from rapidfuzz import fuzz


class ResumeParsingError(Exception):
    pass


# --------------------------------------------------------------------------- texte
def extract_text(content: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == ".docx":
            import docx

            document = docx.Document(io.BytesIO(content))
            parts = [p.text for p in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    parts.extend(cell.text for cell in row.cells)
            text = "\n".join(parts)
        elif ext == ".txt":
            text = content.decode("utf-8", errors="ignore")
        else:
            raise ResumeParsingError(f"Format non supporté : {ext}")
    except ResumeParsingError:
        raise
    except Exception as exc:  # fichier corrompu
        raise ResumeParsingError(f"Impossible de lire le fichier : {exc}") from exc

    text = clean_text(text)
    if not text:
        raise ResumeParsingError("Aucun texte exploitable (CV scanné ?).")
    return text


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    return "".join(c for c in value if not unicodedata.combining(c))


# --------------------------------------------------------------------------- compétences
def extract_skills(
    text: str, taxonomy: dict[str, list[str]], fuzzy_threshold: int = 80
) -> list[str]:
    """Retourne les noms canoniques des compétences présentes dans le texte.

    `taxonomy` : {nom canonique: [alias, ...]}. Recherche exacte par frontières de mots,
    puis repli fuzzy sur les n-grammes (≤ 3 tokens) pour tolérer les fautes de frappe
    (termes ≥ 6 caractères, même initiale, pour limiter les faux positifs).
    """
    norm_text = normalize(text)
    tokens = re.findall(r"[a-z0-9#+./-]+", norm_text)
    ngrams = {" ".join(tokens[i : i + n]) for n in (1, 2, 3) for i in range(len(tokens) - n + 1)}
    found: list[str] = []
    for name, aliases in taxonomy.items():
        terms = [normalize(t) for t in [name, *aliases]]
        if any(_contains_term(norm_text, t) for t in terms):
            found.append(name)
            continue
        long_terms = [t for t in terms if len(t) >= 6]
        if long_terms and any(
            g[0] == t[0] and fuzz.ratio(t, g) >= fuzzy_threshold for t in long_terms for g in ngrams
        ):
            found.append(name)
    return sorted(found)


def _contains_term(text: str, term: str) -> bool:
    pattern = r"(?<![a-z0-9.])" + re.escape(term) + r"(?![a-z0-9#+])"
    return re.search(pattern, text) is not None


# --------------------------------------------------------------------------- expérience
_MONTHS = {
    "jan": 1, "janv": 1, "janvier": 1, "january": 1,
    "fev": 2, "fevr": 2, "fevrier": 2, "feb": 2, "february": 2,
    "mar": 3, "mars": 3, "march": 3,
    "avr": 4, "avril": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6,
    "juil": 7, "juillet": 7, "jul": 7, "july": 7,
    "aou": 8, "aout": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "septembre": 9, "september": 9,
    "oct": 10, "octobre": 10, "october": 10,
    "nov": 11, "novembre": 11, "november": 11,
    "dec": 12, "decembre": 12, "december": 12,
}  # fmt: skip

_DATE = r"(?:(?P<{p}m>[a-z]+\.?|\d{{1,2}})[\s/.-]*)?(?P<{p}y>(?:19|20)\d{{2}})"
_PRESENT = r"(?P<present>aujourd'hui|aujourd hui|present|actuel|maintenant|now|current|ce jour)"
_PERIOD_RE = re.compile(
    _DATE.format(p="s")
    + r"\s*(?:-|–|—|a|à|to|au)\s*(?:"
    + _DATE.format(p="e")
    + "|"
    + _PRESENT
    + ")"
)
_YEARS_RE = re.compile(r"(\d{1,2})\+?\s*(?:ans|annees|years?)\s+d['e ]\s*(?:experience|exp)")
_YEARS_EN_RE = re.compile(r"(\d{1,2})\+?\s*years?\s+(?:of\s+)?experience")


def _month(token: str | None) -> int:
    if not token:
        return 1
    token = token.strip(".")
    if token.isdigit():
        return min(max(int(token), 1), 12)
    return _MONTHS.get(token, _MONTHS.get(token[:4], _MONTHS.get(token[:3], 1)))


def extract_experience_years(text: str, today: date | None = None) -> int:
    """Estime les années d'expérience : mention explicite, sinon union des périodes datées."""
    today = today or date.today()
    norm = normalize(text)

    explicit = [int(m) for m in _YEARS_RE.findall(norm) + _YEARS_EN_RE.findall(norm)]
    if explicit:
        return max(explicit)

    intervals: list[tuple[int, int]] = []
    for m in _PERIOD_RE.finditer(norm):
        start = int(m["sy"]) * 12 + _month(m["sm"]) - 1
        if m["present"]:
            end = today.year * 12 + today.month - 1
        else:
            end = int(m["ey"]) * 12 + _month(m["em"]) - 1
        if 0 < end - start < 50 * 12:
            intervals.append((start, end))

    if not intervals:
        return 0
    intervals.sort()
    total, (cur_s, cur_e) = 0, intervals[0]
    for s, e in intervals[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return round(total / 12)


# --------------------------------------------------------------------------- contacts
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\d[\s.-]?){8,12}\d")


@dataclass
class ParsedResume:
    skills: list[str] = field(default_factory=list)
    experience_years: int = 0
    email: str | None = None
    phone: str | None = None
    word_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def parse_resume(
    text: str, taxonomy: dict[str, list[str]], today: date | None = None
) -> ParsedResume:
    email = _EMAIL_RE.search(text)
    phone = _PHONE_RE.search(text)
    return ParsedResume(
        skills=extract_skills(text, taxonomy),
        experience_years=extract_experience_years(text, today=today),
        email=email.group(0) if email else None,
        phone=phone.group(0).strip() if phone else None,
        word_count=len(text.split()),
    )
