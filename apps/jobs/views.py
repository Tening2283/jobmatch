from django.db.models import Q
from rest_framework import permissions, viewsets

from apps.accounts.permissions import IsOwnerOrReadOnly, IsRecruiter

from .filters import JobOfferFilter
from .models import Company, JobOffer, Skill
from .serializers import CompanySerializer, JobOfferSerializer, SkillSerializer


class RecruiterWritePermissionMixin:
    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsRecruiter(), IsOwnerOrReadOnly()]


class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [permissions.AllowAny]
    search_fields = ("name", "category")
    filterset_fields = ("category",)
    pagination_class = None


class CompanyViewSet(RecruiterWritePermissionMixin, viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    search_fields = ("name", "location")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class JobOfferViewSet(RecruiterWritePermissionMixin, viewsets.ModelViewSet):
    serializer_class = JobOfferSerializer
    filterset_class = JobOfferFilter
    search_fields = ("title", "description", "company__name")
    ordering_fields = ("created_at", "salary_max", "min_experience_years")

    def get_queryset(self):
        qs = JobOffer.objects.select_related("company").prefetch_related("job_skills__skill")
        user = self.request.user
        if self.action in ("list", "retrieve") and not (user.is_authenticated and user.is_staff):
            # Public : offres actives uniquement ; un recruteur voit en plus ses propres
            # offres inactives, mais jamais celles des autres recruteurs.
            visible = Q(is_active=True)
            if user.is_authenticated and user.is_recruiter:
                visible |= Q(recruiter=user)
            qs = qs.filter(visible)
        return qs

    def perform_create(self, serializer):
        serializer.save(recruiter=self.request.user)
