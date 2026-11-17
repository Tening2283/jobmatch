from django.contrib import admin

from .models import Recommendation


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "score", "liked", "applied", "updated_at")
    list_filter = ("liked", "applied")
