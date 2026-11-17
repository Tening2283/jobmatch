from django.contrib import admin

from .models import Company, JobOffer, JobSkill, Skill


class JobSkillInline(admin.TabularInline):
    model = JobSkill
    extra = 1


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "contract_type", "remote", "is_active", "created_at")
    list_filter = ("contract_type", "remote", "is_active")
    search_fields = ("title", "description")
    exclude = ("embedding",)
    inlines = [JobSkillInline]


admin.site.register(Skill)
admin.site.register(Company)
