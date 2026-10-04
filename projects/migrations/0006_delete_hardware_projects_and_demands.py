"""Data migration: delete hardware projects, hardware demands, and hardware categories. Reverse is no-op."""
from django.db import migrations, models

HARDWARE_DEMANDS = [
    "Single Pin",
    "Battery Only",
    "No Soldering",
    "No Microcontroller",
    "Single-Sided PCB",
    "Salvaged",
    "No Supports",
    "Snap-Fit",
    "Parametric",
    "Print-in-Place",
]
HARDWARE_CATEGORIES = ["electronics", "cad"]
OTHER_DEMANDS = ["Tiny", "Two Colors", "No Jargon"]


def delete_hardware_projects_and_demands(apps, schema_editor):
    Category = apps.get_model("projects", "Category")
    Subcategory = apps.get_model("projects", "Subcategory")
    Demand = apps.get_model("projects", "Demand")
    Project = apps.get_model("projects", "Project")
    ProjectDemand = apps.get_model("projects", "ProjectDemand")

    hardware_projects = Project.objects.filter(
        models.Q(category__slug__in=HARDWARE_CATEGORIES) | models.Q(status="awaiting_build")
    )
    hardware_demands = Demand.objects.filter(name__in=HARDWARE_DEMANDS)

    ProjectDemand.objects.filter(
        models.Q(project__in=hardware_projects) | models.Q(demand__in=hardware_demands)
    ).delete()

    hardware_projects.delete()

    for demand in hardware_demands:
        demand.conflicts.clear()
        demand.categories.clear()

    for category in Category.objects.filter(slug__in=HARDWARE_CATEGORIES):
        category.demands.clear()

    hardware_demands.delete()

    Subcategory.objects.filter(category__slug__in=HARDWARE_CATEGORIES).delete()
    Category.objects.filter(slug__in=HARDWARE_CATEGORIES).delete()

    # 0003 reads the live CATEGORIES (now 3), so on a fresh database it linked every demand fitting those 3 to Other: keep only the real three.
    other = Category.objects.filter(slug="other").first()
    if other:
        other.demands.remove(*other.demands.exclude(name__in=OTHER_DEMANDS))


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0005_one_working_project_per_user"),
        ("submissions", "0005_delete_hardware_submissions"),
        ("orders", "0003_delete_hardware_orders"),
    ]

    operations = [
        migrations.RunPython(delete_hardware_projects_and_demands, migrations.RunPython.noop),
    ]
