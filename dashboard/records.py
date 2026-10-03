"""What the dashboard's templates may know: frozen records of plain fields, never a model (the same boundary as shop/catalog.py and
projects/notes.py). The reviewer's hours and internal note are not fields of any of them, so no template can print them."""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Says:
    face_file: str      # in static/assets
    face_alt: str
    line: str


@dataclass(frozen=True)
class ProjectCard:
    name: str
    idea: str
    where: str          # "Web, Website"
    status: str         # the project's status key, for the chip's colour
    status_label: str
    ship: str           # "Design ship", "Build ship" or "" (what handing in next would be, for hardware)
    notes: tuple        # the kept demands as projects.notes.Note records
    action: str         # what the card offers: ship (the Ship it button), reading (it is with Grandma), resume (a hand is on her table), start (nothing in progress)


@dataclass(frozen=True)
class SubmissionRow:
    project: str
    ship: str           # "Ship", "Design ship" or "Build ship"
    when: str
    status: str         # handed_in, waiting, approved or rejected (what the person may know)
    status_label: str
    cookies: int | None     # what she handed over: only once collected and approved
    ribbon: bool            # only once collected
    note: str               # the public note: only once collected


@dataclass(frozen=True)
class OrderRow:
    """One order, as much as the person may know: no internal note, no grant reference, no reviewer."""
    id: int
    title: str              # "iPad", or "AI credits x 3"
    detail: str             # "for Moon Lamp, 3 parts, plus 7 upgrades"
    when: str
    status: str             # the order's status key, for the stamp's colour
    status_label: str
    cookies: int            # what they paid, frozen
    value: Decimal          # what the grant is worth in dollars, frozen
    note: str               # Grandma's public note
    proofs: tuple           # (label, address) pairs: the person's own screenshots, served by orders.views to them and to staff only
    can_cancel: bool        # only while nobody has looked at it


@dataclass(frozen=True)
class CookieRow:
    when: str
    amount: int         # signed
    reason: str


@dataclass(frozen=True)
class Paged:
    rows: tuple
    number: int
    pages: int
    previous: int | None
    next: int | None


@dataclass(frozen=True)
class Summary:
    name: str
    balance: int
    waiting: int            # cookies awarded but not yet collected: the person's current pay
    project: ProjectCard | None
    says: Says
    submissions: tuple      # the latest few
    submissions_total: int
    history: tuple          # the latest few
    history_total: int
    orders: tuple           # the latest few, OrderRow records
    orders_total: int
