"""What the dashboard shows one person, read from the database and handed to the templates as plain records (dashboard/records.py).
Everything is filtered by the signed-in person: nothing here takes an id from a request, so there is nothing to guess. The reviewer's
hours and internal note are never read into a record, and a result is only shown (cookies, ribbon, the public note) once Grandma
has handed it over."""
from zoneinfo import ZoneInfo

from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.urls import reverse

from accounts.services import profile_of
from dashboard import mood, records
from ledger import services as ledger
from ledger.models import CookieEntry
from orders import rules as order_rules
from orders.models import Order
from projects import notes, rules, services as project_services
from shop.models import ShopItem
from submissions import rules as submission_rules
from submissions.models import Submission
from talk.portraits import portrait

LATEST = 3          # submissions on the dashboard itself
RECENT = 5          # cookie entries on the dashboard itself
PAGE = 20           # per page on the sub pages


def zone_of(profile):
    """The person's own time zone (validated when they gave it), else UTC."""
    try:
        return ZoneInfo(profile.timezone)
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def day(moment, zone):
    local = moment.astimezone(zone)
    return f"{local.day} {local:%b %Y}"


def says(face, line):
    file, alt = portrait(face)
    return records.Says(face_file=file, face_alt=alt, line=line)


def waiting_cookies(user):
    """Cookies awarded and not yet handed over: reviewed and approved, not collected."""
    total = Submission.objects.filter(project__user=user, status=submission_rules.APPROVED, claimed_at__isnull=True).aggregate(total=Sum("cookies_awarded"))["total"]
    return total or 0


def project_card(project):
    action = {rules.BUILDING: "ship", rules.IN_REVIEW: "reading", rules.SHIPPED: "reading", rules.DEALING: "resume", rules.CHANGES_REQUESTED: "fix"}.get(project.status, "start")
    return records.ProjectCard(
        id=project.id, note=project_services.change_note(project) if action == "fix" else "", name=project.name, idea=project.idea, where=project.category.name + (f", {project.subcategory.name}" if project.subcategory else ""),
        status=project.status, status_label=rules.LABELS[project.status],
        notes=tuple(notes.notes(project_services.kept_demands(project))), action=action)


def submission_row(submission, zone):
    """One thing handed in, as much as the person may know: a result is only shown once Grandma has handed it over."""
    collected = submission.claimed_at is not None
    if submission.status == submission_rules.SUBMITTED:
        status, label = "handed_in", "Handed in"
    elif not collected:
        status, label = "waiting", "Waiting at Grandma's"
    else:
        status, label = submission.status, submission_rules.LABELS[submission.status]
    approved = collected and submission.status == submission_rules.APPROVED
    return records.SubmissionRow(
        project=submission.project.name, round=submission.round, rounds=submission.rounds, when=day(submission.submitted_at, zone), status=status,
        status_label=label, cookies=submission.cookies_awarded if approved else None, ribbon=approved and submission.ribbon,
        note=submission.public_note.strip() if collected else "")


def cookie_row(entry, zone):
    return records.CookieRow(when=day(entry.created_at, zone), amount=entry.amount, reason=entry.reason)


def order_detail(order):
    """The parts of an order worth a line under its title: how many upgrades."""
    upgrades = sum(line.quantity for line in order.lines.all() if line.upgrade)
    return f"plus {upgrades} {'upgrade' if upgrades == 1 else 'upgrades'}" if upgrades else ""


def order_proofs(order):
    """The person's own screenshots, as addresses of the login-checked view (never a file address: there is none)."""
    return (("Cart screenshot", reverse("order_cart", args=[order.pk])),) if order.cart_screenshot else ()


def order_row(order, zone):
    base = next((line for line in order.lines.all() if not line.upgrade), None)
    quantity = f" x {base.quantity}" if base and base.quantity > 1 else ""
    return records.OrderRow(
        id=order.pk, title=order.item.name + quantity, detail=order_detail(order), when=day(order.created_at, zone), status=order.status,
        status_label=order_rules.LABELS[order.status], cookies=order.total_cookies, value=order.total_value if order.item.kind == ShopItem.Kind.GRANT else None, note=order.public_note.strip(),
        proofs=order_proofs(order), can_cancel=order.status == order_rules.PENDING)


def my_orders(user):
    return Order.objects.filter(user=user).select_related("item").prefetch_related("lines")


def mine(user):
    """The person's submissions, newest first (spelled out: the count of rounds groups the rows, and a grouped query ignores the model's ordering)."""
    return Submission.objects.filter(project__user=user).select_related("project").annotate(rounds=Count("project__submissions")).order_by("-submitted_at", "-id")


def entries(user):
    return CookieEntry.objects.filter(user=user).order_by("-created_at", "-id")


def build(user):
    profile = profile_of(user)
    zone = zone_of(profile)
    project = project_services.working_project(user) or project_services.latest_project(user)
    card = project_card(project) if project else None
    face, line = mood.says(project.status if project else None)
    other_list = project_services.other_projects(user, statuses=(rules.IN_REVIEW, rules.SHIPPED, rules.CHANGES_REQUESTED), limit=5)
    submissions, history, orders = mine(user), entries(user), my_orders(user)
    return records.Summary(
        name=profile.display_name, balance=ledger.balance(user), waiting=waiting_cookies(user), project=card, says=says(face, line),
        submissions=tuple(submission_row(s, zone) for s in submissions[:LATEST]), submissions_total=submissions.count(),
        history=tuple(cookie_row(e, zone) for e in history[:RECENT]), history_total=history.count(),
        orders=tuple(order_row(o, zone) for o in orders[:LATEST]), orders_total=orders.count(),
        other_projects=tuple(row for row in other_list if not (card and row.id == card.id)))


def paged(queryset, number, make):
    """One page of a person's list, as records. A page number that is not a number or out of range is the first or last page."""
    page = Paginator(queryset, PAGE).get_page(number)
    return records.Paged(rows=tuple(make(row) for row in page), number=page.number, pages=page.paginator.num_pages,
                         previous=page.previous_page_number() if page.has_previous() else None, next=page.next_page_number() if page.has_next() else None)


def submissions_page(user, number):
    zone = zone_of(profile_of(user))
    return paged(mine(user), number, lambda s: submission_row(s, zone))


def orders_page(user, number):
    zone = zone_of(profile_of(user))
    return paged(my_orders(user), number, lambda o: order_row(o, zone))


def cookies_page(user, number):
    zone = zone_of(profile_of(user))
    return paged(entries(user), number, lambda e: cookie_row(e, zone))
