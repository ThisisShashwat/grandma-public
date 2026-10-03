"""The staff side of orders: look at what a person ordered and the proof they gave, then approve, reject (the cookies go back by themselves), mark
it fulfilled with the reference of the Hack Club Bank grant staff issued by hand, or refund a fulfilled one. What the person gave is read only,
and so are the frozen totals, always; staff change only the status (through orders/services.py, so a rejection refunds), the notes and the
grant reference. Nothing can be added or deleted. The proof screenshots are private files: they are linked through the login-checked view,
never by a file address. The "Fulfillers" group (migration 0002) has view and change on Order and nothing else."""
from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from orders import rules, services
from orders.models import Order
from submissions import links

PARTICIPANT = ("person", "item", "for_project", "created_at", "totals", "lines_table", "product_link", "user_note", "cart_link", "parts_table")
DECISION = ("status", "public_note", "internal_note", "grant_ref")
RESULT = ("reviewed_by", "reviewed_at")


class DecisionForm(forms.ModelForm):
    """Only the decision. The status offers where this order may go from where it is (rules.TRANSITIONS); a fulfilled order needs its reference."""

    class Meta:
        model = Order
        fields = DECISION

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current = self.instance.status
        self.fields["status"].choices = [(status, rules.LABELS[status]) for status in (current, *rules.TRANSITIONS.get(current, ()))]

    def clean(self):
        cleaned = super().clean()
        status, ref = cleaned.get("status"), (cleaned.get("grant_ref") or "").strip()
        if status == rules.FULFILLED and not ref:
            self.add_error("grant_ref", services.NEEDS_REF)
        return cleaned


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    form = DecisionForm
    list_display = ("id", "who", "item", "status", "total_cookies", "total_value", "reference")
    list_filter = ("status", "item", "item__needs_project")
    list_select_related = ("user", "user__profile", "item")
    search_fields = ("user__username", "user__profile__display_name", "item__name", "grant_ref")
    actions = ["approve", "reject", "mark_fulfilled", "refund"]
    fieldsets = (
        ("What they ordered", {"fields": PARTICIPANT}),
        ("Decision", {"fields": DECISION, "description": "Approve it, or turn it down with a note Grandma reads out (the cookies go back by themselves). "
                                                         "Issue the Hack Club Bank grant by hand, then paste its reference here and set the status to fulfilled. "
                                                         "The person sees the status and the public note, never the internal note."}),
        ("Result", {"fields": RESULT}),
    )
    readonly_fields = PARTICIPANT + RESULT

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        try:
            services.review(obj, by=request.user)
        except ValidationError as error:
            self.message_user(request, error.messages[0], messages.ERROR)

    # the actions: one status move each, through the services (a refund is written once)

    def move(self, request, queryset, mover, done):
        moved = 0
        for order in queryset:
            try:
                mover(order)
                moved += 1
            except ValidationError as error:
                self.message_user(request, f"Order {order.pk}: {error.messages[0]}", messages.ERROR)
        if moved:
            self.message_user(request, f"{moved} {done}.")

    @admin.action(description="Approve the selected orders", permissions=["change"])
    def approve(self, request, queryset):
        self.move(request, queryset, lambda order: services.approve(order.pk, by=request.user), "approved")

    @admin.action(description="Reject the selected orders (the cookies go back)", permissions=["change"])
    def reject(self, request, queryset):
        self.move(request, queryset, lambda order: services.reject(order.pk, by=request.user), "rejected and refunded")

    @admin.action(description="Mark fulfilled (needs the grant reference saved on each order first)", permissions=["change"])
    def mark_fulfilled(self, request, queryset):
        self.move(request, queryset, lambda order: services.fulfil(order.pk, order.grant_ref, by=request.user), "marked fulfilled")

    @admin.action(description="Refund fulfilled orders (the grant was never used or was cancelled)", permissions=["change"])
    def refund(self, request, queryset):
        self.move(request, queryset, lambda order: services.refund(order.pk, by=request.user), "refunded")

    # the list and the read only parts of the form

    @admin.display(description="person", ordering="user__username")
    def who(self, obj):
        """The short form for the list (the detail page has the Slack ID, which is how staff reach someone)."""
        profile = getattr(obj.user, "profile", None)
        return f"{obj.user.get_username()} ({(profile and profile.display_name) or 'no name'})"

    @admin.display(description="person", ordering="user__username")
    def person(self, obj):
        profile = getattr(obj.user, "profile", None)
        return f"{obj.user.get_username()} ({(profile and profile.display_name) or 'no name'}, Slack ID {(profile and profile.slack_id) or 'none'})"

    @admin.display(description="reference", ordering="grant_ref")
    def reference(self, obj):
        return obj.grant_ref or "-"

    @admin.display(description="for project")
    def for_project(self, obj):
        return f"{obj.project.name} (project {obj.project_id})" if obj.project_id else "not a hardware grant"

    @admin.display(description="the price, frozen when they ordered")
    def totals(self, obj):
        return f"{obj.total_cookies:,} cookies, a grant worth ${obj.total_value:,.2f}"

    @admin.display(description="lines")
    def lines_table(self, obj):
        rows = ((line.quantity, line.item.name, "upgrade" if line.upgrade else "grant", line.unit_cookies, line.unit_value) for line in obj.lines.select_related("item"))
        return format_html("<ul>{}</ul>", format_html_join("", "<li>{} x {} ({}), {} cookies and ${} each</li>", rows))

    @admin.display(description="product link")
    def product_link(self, obj):
        return link(obj.product_url) if obj.product_url else "none"

    @admin.display(description="cart screenshot")
    def cart_link(self, obj):
        if not obj.cart_screenshot:
            return "none"
        return format_html('<a href="{0}" target="_blank" rel="noopener">Open the cart screenshot (private)</a>', reverse("order_cart", args=[obj.pk]))

    @admin.display(description="parts")
    def parts_table(self, obj):
        parts = list(obj.parts.all())
        if not parts:
            return "none"
        rows = ((part.name, link(part.url), part.price, shot_link(obj, part)) for part in parts)
        return format_html("<ul>{}</ul><p>The parts come to ${}.</p>", format_html_join("", "<li>{}: {}, ${}{}</li>", rows), f"{sum(part.price for part in parts):,.2f}")


def link(url):
    """A link a person typed, opened in a new tab: only if it still passes the link rules (the database is another door), else plain text."""
    if links.web_url_problem(url):
        return url
    return format_html('<a href="{0}" target="_blank" rel="noopener noreferrer">{0}</a>', url)


def shot_link(order, part):
    return format_html(', <a href="{}" target="_blank" rel="noopener">screenshot (private)</a>', reverse("order_part", args=[order.pk, part.pk])) if part.screenshot else ""
