"""Everything that changes a project, and the reads the conversation needs. Pure rules are in rules.py and program/draw.py; this
layer applies them to the database.

Every change takes the same two locks, in the same order: first the person's Profile row (so one person cannot start two
projects at once), then the project row (select_for_update), so two clicks on the same button cannot both win. SQLite ignores
select_for_update, so the database is in IMMEDIATE mode (settings.py), which serializes writers instead; on Postgres the row
locks do the work. The random generator is always passed in: random.SystemRandom() in production (views.py), a seeded one in tests.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import Profile
from accounts.services import profile_of
from ledger import services as ledger
from program import draw
from projects import rules
from projects.models import Category, Demand, Project, ProjectDemand, Subcategory
from projects.records import ProjectRow

NOT_ON_THE_TABLE = "That isn't on my table, dear. Pick one, two or three of the notes I dealt you."
NOT_DEALING = "There's nothing to keep, dear. You don't have a hand of mine on the go."
ALREADY_STARTED = "You've already started, dear. I'm not letting you swap now."


def working_project(user):
    """The one project this person is currently working on (dealing or building), or None."""
    return Project.objects.filter(user=user, status__in=rules.WORKING_STATUSES).select_related("category", "subcategory").first()


def other_projects(user, statuses=None, limit=30):
    """The person's projects that are not their working project, newest first, one query with select_related("category")."""
    qs = Project.objects.filter(user=user).exclude(status__in=rules.WORKING_STATUSES)
    if statuses is not None:
        qs = qs.filter(status__in=statuses)
    qs = qs.select_related("category").order_by("-id")[:limit]
    return [
        ProjectRow(
            id=p.id,
            name=p.name,
            status=p.status,
            status_label=rules.LABELS.get(p.status, p.status),
            hardware=p.category.kind == Category.Kind.HARDWARE,
            can_ship_build=p.status == rules.AWAITING_BUILD,
            can_finish=p.status == rules.AWAITING_BUILD,
        )
        for p in qs
    ]


def dealing_project(user):
    """The project whose hand is on the table (not yet confirmed), or None."""
    return Project.objects.filter(user=user, status=rules.DEALING).select_related("category").first()


def latest_project(user):
    return Project.objects.filter(user=user).select_related("category", "subcategory").first()


def category_choices():
    return tuple((c.slug, c.name) for c in Category.objects.filter(active=True))


def subcategory_choices(category_slug):
    """The subcategories offered for a category, as (id, name) pairs. Empty for an unknown or switched-off category."""
    rows = Subcategory.objects.filter(category__slug=category_slug, category__active=True, active=True)
    return tuple((str(s.pk), s.name) for s in rows)


def resolve(category_slug, subcategory_id):
    """The Category and Subcategory (or None) an answer names. ValidationError if they do not exist, are switched off or do
    not belong together."""
    category = Category.objects.filter(slug=category_slug, active=True).first()
    subcategory = Subcategory.objects.filter(pk=subcategory_id, category=category, active=True).first() if str(subcategory_id).isdigit() else None
    if category is None or (subcategory_id and subcategory is None) or (subcategory is None and subcategory_choices(category_slug)):
        raise ValidationError("I don't know that one, dear.")
    return category, subcategory


def cards():
    """Every demand in the jar as plain records for program.draw."""
    rows = Demand.objects.filter(active=True).prefetch_related("categories", "conflicts")
    return [draw.Card(d.id, d.tier, frozenset(c.id for c in d.categories.all()), frozenset(x.id for x in d.conflicts.all())) for d in rows]


def hand_demands(project):
    """The demands dealt to this project, in the order dealt (a demand deleted since is skipped)."""
    by_id = Demand.objects.in_bulk(project.hand)
    return [by_id[i] for i in project.hand if i in by_id]


def kept_demands(project):
    return [row.demand for row in project.kept.select_related("demand")]


def lock_person(user):
    """Serialize everything one person does to their projects (the same lock the cookie ledger takes)."""
    profile_of(user)
    Profile.objects.select_for_update().get(user=user)


def locked_project(user, *statuses):
    """The person's project in one of these statuses, row locked until the transaction ends. Not select_related: Postgres
    refuses FOR UPDATE on the nullable side of a join."""
    return Project.objects.select_for_update().filter(user=user, status__in=statuses).first()


def design_collected(project):
    """A hardware project whose design ship was approved and handed over (collected). Asked through the reverse relation so that
    projects never imports submissions; tests/test_projects_finish.py pins these words to submissions.rules.next_ship."""
    return project.category.kind == Category.Kind.HARDWARE and project.submissions.filter(stage="design", status="approved", claimed_at__isnull=False).exists()


def closed_without_build(project):
    """An approved hardware project that never had a build ship: the person closed it with the finish button."""
    return project.status == rules.APPROVED and design_collected(project) and not project.submissions.filter(stage="build").exists()


@transaction.atomic
def finish(user, pk):
    """The "I am done with this project" button, for a hardware project that sits in `awaiting_build` after its design ship was
    approved and collected: the build ship is optional (it may go to this program, another one, or nowhere). It becomes `approved`.
    Asking again on an already approved own hardware project is idempotent.
    Returns the project, or None when there is nothing to finish."""
    lock_person(user)
    project = Project.objects.select_for_update().filter(user=user, pk=pk).first()
    if project is None:
        return None
    if not design_collected(project) or project.status not in (rules.AWAITING_BUILD, rules.APPROVED):
        return None
    if project.status == rules.AWAITING_BUILD:
        project.status = rules.APPROVED
        project.save(update_fields=["status"])
    return project


@transaction.atomic
def start(user, *, idea, name, category, subcategory, size, rng):
    """Make the person's project and deal its first hand. Called when they have answered Grandma's four questions, and only
    then. A person with a project in progress gets that one back (a double click or a second tab starts nothing new)."""
    lock_person(user)
    existing = working_project(user)
    if existing:
        return existing
    project = Project(user=user, idea=idea, name=name, category=category, subcategory=subcategory,
                      hand=draw.deal(cards(), size, rng, category.id))
    project.full_clean()
    project.save()
    return project


@transaction.atomic
def redeal(user, *, expect, free, cost, size, rng):
    """Replace the hand. `expect` is the number of the re-deal the person was shown (1 for the first): a request that does not
    match the counter is a double click or a replay and changes nothing. The first `free` re-deals cost nothing, then each costs
    `cost` cookies through the ledger, under a key made from the project and the re-deal number. Raises
    ledger.rules.InsufficientCookies (and changes nothing) when they cannot pay. Returns the project, None if there is no hand."""
    lock_person(user)
    project = locked_project(user, rules.DEALING)
    if project is None:
        return None
    next_one = rules.offer(project.redeals_used, free, cost)
    if expect != next_one.number:
        return project
    if next_one.cost:
        ledger.debit(user, next_one.cost, reason=f"Grandma dealt again: {project.name}", key=f"redeal-{project.pk}-{next_one.number}")
    project.hand = draw.deal(cards(), size, rng, project.category_id)
    project.redeals_used = next_one.number
    project.save(update_fields=["hand", "redeals_used"])
    return project


@transaction.atomic
def keep(user, ids, now):
    """Confirm the notes the person keeps: one to three of the hand that was dealt, nothing else. The project becomes
    `building` and its clock starts. Asking again with the same notes is harmless; with other notes it is refused."""
    lock_person(user)
    project = locked_project(user, *rules.WORKING_STATUSES)
    try:
        kept = {int(i) for i in ids}
    except (TypeError, ValueError):
        raise ValidationError(NOT_ON_THE_TABLE) from None
    if project is None:
        raise ValidationError(NOT_DEALING)
    if project.status != rules.DEALING:
        if project.status == rules.BUILDING and kept == {d.id for d in kept_demands(project)}:
            return project
        raise ValidationError(ALREADY_STARTED)
    demands = Demand.objects.in_bulk(kept)
    if not draw.keeps_fit(kept, project.hand) or len(demands) != len(kept):
        raise ValidationError(NOT_ON_THE_TABLE)
    for order, demand_id in enumerate((i for i in project.hand if i in kept), start=1):
        ProjectDemand.objects.create(project=project, demand=demands[demand_id], order=order)
    project.status, project.started_at = rules.BUILDING, now
    project.save(update_fields=["status", "started_at"])
    return project
