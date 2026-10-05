"""Getting a grant: /shop/<slug>/get/ for a plain grant, a person taking back an order nobody has
looked at, and the private proof screenshots. Every page is for one signed-in, onboarded person and works only on their own things: a
grant comes from the address, but a price and the balance never do (services.py reads them from the database again), and the
proofs are served only to the order's owner or to staff who may view orders, never as a public file (docs/orders.md)."""
import uuid
from pathlib import Path

from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from accounts.access import invited, onboarded
from ledger import services as ledger
from orders import forms, services, sheet
from orders.models import Order
from pages.live import live
from submissions.services import holds_ribbon_user
from talk.portraits import portrait

ORDERED = "Ordered, dear. Your cookies are in my pocket. I'll look at the cart before I pay a penny."
TAKEN_BACK = "Taken back, dear. Your cookies are back in the jar."
PROOF_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}


def form_for(request, item, record, cfg):
    """The order form for this grant and person: bound to the post, or empty. It runs services.precheck (the limit, the stock, the balance)
    before it decodes any picture."""
    arguments = {"cfg": cfg, "proves": not record.manual, "stackable": record.stackable,
                 "upgrades": [(option.field, int(option.field.removeprefix("up_"))) for option in record.options],
                 "precheck": lambda quantity, upgrades: services.precheck(request.user, item.pk, quantity=quantity, upgrades=upgrades)}
    return forms.OrderForm(request.POST, request.FILES, **arguments) if request.method == "POST" else forms.OrderForm(**arguments)


def order_page(request, item):
    """One grant's page. Nothing is placed unless the form is valid and services.place_order accepts it (it checks everything again).
    A page already posted once (same nonce) just goes on to My orders, so a double click places one order."""
    if request.method == "POST" and services.already_placed(request.user, request.POST.get("nonce")):
        return redirect("dashboard_orders")
    cfg = live()
    record = sheet.build(request.user, item, cfg, ledger.balance(request.user))
    form = None if record.blocked else form_for(request, item, record, cfg)       # nothing is decoded for someone who could not place it anyway
    if form is not None and request.method == "POST" and form.is_valid():
        try:
            services.place_order(request.user, item.pk, **form.order_kwargs())
        except ValidationError as error:
            form.add_error(None, error)
        else:
            request.session["order_flash"] = ORDERED
            return redirect("dashboard_orders")
    nonce = form["nonce"].value() if form is not None and form.is_bound and not form["nonce"].errors else uuid.uuid4().hex
    face = "sideeye" if record.blocked or (form is not None and form.errors) else "writing"
    return render(request, "pages/order.html", {"sheet": record, "form": form, "nonce": nonce, "portrait": dict(zip(("file", "alt"), portrait(face))),
                                                "max_mb": cfg.ORDER_SCREENSHOT_MAX_MB})


@onboarded
@never_cache
@require_http_methods(["GET", "HEAD", "POST"])
def get_grant(request, slug):
    item = services.gettable(slug, holds_ribbon_user(request.user))      # a ribbon only grant is a plain 404 for anybody without a Blue Ribbon
    if item is None:
        raise Http404
    return order_page(request, item)


@onboarded
@never_cache
@require_POST
def cancel_order(request, pk):
    """A person takes back their own order while it is still pending (cookies back, once). Somebody else's order is a 404."""
    try:
        order = services.cancel(request.user, pk)
    except ValidationError as error:
        request.session["order_flash"] = error.messages[0]
        return redirect("dashboard_orders")
    if order is None:
        raise Http404
    request.session["order_flash"] = TAKEN_BACK
    return redirect("dashboard_orders")


# the private proofs

def viewable(user, pk):
    """The order if this person may see its proof: the owner, or staff who may view orders. None otherwise (the caller says 404)."""
    orders = Order.objects.filter(pk=pk)
    if not (user.is_staff and user.has_perm("orders.view_order")):
        orders = orders.filter(user=user)
    return orders.first()


def serve(proof):
    """A stored proof as an image, never guessed: the type comes from our own extension table, and the response cannot be cached or sniffed."""
    extension = Path(proof.name or "").suffix.lower() if proof else ""
    if extension not in PROOF_TYPES:
        raise Http404
    try:
        handle = proof.storage.open(proof.name, "rb")
    except (FileNotFoundError, SuspiciousFileOperation, ValueError, OSError):
        raise Http404 from None
    response = FileResponse(handle, content_type=PROOF_TYPES[extension], filename=f"proof{extension}", as_attachment=False)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    return response


@invited
@require_safe
def cart(request, pk):
    order = viewable(request.user, pk)
    if order is None:
        raise Http404
    return serve(order.cart_screenshot)
