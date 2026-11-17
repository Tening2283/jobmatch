from pathlib import PurePosixPath

from django.conf import settings
from rest_framework import serializers
from rest_framework.reverse import reverse

from apps.core.choices import ContractType
from apps.jobs.models import Skill
from apps.jobs.serializers import SkillSerializer

from .models import CandidateProfile, Resume

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "application/octet-stream",
}


class CandidateProfileSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)
    skill_ids = serializers.PrimaryKeyRelatedField(
        source="skills", queryset=Skill.objects.all(), many=True, write_only=True, required=False
    )
    contract_types = serializers.ListField(
        child=serializers.ChoiceField(choices=ContractType.choices), required=False
    )
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = CandidateProfile
        fields = (
            "id",
            "email",
            "headline",
            "summary",
            "location",
            "remote_preference",
            "contract_types",
            "expected_salary",
            "experience_years",
            "skills",
            "skill_ids",
            "updated_at",
        )
        read_only_fields = ("id", "updated_at")


class ResumeSerializer(serializers.ModelSerializer):
    filename = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Resume
        fields = (
            "id",
            "file",
            "filename",
            "download_url",
            "status",
            "parsed_data",
            "error",
            "created_at",
            "processed_at",
        )
        read_only_fields = ("id", "status", "parsed_data", "error", "created_at", "processed_at")
        # Le chemin média n'est jamais exposé (nginx le sert en `internal`) :
        # on passe par `download_url`, qui contrôle l'accès.
        extra_kwargs = {"file": {"write_only": True}}

    def get_filename(self, obj) -> str:
        return PurePosixPath(obj.file.name).name

    def get_download_url(self, obj) -> str:
        return reverse("resume-download", args=[obj.pk], request=self.context.get("request"))

    def validate_file(self, file):
        max_bytes = settings.RESUME_MAX_UPLOAD_MB * 1024 * 1024
        if file.size > max_bytes:
            raise serializers.ValidationError(
                f"Fichier trop volumineux (max {settings.RESUME_MAX_UPLOAD_MB} Mo)."
            )
        content_type = getattr(file, "content_type", None)
        if content_type and content_type not in ALLOWED_CONTENT_TYPES:
            raise serializers.ValidationError(f"Type de fichier non autorisé : {content_type}.")
        return file
