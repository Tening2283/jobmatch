from django.contrib import admin

from .models import CandidateProfile, Resume


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "experience_years", "updated_at")
    exclude = ("embedding",)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "status", "created_at", "processed_at")
    list_filter = ("status",)
