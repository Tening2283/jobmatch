from rest_framework import serializers

from apps.core.choices import ContractType, RemoteMode
from apps.jobs.serializers import JobOfferSerializer

from .models import Recommendation


class ScoreBreakdownSerializer(serializers.Serializer):
    semantic = serializers.FloatField()
    skills = serializers.FloatField()
    experience = serializers.FloatField()
    location = serializers.FloatField()
    salary = serializers.FloatField()
    freshness = serializers.FloatField(required=False)


class RecommendationSerializer(serializers.ModelSerializer):
    job = JobOfferSerializer(read_only=True)
    score_breakdown = ScoreBreakdownSerializer(read_only=True)

    class Meta:
        model = Recommendation
        fields = ("id", "score", "score_breakdown", "liked", "applied", "job", "updated_at")


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ("liked", "applied")


class CandidateMatchSerializer(serializers.Serializer):
    candidate_id = serializers.IntegerField(source="obj.id")
    email = serializers.EmailField(source="obj.user.email")
    headline = serializers.CharField(source="obj.headline")
    location = serializers.CharField(source="obj.location")
    experience_years = serializers.IntegerField(source="obj.experience_years")
    score = serializers.FloatField()
    score_breakdown = serializers.DictField(source="breakdown", child=serializers.FloatField())


class RecommendationQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)
    contract_type = serializers.ChoiceField(choices=ContractType.choices, required=False)
    remote = serializers.ChoiceField(choices=RemoteMode.choices, required=False)
    location = serializers.CharField(required=False, max_length=120)
