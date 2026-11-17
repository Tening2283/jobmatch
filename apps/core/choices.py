from django.db import models


class RemoteMode(models.TextChoices):
    ONSITE = "onsite", "Sur site"
    HYBRID = "hybrid", "Hybride"
    REMOTE = "remote", "Télétravail complet"


class ContractType(models.TextChoices):
    CDI = "cdi", "CDI"
    CDD = "cdd", "CDD"
    INTERNSHIP = "internship", "Stage"
    FREELANCE = "freelance", "Freelance"
    APPRENTICESHIP = "apprenticeship", "Alternance"
