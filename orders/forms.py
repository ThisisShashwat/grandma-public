"""The note a person fills in to get a grant. The form only validates (every rule is enforced again on the server in orders/services.py,
whatever the page showed, and the price is never in it); the page draws the fields by hand (templates/pages/order.html). It is built per
request for one grant: a plain grant has a quantity (if it stacks), upgrades (if it has them), a link and a cart screenshot; a by-hand
item only a note. The pictures are decoded and re-encoded last, only once everything else is right (submissions/images.py), with the caps
from the admin settings: the fields first, then the business checks the view hands in as `precheck` (the limit, the stock, the balance:
services.precheck), and only then the decoding."""
from django import forms
from django.core.exceptions import ValidationError

from orders import rules
from submissions import images, links
from submissions.forms import prose, run_precheck

FILL_IN = "Fill that in, dear."
NEEDS = {"required": FILL_IN}
NOTE_WITH_UPGRADES = "Tell me what you're really buying with the upgrades, dear: the exact thing, and why it costs more."
MIN_UPGRADE_NOTE = 15


class OrderForm(forms.Form):
    nonce = forms.CharField(max_length=32, error_messages={**NEEDS, "max_length": "That page has gone stale, dear. Open it again."})
    user_note = forms.CharField(required=False, max_length=600)

    def __init__(self, *args, cfg, proves, stackable, upgrades, precheck=None, **kwargs):
        """`proves`: a plain grant, which shows its link and its cart. `upgrades`: (field name, item id) pairs. `precheck(quantity, upgrades)`:
        the cheap business checks (services.precheck for this person and grant), raising ValidationError, run before any picture is decoded."""
        super().__init__(*args, **kwargs)
        self.proves = proves
        self.precheck = precheck
        self.max_bytes, self.max_side, self.max_pixels = cfg.ORDER_SCREENSHOT_MAX_MB * 1024 * 1024, cfg.ORDER_SCREENSHOT_MAX_SIDE, cfg.ORDER_SCREENSHOT_MAX_MEGAPIXELS * 1_000_000
        self.upgrade_fields = dict(upgrades)
        if stackable:
            self.fields["quantity"] = forms.IntegerField(min_value=1, max_value=rules.MAX_QUANTITY, required=False, error_messages={"invalid": "A whole number, dear."})
        for name in self.upgrade_fields:
            self.fields[name] = forms.IntegerField(min_value=0, max_value=rules.MAX_QUANTITY, required=False, error_messages={"invalid": "A whole number, dear."})
        if proves:
            self.fields["product_url"] = forms.CharField(max_length=links.MAX_LENGTH, error_messages=NEEDS)
            self.fields["cart_screenshot"] = forms.FileField(error_messages={"required": "I need a screenshot of the cart, dear.", "empty": "That file is empty, dear.", "missing": "I need a screenshot of the cart, dear."})

    def clean_nonce(self):
        nonce = self.cleaned_data["nonce"]
        if not rules.NONCE.fullmatch(nonce):
            raise ValidationError("That page has gone stale, dear. Open it again.")
        return nonce

    def clean_product_url(self):
        url = self.cleaned_data["product_url"].strip()
        if problem := rules.url_problem(url):
            raise ValidationError(problem)
        return url

    def clean_user_note(self):
        return prose(self.cleaned_data["user_note"])

    def clean(self):
        """Upgrades are checked as a whole, then the business checks; the pictures are only decoded (the costly part) once everything else is right."""
        cleaned = super().clean()
        if any(cleaned.get(name) for name in self.upgrade_fields) and len(cleaned.get("user_note") or "") < MIN_UPGRADE_NOTE and "user_note" not in self.errors:
            self.add_error("user_note", NOTE_WITH_UPGRADES)
        if not self.errors:
            run_precheck(self, self.precheck, cleaned.get("quantity") or 1, {item_id: cleaned.get(name) or 0 for name, item_id in self.upgrade_fields.items()})
        if not self.errors:
            self.clean_pictures(cleaned)
        return cleaned

    def clean_cart_screenshot(self):
        upload = self.cleaned_data.get("cart_screenshot")
        if upload and upload.size > self.max_bytes:
            raise ValidationError(images.too_big_file(self.max_bytes))
        return upload

    def clean_pictures(self, cleaned):
        """Rebuild every upload from its pixels (EXIF and GPS gone, a random name)."""
        if cleaned.get("cart_screenshot"):
            try:
                cleaned["cart_screenshot"] = images.clean_screenshot(cleaned["cart_screenshot"], self.max_bytes, self.max_side, self.max_pixels)
            except ValidationError as error:
                self.add_error("cart_screenshot", error)

    def order_kwargs(self):
        """What orders.services.place_order takes, from a valid form. No price anywhere: the server reads it from the database."""
        cleaned = self.cleaned_data
        return {
            "nonce": cleaned["nonce"],
            "quantity": cleaned.get("quantity") or 1,
            "upgrades": {item_id: cleaned.get(name) or 0 for name, item_id in self.upgrade_fields.items()},
            "product_url": cleaned.get("product_url", ""),
            "user_note": cleaned["user_note"],
            "cart_screenshot": cleaned.get("cart_screenshot") or None,
        }
