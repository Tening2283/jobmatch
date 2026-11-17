import factory
from django.contrib.auth import get_user_model

from apps.candidates.models import CandidateProfile, Resume
from apps.core.choices import ContractType, RemoteMode
from apps.jobs.models import Company, JobOffer, JobSkill, Skill

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    role = User.Role.CANDIDATE
    password = factory.PostGenerationMethodCall("set_password", "S3cure-pass!")

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class RecruiterFactory(UserFactory):
    role = User.Role.RECRUITER


class CandidateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CandidateProfile
        skip_postgeneration_save = True

    user = factory.SubFactory(UserFactory)
    headline = "Développeur backend Python"
    location = "Dakar"
    remote_preference = RemoteMode.HYBRID
    experience_years = 3

    @factory.post_generation
    def skills(self, create, extracted, **kwargs):
        if create and extracted:
            self.skills.add(*extracted)


class SkillFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Skill
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Skill{n}")


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Sequence(lambda n: f"Entreprise {n}")
    owner = factory.SubFactory(RecruiterFactory)
    location = "Dakar"


class JobOfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobOffer
        skip_postgeneration_save = True

    title = "Développeur Python"
    description = "Nous cherchons un développeur Python Django."
    company = factory.SubFactory(CompanyFactory)
    recruiter = factory.SelfAttribute("company.owner")
    location = "Dakar"
    remote = RemoteMode.HYBRID
    contract_type = ContractType.CDI
    min_experience_years = 2

    @factory.post_generation
    def required_skills(self, create, extracted, **kwargs):
        if create and extracted:
            JobSkill.objects.bulk_create(
                [JobSkill(job=self, skill=s, required=True) for s in extracted]
            )

    @factory.post_generation
    def optional_skills(self, create, extracted, **kwargs):
        if create and extracted:
            JobSkill.objects.bulk_create(
                [JobSkill(job=self, skill=s, required=False) for s in extracted]
            )


class ResumeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Resume

    candidate = factory.SubFactory(CandidateProfileFactory)
    file = factory.django.FileField(
        filename="cv.txt", data=b"Python Django Docker 5 ans d'experience"
    )
