import mimetypes
from pathlib import PurePosixPath
from urllib.parse import quote

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, mixins, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.permissions import IsCandidate

from .models import CandidateProfile, Resume
from .serializers import CandidateProfileSerializer, ResumeSerializer
from .tasks import analyze_resume


def get_profile(user) -> CandidateProfile:
    profile, _ = CandidateProfile.objects.get_or_create(user=user)
    return profile


class CandidateMeView(generics.RetrieveUpdateAPIView):
    serializer_class = CandidateProfileSerializer
    permission_classes = [IsCandidate]

    def get_object(self):
        return get_profile(self.request.user)

    def perform_update(self, serializer):
        profile = serializer.save()
        from apps.matching.tasks import embed_candidate_profile

        transaction.on_commit(lambda: embed_candidate_profile.delay(profile.pk))


class ResumeViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ResumeSerializer
    permission_classes = [IsCandidate]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "uploads"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):  # génération du schéma OpenAPI
            return Resume.objects.none()
        return Resume.objects.filter(candidate__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resume = serializer.save(candidate=get_profile(request.user))
        transaction.on_commit(lambda: analyze_resume.delay(resume.pk))
        return Response(self.get_serializer(resume).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Téléchargement du CV, réservé à son propriétaire (les médias ne sont pas publics)."""
        resume = self.get_object()
        filename = PurePosixPath(resume.file.name).name
        if settings.RESUME_X_ACCEL_REDIRECT:
            # Django contrôle l'accès, nginx sert le fichier (location /media/ en `internal`).
            response = HttpResponse(
                content_type=mimetypes.guess_type(filename)[0] or "application/octet-stream"
            )
            internal_path = f"/{settings.MEDIA_URL.strip('/')}/{resume.file.name}"
            response["X-Accel-Redirect"] = quote(internal_path)
            response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response
        return FileResponse(resume.file.open("rb"), as_attachment=True, filename=filename)
