"""The public side: what a stranger may see of a person and their projects, as plain frozen dataclasses.

This is the privacy boundary of the public pages (docs/security.md, docs/public-pages.md), the same idea as shop/catalog.py. Templates
only ever receive these records, never a model instance, so a field that is not listed here (email, username, real name, region, time
zone, expertise, the cookie ledger, the reviewer's hours and internal note, anything about identity) cannot reach a page by accident.
Every query asks the database for exactly the columns it needs (`values()`), never a whole row. Add a field only after asking
whether the whole world may know it. Layers: showcase/rules.py (pure) <- this file <- views.py.
"""
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.urls import reverse

from accounts.models import Profile
from accounts.validators import SLACK_ID
from ledger import services as ledger
from program.content.demands import LEVELS, TIERS
from projects import rules as project_rules
from projects.models import Project, ProjectDemand
from showcase import rules
from submissions import links
from submissions import rules as submission_rules
from submissions.models import Submission
from talk.portraits import portrait

PAGE = 12           # projects per page on a profile
WALL_PAGE = 24      # projects per page on the Blue Ribbon wall


@dataclass(frozen=True)
class Paged:
    number: int
    pages: int
    previous: int | None
    next: int | None


@dataclass(frozen=True)
class Card:
    """A project as a card: on a profile, and on the Blue Ribbon wall."""
    name: str
    path: str
    where: str          # "Web, Website"
    status: str         # in_review, approved, ribbon or rejected (showcase/rules.py)
    status_label: str
    ribbon: bool        # some ship of it earned a Blue Ribbon
    screenshot: str     # an address, or ""
    maker: str
    maker_path: str


@dataclass(frozen=True)
class ProfilePage:
    name: str
    path: str
    slack_id: str
    slack_url: str      # "" when it cannot be built safely
    projects: int
    ribbons: int
    cards: tuple
    paged: Paged


@dataclass(frozen=True)
class Demand:
    name: str
    tier_label: str     # "Just a thought, dear"
    level: str          # mild, medium or spicy
    rule: str


@dataclass(frozen=True)
class Link:
    label: str
    url: str            # always http or https (checked by submissions/links.py)


@dataclass(frozen=True)
class Ship:
    status: str
    status_label: str
    ribbon: bool
    description: str
    screenshot: str
    links: tuple
    note: str           # Grandma's note: only once the maker has collected the result


@dataclass(frozen=True)
class Says:
    face_file: str
    face_alt: str
    line: str


@dataclass(frozen=True)
class ProjectPage:
    name: str
    path: str
    idea: str
    where: str
    maker: str
    maker_path: str
    status: str
    status_label: str
    ribbon: bool
    says: Says
    demands: tuple
    ships: tuple


@dataclass(frozen=True)
class Wall:
    cards: tuple
    paged: Paged


@dataclass(frozen=True)
class Row:
    rank: int
    name: str
    path: str
    cookies: int        # the all-time earned total, nothing else about their cookies


def profile_path(user_id, name):
    return reverse("public_profile", kwargs={"pk": user_id, "slug": rules.slug_of(name, "person")})


def project_path(project_id, name):
    return reverse("public_project", kwargs={"pk": project_id, "slug": rules.slug_of(name, "project")})


def people():
    """The profiles that may be shown: onboarding finished and the account not switched off (staff pull a person off the public
    pages by deactivating the account)."""
    return Profile.objects.filter(onboarded_at__isnull=False, user__is_active=True)


def ships(show_rejected):
    """The ships that may be shown: a shown person's, of a project staff have not abandoned (abandoning pulls a project off the
    pages), and not a rejected one the maker has already heard about when the setting hides those. A project that was never
    handed in has no ship, so it is never shown."""
    rows = Submission.objects.filter(project__user__is_active=True, project__user__profile__onboarded_at__isnull=False)
    rows = rows.exclude(project__status=project_rules.ABANDONED)
    return rows if show_rejected else rows.exclude(status=submission_rules.REJECTED, claimed_at__isnull=False)


def ribboned(visible):
    """The ships that earned a Blue Ribbon: approved, with the ribbon, and the maker has collected the result."""
    return visible.filter(status=submission_rules.APPROVED, ribbon=True, claimed_at__isnull=False)


def ship_status(row):
    return rules.public_status(row["status"], row["claimed_at"] is not None, row["ribbon"])


def picture(name):
    return default_storage.url(name) if name else ""


def where(category, subcategory):
    return category + (f", {subcategory}" if subcategory else "")


def slack_url(workspace, slack_id):
    """The link that opens a person in Slack, or "" if either part is not what it should be (a Slack ID is [UW] and capitals and
    digits, the workspace an http or https address)."""
    if not SLACK_ID.fullmatch(slack_id) or urlsplit(workspace).scheme not in ("http", "https"):
        return ""
    return f"{workspace.rstrip('/')}/team/{slack_id}"


def external(label, url):
    """A link a stranger may follow: only a plain http or https one that passes the same rules as the hand-in form."""
    return (Link(label, url),) if url and not links.web_url_problem(url) else ()


def card(project, rows, maker, maker_id):
    """One project as a card. `rows` are its visible ships, the latest round first; top gives the status, the ribbon shows if any ship earned one."""
    top = rows[0]
    status = ship_status(top)
    return Card(
        name=project["name"], path=project_path(project["id"], project["name"]),
        where=where(project["category__name"], project["subcategory__name"]), status=status, status_label=rules.LABELS[status],
        ribbon=any(ship_status(row) == rules.RIBBON for row in rows), screenshot=picture(top["screenshot"]),
        maker=maker, maker_path=profile_path(maker_id, maker))


def paged(page):
    return Paged(number=page.number, pages=page.paginator.num_pages, previous=page.previous_page_number() if page.has_previous() else None,
                 next=page.next_page_number() if page.has_next() else None)


def profile_page(pk, number, cfg):
    """A person's page, or None when there is nobody to show (unknown, not onboarded, switched off). `number` is the ?page= text."""
    person = people().filter(user_id=pk).values("user_id", "display_name", "slack_id").first()
    if person is None:
        return None
    visible = ships(cfg.SHOW_REJECTED_PUBLICLY)
    shown = Project.objects.filter(user_id=pk).filter(Exists(visible.filter(project=OuterRef("pk"))))
    page = Paginator(shown.values("id", "name", "category__name", "subcategory__name").order_by("-id"), PAGE).get_page(number)
    by_project = defaultdict(list)
    for row in visible.filter(project__in=[p["id"] for p in page]).values("project_id", "status", "ribbon", "claimed_at", "screenshot").order_by("-round", "-id"):
        by_project[row["project_id"]].append(row)
    name = person["display_name"]
    return ProfilePage(
        name=name, path=profile_path(pk, name), slack_id=person["slack_id"], slack_url=slack_url(cfg.SLACK_WORKSPACE_URL, person["slack_id"]),
        projects=page.paginator.count, ribbons=shown.filter(Exists(ribboned(visible).filter(project=OuterRef("pk")))).count(),
        cards=tuple(card(p, by_project[p["id"]], name, pk) for p in page), paged=paged(page))


def demand(row):
    return Demand(name=row["demand__name"], tier_label=TIERS[row["demand__tier"]], level=LEVELS[row["demand__tier"]], rule=row["demand__rule"])


def ship(row):
    """One ship as a stranger sees it. Grandma's note is only read once the maker has collected the result."""
    status = ship_status(row)
    note = row["public_note"].strip() if row["claimed_at"] is not None else ""
    return Ship(
        status=status, status_label=rules.LABELS[status], ribbon=status == rules.RIBBON,
        description=row["description"], screenshot=picture(row["screenshot"]), note=note,
        links=external("Try it", row["playable_url"]) + external("The code", row["repo_url"]) + external("Recording", row["recording_url"]))


def project_page(pk, cfg):
    """A project's page, or None when there is nothing to show (unknown, never handed in, abandoned, a hidden rejection, a person
    who may not be shown)."""
    visible = ships(cfg.SHOW_REJECTED_PUBLICLY)
    project = Project.objects.filter(pk=pk).filter(Exists(visible.filter(project=OuterRef("pk")))).values(
        "id", "name", "idea", "category__name", "subcategory__name", "user_id", "user__profile__display_name").first()
    if project is None:
        return None
    rows = list(visible.filter(project_id=pk).values(
        "status", "ribbon", "claimed_at", "screenshot", "description", "playable_url", "repo_url", "recording_url", "public_note").order_by("-round", "-id"))
    top = rows[0]
    status = ship_status(top)
    face, line = rules.SAYS[status]
    file, alt = portrait(face)
    maker = project["user__profile__display_name"]
    return ProjectPage(
        name=project["name"], path=project_path(pk, project["name"]), idea=project["idea"], where=where(project["category__name"], project["subcategory__name"]),
        maker=maker, maker_path=profile_path(project["user_id"], maker), status=status, status_label=rules.LABELS[status],
        ribbon=any(ship_status(row) == rules.RIBBON for row in rows), says=Says(file, alt, line),
        demands=tuple(demand(d) for d in ProjectDemand.objects.filter(project_id=pk).values("demand__name", "demand__tier", "demand__rule").order_by("order")),
        ships=tuple(ship(row) for row in rows))


def wall_page(number, cfg):
    """Every project that earned a Blue Ribbon, newest ribbon first."""
    rows = ribboned(ships(cfg.SHOW_REJECTED_PUBLICLY)).values(
        "project_id", "status", "ribbon", "claimed_at", "screenshot", "project__name", "project__category__name", "project__subcategory__name",
        "project__user_id", "project__user__profile__display_name").order_by("-claimed_at", "-id")
    page = Paginator(rows, WALL_PAGE).get_page(number)
    cards = tuple(card({"id": r["project_id"], "name": r["project__name"], "category__name": r["project__category__name"], "subcategory__name": r["project__subcategory__name"]},
                       [r], r["project__user__profile__display_name"], r["project__user_id"]) for r in page)
    return Wall(cards=cards, paged=paged(page))


def board(cfg):
    """The cookie board: the biggest earned totals of all time, the number only. One aggregate query for the totals (ledger.services),
    one for the names of the people on it; ties share a rank and keep a fixed order; people with nothing earned are not on it."""
    users = get_user_model().objects.filter(is_active=True, profile__onboarded_at__isnull=False)
    totals = list(ledger.earned_totals(users)[:cfg.LEADERBOARD_SIZE])
    names = dict(people().filter(user_id__in=[t["user"] for t in totals]).values_list("user_id", "display_name"))
    totals = [t for t in totals if t["user"] in names]
    return tuple(Row(rank, names[t["user"]], profile_path(t["user"], names[t["user"]]), t["total"]) for rank, t in zip(rules.ranks([t["total"] for t in totals]), totals))
