from django.db import transaction
from rest_framework import serializers

from .models import Company, JobOffer, JobSkill, Skill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ("id", "name", "category", "aliases")


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ("id", "name", "description", "website", "location", "owner", "created_at")
        read_only_fields = ("id", "owner", "created_at")


class JobSkillSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="skill.id", read_only=True)
    name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = JobSkill
        fields = ("id", "name", "required")


class JobSkillInputSerializer(serializers.Serializer):
    skill = serializers.PrimaryKeyRelatedField(queryset=Skill.objects.all())
    required = serializers.BooleanField(default=True)


class JobOfferSerializer(serializers.ModelSerializer):
    skills = JobSkillSerializer(source="job_skills", many=True, read_only=True)
    skills_input = JobSkillInputSerializer(many=True, write_only=True, required=False)
    company_name = serializers.CharField(source="company.name", read_only=True)
    has_embedding = serializers.SerializerMethodField()

    class Meta:
        model = JobOffer
        fields = (
            "id",
            "title",
            "description",
            "company",
            "company_name",
            "recruiter",
            "skills",
            "skills_input",
            "min_experience_years",
            "location",
            "remote",
            "contract_type",
            "salary_min",
            "salary_max",
            "is_active",
            "expires_at",
            "has_embedding",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "recruiter", "created_at", "updated_at")

    def get_has_embedding(self, obj) -> bool:
        return obj.embedding is not None

    def validate_company(self, company):
        user = self.context["request"].user
        if company.owner_id != user.id and not user.is_staff:
            raise serializers.ValidationError("Vous n'êtes pas propriétaire de cette entreprise.")
        return company

    def validate(self, attrs):
        smin = attrs.get("salary_min", getattr(self.instance, "salary_min", None))
        smax = attrs.get("salary_max", getattr(self.instance, "salary_max", None))
        if smin is not None and smax is not None and smin > smax:
            raise serializers.ValidationError({"salary_max": "Doit être ≥ salary_min."})
        return attrs

    def _set_skills(self, job, skills_input):
        JobSkill.objects.filter(job=job).delete()
        JobSkill.objects.bulk_create(
            [
                JobSkill(job=job, skill=s["skill"], required=s.get("required", True))
                for s in skills_input
            ]
        )

    @transaction.atomic
    def create(self, validated_data):
        skills_input = validated_data.pop("skills_input", [])
        job = super().create(validated_data)
        self._set_skills(job, skills_input)
        return job

    @transaction.atomic
    def update(self, instance, validated_data):
        skills_input = validated_data.pop("skills_input", None)
        job = super().update(instance, validated_data)
        if skills_input is not None:
            self._set_skills(job, skills_input)
        return job
