from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsCandidate, IsRecruiter
from apps.candidates.views import get_profile
from apps.jobs.models import JobOffer

from .models import Recommendation
from .serializers import (
    CandidateMatchSerializer,
    FeedbackSerializer,
    RecommendationQuerySerializer,
    RecommendationSerializer,
)
from .services.engine import recommend_candidates, recommend_jobs


class RecommendationListView(APIView):
    """Offres recommandées pour le candidat connecté, avec score explicable."""

    permission_classes = [IsCandidate]

    @extend_schema(
        parameters=[RecommendationQuerySerializer],
        responses=RecommendationSerializer(many=True),
    )
    def get(self, request):
        params = RecommendationQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        data = params.validated_data
        profile = get_profile(request.user)

        filters = Q()
        if "contract_type" in data:
            filters &= Q(contract_type=data["contract_type"])
        if "remote" in data:
            filters &= Q(remote=data["remote"])
        if "location" in data:
            filters &= Q(location__icontains=data["location"])

        disliked = set(
            Recommendation.objects.filter(candidate=profile, liked=False).values_list(
                "job_id", flat=True
            )
        )
        matches = recommend_jobs(
            profile, limit=data["limit"], extra_filters=filters, exclude_ids=disliked
        )

        Recommendation.objects.bulk_create(
            [
                Recommendation(
                    candidate=profile, job=m.obj, score=m.score, score_breakdown=m.breakdown
                )
                for m in matches
            ],
            update_conflicts=True,
            unique_fields=["candidate", "job"],
            update_fields=["score", "score_breakdown", "updated_at"],
        )
        by_job = {
            r.job_id: r
            for r in Recommendation.objects.filter(
                candidate=profile, job_id__in=[m.obj.pk for m in matches]
            )
            .select_related("job__company")
            .prefetch_related("job__job_skills__skill")
        }
        ordered = [by_job[m.obj.pk] for m in matches]
        return Response(RecommendationSerializer(ordered, many=True).data)


class RecommendationFeedbackView(generics.UpdateAPIView):
    serializer_class = FeedbackSerializer
    permission_classes = [IsCandidate]
    http_method_names = ["patch", "post"]

    def get_queryset(self):
        return Recommendation.objects.filter(candidate__user=self.request.user)

    def post(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)


class JobMatchingCandidatesView(APIView):
    """Meilleurs candidats pour une offre (réservé au recruteur propriétaire)."""

    permission_classes = [IsRecruiter]

    @extend_schema(
        parameters=[OpenApiParameter("limit", int, required=False)],
        responses=CandidateMatchSerializer(many=True),
    )
    def get(self, request, pk: int):
        job = get_object_or_404(JobOffer.objects.prefetch_related("job_skills"), pk=pk)
        if job.recruiter_id != request.user.id and not request.user.is_staff:
            return Response(
                {"error": {"status": 403, "detail": "Offre d'un autre recruteur."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            limit = min(max(int(request.query_params.get("limit", 20)), 1), 100)
        except ValueError:
            limit = 20
        matches = recommend_candidates(job, limit=limit)
        return Response(CandidateMatchSerializer(matches, many=True).data)
