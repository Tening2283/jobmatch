from django.db import migrations


def seed(apps, schema_editor):
    from apps.jobs.skills_data import SKILLS

    Skill = apps.get_model("jobs", "Skill")
    for name, category, aliases in SKILLS:
        Skill.objects.update_or_create(name=name, defaults={"category": category, "aliases": aliases})


def unseed(apps, schema_editor):
    from apps.jobs.skills_data import SKILLS

    apps.get_model("jobs", "Skill").objects.filter(name__in=[s[0] for s in SKILLS]).delete()


class Migration(migrations.Migration):
    dependencies = [("jobs", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
