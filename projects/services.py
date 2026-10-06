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
from audit import services as audit
from ledger import services as ledger
from program import draw
from projects import rules
from projects.models import Category, Demand, Project, ProjectDemand, Subcategory
from projects.records import ProjectRow

NOT_ON_THE_TABLE = "That isn't on my table, dear. Pick one, two or three of the notes I dealt you."
NOT_DEALING = "There's nothing to keep, dear. You don't have a hand of mine on the go."
ALREADY_STARTED = "You've already started, dear. I'm not letting you swap now."
NOTHING_NEW = "That is everything I have for you, dear."


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
            public_id=p.public_id,
            name=p.name,
            status=p.status,
            status_label=rules.LABELS.get(p.status, p.status),
        )
        for p in qs
    ]


def change_note(project):
    """What the reviewer asked to change, once Grandma has told the person: the public note of the project's latest handed-over round.
    Read through the reverse name `submissions`, so this layer never imports the app that sits above it."""
    note = project.submissions.filter(claimed_at__isnull=False).order_by("-round", "-id").values_list("public_note", flat=True).first()
    return (note or "").strip()


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
    subcategory = Subcategory.objects.filter(pk=subcategory_id, category=category, active=True).first() if str(subcategory_id).isascii() and str(subcategory_id).isdigit() else None
    if category is None or (subcategory_id and subcategory is None) or (subcategory is None and subcategory_choices(category_slug)):
        raise ValidationError("I don't know that one, dear.")
    return category, subcategory


def cards():
    """Every demand in the jar as plain records for program.draw."""
    rows = Demand.objects.filter(active=True).prefetch_related("categories", "conflicts", "excluded_subcategories")
    return [draw.Card(d.id, d.tier, frozenset(c.id for c in d.categories.all()), frozenset(x.id for x in d.conflicts.all()),
                      frozenset(s.id for s in d.excluded_subcategories.all())) for d in rows]


def eligible_demands(category_id, subcategory_id):
    """The demands a project of this category and subcategory (ids; no subcategory excludes nothing) may hold: the category is one of the
    demand's and the subcategory is not one it excludes. Active or not (a demand switched off stays in the hands that hold it; add
    active=True to deal). The same rule as program.draw.fits, which tests pin to this one: every path that decides whether a note suits a
    project (what is shown, kept, re-kept, dropped by an edit, handed in) asks here."""
    fitting = Demand.objects.filter(categories=category_id)
    return fitting if subcategory_id is None else fitting.exclude(excluded_subcategories=subcategory_id)


def unfit_kept(project):
    """The kept notes (ProjectDemand rows) that do not suit the project's category and subcategory now. An edit drops them at once, so only
    staff can leave one behind (a project's kind or a demand's exclusions changed in the admin)."""
    return project.kept.exclude(demand__in=eligible_demands(project.category_id, project.subcategory_id))


def hand_demands(project):
    """The demands dealt to this project that suit its current category and subcategory, in the order dealt (a demand deleted since is
    skipped). The stored hand itself is never filtered or changed: the rest is only not shown, and shows again if the kind changes back."""
    by_id = eligible_demands(project.category_id, project.subcategory_id).in_bulk(project.hand)
    return [by_id[i] for i in project.hand if i in by_id]


def can_redeal(project, size):
    """Could another deal change the notes this project shows? Not for a kind with so few demands that every hand is the same
    (Other): that re-deal is never offered and never charged (program.draw.can_change)."""
    return draw.can_change(cards(), [d.id for d in hand_demands(project)], size, project.category_id, project.subcategory_id)


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


@transaction.atomic
def start(user, *, idea, name, category, subcategory, size, rng):
    """Make the person's project and deal its first hand. Called when they have answered Grandma's four questions, and only
    then. A person with a project in progress gets that one back (a double click or a second tab starts nothing new)."""
    lock_person(user)
    existing = working_project(user)
    if existing:
        return existing
    project = Project(user=user, idea=idea, name=name, category=category, subcategory=subcategory,
                      hand=draw.deal(cards(), size, rng, category.id, subcategory.id if subcategory else None))
    project.full_clean()
    project.save()
    audit.record(
        "project.start",
        actor=user,
        subject=user,
        target=project,
        details={
            "category": category.id,
            "subcategory": subcategory.id if subcategory else None,
            "hand": list(project.hand),
            "size": size,
        },
    )
    return project


@transaction.atomic
def redeal(user, *, expect, free, cost, size, rng):
    """Replace the hand. `expect` is the number of the re-deal the person was shown (1 for the first): a request that does not
    match the counter is a double click or a replay and changes nothing. The first `free` re-deals cost nothing, then each costs
    `cost` cookies through the ledger, under a key made from the project and the re-deal number. Raises
    ledger.rules.InsufficientCookies (and changes nothing) when they cannot pay, and ValidationError (NOTHING_NEW, nothing charged,
    nothing written) when no deal could differ from the hand they hold. Returns the project, None if there is no hand."""
    lock_person(user)
    project = locked_project(user, *rules.WORKING_STATUSES)
    if project is None:
        return None
    if not can_redeal(project, size):
        raise ValidationError(NOTHING_NEW)
    next_one = rules.offer(project.redeals_used, free, cost)
    if expect != next_one.number:
        return project
    if next_one.cost:
        ledger.debit(user, next_one.cost, reason=f"Grandma dealt again: {project.name}", key=f"redeal-{project.pk}-{next_one.number}")
    if project.status == rules.BUILDING:
        project.kept.all().delete()
        project.status = rules.DEALING
    project.hand = draw.deal(cards(), size, rng, project.category_id, project.subcategory_id)
    project.redeals_used = next_one.number
    project.save(update_fields=["hand", "redeals_used", "status"])
    audit.record(
        "project.redeal",
        actor=user,
        subject=user,
        target=project,
        details={"number": next_one.number, "cost": next_one.cost, "hand": list(project.hand)},
    )
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
    demands = eligible_demands(project.category_id, project.subcategory_id).in_bulk(kept)
    if not draw.keeps_fit(kept, project.hand) or len(demands) != len(kept):
        raise ValidationError(NOT_ON_THE_TABLE)
    kept_in_order = [i for i in project.hand if i in kept]
    for order, demand_id in enumerate(kept_in_order, start=1):
        ProjectDemand.objects.create(project=project, demand=demands[demand_id], order=order)
    if project.started_at is None:
        project.started_at = now
    project.status = rules.BUILDING
    project.save(update_fields=["status", "started_at"])
    audit.record(
        "project.keep",
        actor=user,
        subject=user,
        target=project,
        details={"kept": kept_in_order},
    )
    return project


def drop_unfit_kept(project):
    """Delete the kept notes that do not suit the project's category and subcategory and number the rest 1, 2, 3 again (a lower number
    is always free by then, so the unique order never clashes)."""
    unfit_kept(project).delete()
    for order, row in enumerate(project.kept.order_by("order"), start=1):
        if row.order != order:
            row.order = order
            row.save(update_fields=["order"])


@transaction.atomic
def edit_project(user, idea, name, category_value, subcategory_value):
    """Update a working project's details without touching the hand or redeals counter: an edit never creates a note. If the category
    or the subcategory changed, remove the kept demands that do not suit the new kind (eligible_demands) and number the rest again. If
    building and no kept demands remain, revert status to dealing. No audit entry is recorded."""
    lock_person(user)
    project = locked_project(user, *rules.WORKING_STATUSES)
    if project is None:
        raise ValidationError("You don't have a project to edit, dear.")
    category, subcategory = resolve(category_value, subcategory_value)
    kind_changed = (project.category_id, project.subcategory_id) != (category.id, subcategory.id if subcategory else None)
    project.idea = idea
    project.name = name
    project.category = category
    project.subcategory = subcategory
    if kind_changed:
        drop_unfit_kept(project)
        if project.status == rules.BUILDING and not project.kept.exists():
            project.status = rules.DEALING
    project.full_clean()
    project.save(update_fields=["idea", "name", "category", "subcategory", "status"])
    return project


@transaction.atomic
def rename_project(user, name, idea):
    """Change only the name and the description (the idea) of a project that is being worked on or has changes requested: the kind, the hand, the kept
    demands and the re-deal counter are not touched. The audit entry carries neither (free text)."""
    lock_person(user)
    project = locked_project(user, *rules.WORKING_STATUSES, rules.CHANGES_REQUESTED)
    if project is None:
        raise ValidationError("You don't have a project to rename, dear.")
    project.name = name
    project.idea = idea
    project.full_clean()
    project.save(update_fields=["name", "idea"])
    audit.record("project.rename", actor=user, subject=user, target=project)
    return project


@transaction.atomic
def rekeep(user, ids, now):
    """Confirm the new notes kept for a building project: one to three distinct ids from the persisted hand that
    suit the project's current category and subcategory. Replaces the ProjectDemand rows in the order dealt. Refuses anything else."""
    lock_person(user)
    project = locked_project(user, *rules.WORKING_STATUSES)
    if project is None or project.status != rules.BUILDING:
        raise ValidationError(NOT_DEALING)
    try:
        kept = {int(i) for i in ids}
    except (TypeError, ValueError):
        raise ValidationError(NOT_ON_THE_TABLE) from None
    if not (draw.MIN_KEEP <= len(kept) <= draw.MAX_KEEP):
        raise ValidationError(NOT_ON_THE_TABLE)
    if not kept <= set(project.hand):
        raise ValidationError(NOT_ON_THE_TABLE)
    demands = eligible_demands(project.category_id, project.subcategory_id).in_bulk(kept)
    if len(demands) != len(kept):
        raise ValidationError(NOT_ON_THE_TABLE)
    project.kept.all().delete()
    kept_in_order = [i for i in project.hand if i in kept]
    for order, demand_id in enumerate(kept_in_order, start=1):
        ProjectDemand.objects.create(project=project, demand=demands[demand_id], order=order)
    return project
