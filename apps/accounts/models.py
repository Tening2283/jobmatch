from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CANDIDATE = "candidate", "Candidat"
        RECRUITER = "recruiter", "Recruteur"
        ADMIN = "admin", "Administrateur"

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CANDIDATE)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    @property
    def is_candidate(self) -> bool:
        return self.role == self.Role.CANDIDATE

    @property
    def is_recruiter(self) -> bool:
        return self.role == self.Role.RECRUITER
