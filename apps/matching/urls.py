from django.urls import path

from .views import JobMatchingCandidatesView, RecommendationFeedbackView, RecommendationListView

urlpatterns = [
    path("recommendations/", RecommendationListView.as_view(), name="recommendations"),
    path(
        "recommendations/<int:pk>/feedback/",
        RecommendationFeedbackView.as_view(),
        name="recommendation-feedback",
    ),
    path(
        "jobs/<int:pk>/matching-candidates/",
        JobMatchingCandidatesView.as_view(),
        name="job-matching-candidates",
    ),
]
