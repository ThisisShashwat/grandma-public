"""The numbers behind the admin's Metrics page: read only, aggregated in the database, so the query count does not grow with the people.
Staff are left out of everything (is_staff False). A day is a calendar day in the site's zone (metrics/clock.py), and a range of N days is
the last N days including today, every one of them present even when nothing happened on it. Everything returned is plain data the
template only prints. Definitions: docs/metrics.md."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.db.models import Count, Exists, Min, OuterRef, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import Profile
from metrics.clock import site_day, site_zone
from metrics.models import ActiveDay, DayViews
from projects.models import Project
from submissions import rules
from submissions.models import Submission

RANGES = (7, 30, 60, 90, 180)
DEFAULT_RANGE = 30
ACTIVE_NOW_MINUTES = 10
CHART_WIDTH, CHART_HEIGHT, BAR_SHARE = 600, 140, 0.8
NOT_COUNTED = "Not counted. Switch COUNT_VISITS on to count it (Admin, Constance, group Metrics)."
STAGES = (("signed_up", "Signed up"), ("onboarded", "Finished onboarding"), ("hackatime", "Connected Hackatime"),
          ("started", "Started a project"), ("handed_in", "Handed a project in"), ("approved", "Got an approval"))


@dataclass(frozen=True)
class Card:
    key: str
    label: str
    value: float
    text: str
    hint: str


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    count: int | None          # None: not counted
    text: str
    percent: int | None        # of the stage before it
    note: str
    width: int                 # bar width, percent


@dataclass(frozen=True)
class Bar:
    x: str
    y: str
    width: str
    height: str
    hit_x: str
    tip: str


@dataclass(frozen=True)
class Chart:
    key: str
    title: str
    bars: tuple[Bar, ...]
    width: int
    height: int
    slot: str
    top: str
    first: str
    last: str


@dataclass(frozen=True)
class Report:
    days: int
    first: date
    last: date
    since: date | None
    zone: str
    people: tuple[Card, ...]
    hours: tuple[Card, ...]
    funnel: tuple[Stage, ...]
    funnel_hours: str
    charts: tuple[Chart, ...]

    def card(self, key):
        return next(card for card in self.people + self.hours if card.key == key)

    def stage(self, key):
        return next(stage for stage in self.funnel if stage.key == key)

    def chart(self, key):
        return next((chart for chart in self.charts if chart.key == key), None)


@dataclass(frozen=True)
class Span:
    """The last `days` calendar days up to and including `last` (today)."""
    days: int
    first: date
    last: date

    @property
    def dates(self):
        return [self.first + timedelta(days=i) for i in range(self.days)]

    @property
    def start(self):
        return at_midnight(self.first)

    @property
    def end(self):
        return at_midnight(self.last + timedelta(days=1))


def parse_days(value):
    """A range from the address: one of RANGES, else the default."""
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_RANGE
    return days if days in RANGES else DEFAULT_RANGE


def at_midnight(day):
    return datetime.combine(day, time.min, tzinfo=site_zone())


def hours_of(seconds):
    return (seconds or 0) / 3600


def hours_text(hours):
    return f"{hours:.1f} h"


def day_text(day):
    return f"{day:%b} {day.day}"


def people_text(n):
    return f"{n} {'person' if n == 1 else 'people'}"


def sign_ups_text(n):
    return f"{n} {'sign up' if n == 1 else 'sign ups'}"


def views_text(n):
    return f"{n} {'view' if n == 1 else 'views'}"


def percent_of(count, before):
    """Whole percent, half up; nothing when there is no stage before to compare with."""
    return (count * 200 + before) // (2 * before) if before else None


# the questions, one small function each

def active_people(span, moment):
    """Distinct people seen now, today and in the range, and how many were seen on each day."""
    rows = ActiveDay.objects.filter(user__is_staff=False, day__range=(span.first, span.last))
    cut = moment - timedelta(minutes=ACTIVE_NOW_MINUTES)
    counts = rows.aggregate(now=Count("user", distinct=True, filter=Q(last_seen__gte=cut)), today=Count("user", distinct=True, filter=Q(day=span.last)),
                            span=Count("user", distinct=True))
    return counts, dict(rows.order_by().values_list("day").annotate(n=Count("user", distinct=True)))


def counted_since():
    return ActiveDay.objects.aggregate(first=Min("day"))["first"]


def total_users():
    return Profile.objects.filter(user__is_staff=False).count()


def joined(span):
    """The people who signed up in the range: the cohort of the funnel."""
    return Profile.objects.filter(user__is_staff=False, user__date_joined__gte=span.start, user__date_joined__lt=span.end)


def sign_ups_per_day(span):
    return dict(joined(span).order_by().annotate(day=TruncDate("user__date_joined", tzinfo=site_zone())).values_list("day").annotate(n=Count("pk")))


def handed_in_rows(span):
    return Submission.objects.filter(project__user__is_staff=False, submitted_at__gte=span.start, submitted_at__lt=span.end)


def seconds_per_day(span):
    """Tracked seconds handed in on each day (a hand-in without a Hackatime check counts 0)."""
    rows = handed_in_rows(span).order_by().annotate(day=TruncDate("submitted_at", tzinfo=site_zone()))
    return {day: seconds or 0 for day, seconds in rows.values_list("day").annotate(s=Sum("tracked_seconds"))}


def makers_in(span):
    return handed_in_rows(span).aggregate(n=Count("project__user", distinct=True))["n"]


def seconds_in_review():
    return Submission.objects.filter(project__user__is_staff=False, status=rules.SUBMITTED).aggregate(s=Sum("tracked_seconds"))["s"]


def approved_hours_in(span):
    rows = Submission.objects.filter(project__user__is_staff=False, status=rules.APPROVED, reviewed_at__gte=span.start, reviewed_at__lt=span.end)
    return float(rows.aggregate(h=Sum("approved_hours"))["h"] or 0)


def views_per_page(span):
    """{page: {day: views}} for the range; empty when nothing was counted (the COUNT_VISITS setting is off or the range is older)."""
    pages = {}
    for page, day, views in DayViews.objects.filter(day__range=(span.first, span.last)).values_list("page", "day", "views"):
        pages.setdefault(page, {})[day] = views
    return pages


def cohort_counts(span):
    """How many of the people who signed up in the range got as far as each stage."""
    def has(model, **where):
        return Exists(model.objects.filter(**where))
    return joined(span).aggregate(
        signed_up=Count("pk"), onboarded=Count("pk", filter=Q(onboarded_at__isnull=False)), hackatime=Count("pk", filter=Q(hackatime_connected=True)),
        started=Count("pk", filter=has(Project, user=OuterRef("user"), started_at__isnull=False)),
        handed_in=Count("pk", filter=has(Submission, project__user=OuterRef("user"))),
        approved=Count("pk", filter=has(Submission, project__user=OuterRef("user"), status=rules.APPROVED)))


def cohort_approved_hours(span):
    rows = Submission.objects.filter(status=rules.APPROVED, project__user__in=joined(span).values("user"))
    return float(rows.aggregate(h=Sum("approved_hours"))["h"] or 0)


# turning answers into what the page shows

def people_cards(span, active, per_day, users, new):
    average = sum(per_day.values()) / span.days
    last = f"last {span.days} days"
    return (Card("active_now", "Active now", active["now"], str(active["now"]), f"in the last {ACTIVE_NOW_MINUTES} minutes"),
            Card("active_today", "Active today", active["today"], str(active["today"]), "signed in people"),
            Card("average_daily_active", "Average daily active", average, f"{average:.1f}", f"people a day, {last}"),
            Card("active_in_range", "Active in range", active["span"], str(active["span"]), f"different people, {last}"),
            Card("total_users", "Total users", users, str(users), "all sign ups"),
            Card("new_sign_ups", "New sign ups", new, str(new), last))


def hour_cards(span, seconds, makers, in_review, approved):
    handed = hours_of(sum(seconds.values()))
    today = hours_of(seconds.get(span.last, 0))
    per_day, per_person = handed / span.days, handed / makers if makers else 0
    last = f"last {span.days} days"
    return (Card("handed_today", "Hours handed in today", today, hours_text(today), "tracked time of today's hand-ins"),
            Card("handed_range", "Hours handed in", handed, hours_text(handed), last),
            Card("in_review", "Hours in review", hours_of(in_review), hours_text(hours_of(in_review)), "waiting for a decision, all time"),
            Card("approved_range", "Hours approved", approved, hours_text(approved), last),
            Card("per_day", "Average hours per day", per_day, hours_text(per_day), f"handed in a day, {last}"),
            Card("per_person", "Average hours per person", per_person, hours_text(per_person), "per person who handed in"))


def view_stage(key, label, pages, counted):
    count = sum(pages.get(key, {}).values()) if counted else None
    return key, label, count, None, "" if counted else NOT_COUNTED


def funnel_stages(counts, pages, counted):
    """The two view stages (views, not people), then the cohort stages, each a percent of the one before it. Widths are against the largest count."""
    rows = [view_stage("home", "Home page views", pages, counted), view_stage("signin", "Pressed Sign in", pages, counted)]
    home = rows[0][2]
    before = None
    for key, label in STAGES:
        count = counts[key]
        note = f"{count * 100 / home:.1f} signed up per 100 home views" if before is None and home else ""
        rows.append((key, label, count, None if before is None else percent_of(count, before), note))
        before = count
    biggest = max((count for _, _, count, _, _ in rows if count is not None), default=0)
    return tuple(Stage(key, label, count, "not counted" if count is None else str(count), percent, note, bar_width(count, biggest))
                 for key, label, count, percent, note in rows)


def bar_width(count, biggest):
    if not count:
        return 0
    return max(1, round(count * 100 / biggest))


def chart(key, title, span, per_day, text):
    """A bar per day: x, y, width and height are for an inline SVG of CHART_WIDTH by CHART_HEIGHT. A day of nothing is still a 1 unit line."""
    values = [per_day.get(day, 0) for day in span.dates]
    peak = max(values)
    slot = CHART_WIDTH / span.days
    width = slot * BAR_SHARE
    bars = []
    for i, (day, value) in enumerate(zip(span.dates, values)):
        height = max(1, value / peak * CHART_HEIGHT) if peak else 1
        bars.append(Bar(f"{i * slot + (slot - width) / 2:.2f}", f"{CHART_HEIGHT - height:.2f}", f"{width:.2f}", f"{height:.2f}", f"{i * slot:.2f}", f"{day_text(day)}: {text(value)}"))
    return Chart(key, title, tuple(bars), CHART_WIDTH, CHART_HEIGHT, f"{slot:.2f}", f"Highest day: {text(peak)}", day_text(span.first), day_text(span.last))


def charts_for(span, active_per_day, signs, seconds, pages):
    charts = [chart("active", "Daily active people", span, active_per_day, people_text), chart("sign_ups", "New sign ups per day", span, signs, sign_ups_text),
              chart("hours", "Hours handed in per day", span, {day: hours_of(s) for day, s in seconds.items()}, hours_text)]
    if pages:
        charts.append(chart("home_views", "Home page views per day", span, pages.get("home", {}), views_text))
    return tuple(charts)


def build(days, now=None):
    moment = now or timezone.now()
    today = site_day(moment)
    span = Span(days, today - timedelta(days=days - 1), today)
    active, active_per_day = active_people(span, moment)
    signs, seconds, pages = sign_ups_per_day(span), seconds_per_day(span), views_per_page(span)
    counts = cohort_counts(span)
    return Report(days, span.first, span.last, counted_since(), settings.TIME_ZONE,
                  people_cards(span, active, active_per_day, total_users(), counts["signed_up"]),
                  hour_cards(span, seconds, makers_in(span), seconds_in_review(), approved_hours_in(span)),
                  funnel_stages(counts, pages, bool(pages)), hours_text(cohort_approved_hours(span)),
                  charts_for(span, active_per_day, signs, seconds, pages))
