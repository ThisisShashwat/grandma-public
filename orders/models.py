"""An order: one person getting one grant, with the proof of what it is for. Prices and values are FROZEN on the order and its lines when
it is placed, so editing the shop item later never changes an order. The money moves through the cookie ledger only (ledger/services.py,
keys `order:{id}` and `order:{id}:refund`), written by orders/services.py in the same transaction as the order. Participant fields are
written once and never edited; staff change only the status (through the services, which refund when they must) and the notes.
Layers: program, shop.models, projects.models <- rules.py (pure) <- models.py <- services.py.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from orders import rules
from orders.storage import private_storage, proof_path
from projects.models import Project
from shop.models import ShopItem
from submissions.validators import validate_prose, validate_web_url


class Order(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT, related_name="orders", help_text="The base grant. Upgrades are order lines.")
    project = models.ForeignKey(Project, on_delete=models.PROTECT, null=True, blank=True, related_name="orders",
                                help_text="Hardware grants only: the shipped design this grant is for.")
    status = models.CharField(max_length=9, choices=rules.STATUSES, default=rules.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    nonce = models.CharField(max_length=32, editable=False, help_text="Made when the page was shown: a second post of the same page places nothing.")

    # frozen when the order is placed (never edited)
    total_cookies = models.PositiveIntegerField(editable=False, help_text="What the person paid, in cookies, frozen.")
    total_value = models.DecimalField(max_digits=10, decimal_places=2, editable=False, help_text="What the grant is worth in dollars, upgrades included, frozen.")

    # the proof, written once by the person
    product_url = models.URLField(max_length=300, blank=True, validators=[validate_web_url], help_text="Link to the product. Empty for a hardware order (each part has its own).")
    user_note = models.TextField(max_length=600, blank=True, validators=[validate_prose])
    cart_screenshot = models.ImageField(upload_to=proof_path, storage=private_storage, max_length=100, blank=True,
                                        help_text="Private. The cart with tax and shipping, served only by the login-checked view.")

    # what staff decide
    public_note = models.TextField(max_length=1000, blank=True, help_text="What Grandma tells the person. They read it on My orders. Never put anything private in it.")
    internal_note = models.TextField(max_length=2000, blank=True, help_text="For staff only. Never shown to the person.")
    grant_ref = models.CharField("HCB grant reference", max_length=120, blank=True,
                                 help_text="Paste the reference of the Hack Club Bank grant you issued by hand. Needed to mark the order fulfilled.")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, editable=False, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(status__in=[s for s, _ in rules.STATUSES]), name="order_status_is_known"),
            models.CheckConstraint(condition=Q(total_cookies__gt=0), name="order_cookies_positive"),
            models.CheckConstraint(condition=Q(total_value__gt=0), name="order_value_positive"),
            models.CheckConstraint(condition=~Q(status=rules.FULFILLED) | ~Q(grant_ref=""), name="order_fulfilled_has_grant_ref",
                                   violation_error_message="A fulfilled order needs the reference of the grant that was issued."),
            models.UniqueConstraint(fields=["user", "nonce"], name="order_one_per_page_shown",
                                    violation_error_message="That page already placed an order."),
            models.UniqueConstraint(fields=["project", "item"], condition=Q(project__isnull=False, status__in=rules.LIVE), name="order_one_grant_per_project",
                                    violation_error_message="That project already has a grant of that kind on the way."),
        ]

    def __str__(self):
        return f"Order {self.pk}: {self.item.name} for {self.user.get_username()} ({self.get_status_display().lower()})"

    def clean(self):
        if self.item_id and self.item.needs_project and self.project_id is None:
            raise ValidationError("A hardware grant is for one project.")
        if self.project_id and self.project.user_id != self.user_id:
            raise ValidationError("The project must be the buyer's own.")

    def validate_constraints(self, exclude=None):
        """Every constraint, even for fields the admin form leaves out: otherwise it would only fail in the database, as an error page."""
        super().validate_constraints(exclude=None)


class OrderLine(models.Model):
    """The base grant (upgrade False, exactly one per order) and one line per upgrade item, with price and value frozen."""
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="lines")
    item = models.ForeignKey(ShopItem, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveSmallIntegerField()
    unit_cookies = models.PositiveIntegerField()
    unit_value = models.DecimalField(max_digits=8, decimal_places=2)
    upgrade = models.BooleanField(default=False)

    class Meta:
        ordering = ["upgrade", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1, quantity__lte=rules.MAX_QUANTITY), name="orderline_quantity_sane"),
            models.CheckConstraint(condition=Q(unit_cookies__gt=0) & Q(unit_value__gt=0), name="orderline_price_positive"),
            models.UniqueConstraint(fields=["order", "item"], name="orderline_one_per_item"),
            models.UniqueConstraint(fields=["order"], condition=Q(upgrade=False), name="orderline_one_base_per_order"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.item.name}"

    @property
    def cookies(self):
        return self.quantity * self.unit_cookies

    @property
    def value(self):
        return self.quantity * self.unit_value


class OrderPart(models.Model):
    """Hardware only: one part the person is buying, as they typed it. The parts together may not come to more than the grant's value."""
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="parts")
    name = models.CharField(max_length=80, validators=[validate_prose])
    url = models.URLField(max_length=300, validators=[validate_web_url])
    price = models.DecimalField(max_digits=7, decimal_places=2, help_text="In dollars, with tax and shipping, as the person typed it.")
    screenshot = models.ImageField(upload_to=proof_path, storage=private_storage, max_length=100, blank=True, help_text="Private, like the cart.")

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=Q(price__gt=0), name="orderpart_price_positive")]

    def __str__(self):
        return f"{self.name} (${self.price})"
