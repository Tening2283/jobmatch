from rest_framework.routers import DefaultRouter

from .views import CompanyViewSet, JobOfferViewSet, SkillViewSet

router = DefaultRouter()
router.register("skills", SkillViewSet, basename="skill")
router.register("companies", CompanyViewSet, basename="company")
router.register("jobs", JobOfferViewSet, basename="job")

urlpatterns = router.urls
