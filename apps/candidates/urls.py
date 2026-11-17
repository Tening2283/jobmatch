from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CandidateMeView, ResumeViewSet

router = DefaultRouter()
router.register("resumes", ResumeViewSet, basename="resume")

urlpatterns = [path("candidates/me/", CandidateMeView.as_view(), name="candidate-me"), *router.urls]
