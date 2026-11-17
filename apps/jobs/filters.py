import django_filters

from .models import JobOffer


class JobOfferFilter(django_filters.FilterSet):
    skill = django_filters.CharFilter(field_name="skills__name", lookup_expr="iexact")
    location = django_filters.CharFilter(lookup_expr="icontains")
    salary_min = django_filters.NumberFilter(field_name="salary_max", lookup_expr="gte")
    company = django_filters.NumberFilter(field_name="company_id")

    class Meta:
        model = JobOffer
        fields = ("contract_type", "remote", "is_active", "skill", "location", "company")
