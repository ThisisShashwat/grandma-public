"""The note a person fills in to get a grant. The form only validates (every rule is enforced again on the server in orders/services.py,
whatever the page showed, and the price is never in it); the page draws the fields by hand (templates/pages/order.html). It is built per
request for one grant: a plain grant has a quantity (if it stacks), upgrades (if it has them), a link and a cart screenshot; a by-hand
item only a note; a hardware grant a project and its parts. The pictures are decoded and re-encoded last, only once everything else
is right (submissions/images.py), with the caps from the admin settings."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from orders import rules
from orders.services import Part
from submissions import images, links
from submissions.forms import prose

FILL_IN = "Fill that in, dear."
NEEDS = {"required": FILL_IN}
NOTE_WITH_UPGRADES = "Tell me what you're really buying with the upgrades, dear: the exact thing, and why it costs more."
MIN_UPGRADE_NOTE = 15


class OrderForm(forms.Form):
    nonce = forms.CharField(max_length=32, error_messages={**NEEDS, "max_length": "That page has gone stale, dear. Open it again."})
    user_note = forms.CharField(required=False, max_length=600)

    def __init__(self, *args, cfg, hardware, proves, stackable, upgrades, projects, **kwargs):
        """`proves`: a plain grant, which shows its link and its cart. `upgrades`: (field name, item id) pairs. `projects`: (id, name) pairs a
        hardware grant may be for."""
        super().__init__(*args, **kwargs)
        self.hardware, self.proves, self.max_parts = hardware, proves, cfg.ORDER_MAX_PARTS
        self.max_bytes, self.max_side, self.max_pixels = cfg.ORDER_SCREENSHOT_MAX_MB * 1024 * 1024, cfg.ORDER_SCREENSHOT_MAX_SIDE, cfg.ORDER_SCREENSHOT_MAX_MEGAPIXELS * 1_000_000
        self.upgrade_fields = dict(upgrades)
        if stackable and not hardware:
            self.fields["quantity"] = forms.IntegerField(min_value=1, max_value=rules.MAX_QUANTITY, required=False, error_messages={"invalid": "A whole number, dear."})
        for name in self.upgrade_fields:
            self.fields[name] = forms.IntegerField(min_value=0, max_value=rules.MAX_QUANTITY, required=False, error_messages={"invalid": "A whole number, dear."})
        if proves:
            self.fields["product_url"] = forms.CharField(max_length=links.MAX_LENGTH, error_messages=NEEDS)
            self.fields["cart_screenshot"] = forms.FileField(error_messages={"required": "I need a screenshot of the cart, dear.", "empty": "That file is empty, dear.", "missing": "I need a screenshot of the cart, dear."})
        if hardware:
            self.fields["project"] = forms.ChoiceField(choices=[(str(pk), name) for pk, name in projects], error_messages={"required": "Which project is it for, dear?", "invalid_choice": "I don't know that one, dear."})
            self.fields["cart_screenshot"] = forms.FileField(required=False, error_messages={"empty": "That file is empty, dear."})
            for i in range(self.max_parts):
                self.add_part_fields(i)
        self.part_rows = [{"n": i + 1, **{key: self[f"part_{i}_{key}"] for key in ("name", "url", "price", "screenshot")}} for i in range(self.max_parts if hardware else 0)]

    def add_part_fields(self, i):
        self.fields[f"part_{i}_name"] = forms.CharField(required=False, max_length=80, error_messages={"max_length": "80 characters at the very most, dear."})
        self.fields[f"part_{i}_url"] = forms.CharField(required=False, max_length=links.MAX_LENGTH)
        self.fields[f"part_{i}_price"] = forms.DecimalField(
            required=False, min_value=Decimal("0.01"), max_value=rules.MAX_PRICE, max_digits=7, decimal_places=2,
            error_messages={"invalid": "A price in dollars, dear.", "min_value": "A part costs something, dear.", "max_value": f"Not more than ${rules.MAX_PRICE:,}, dear.",
                            "max_decimal_places": "Dollars and cents, dear. Two decimals at the most.", "max_digits": f"Not more than ${rules.MAX_PRICE:,}, dear."})
        self.fields[f"part_{i}_screenshot"] = forms.FileField(required=False, error_messages={"empty": "That file is empty, dear."})

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
        """Parts and upgrades are checked as a whole; the pictures are only decoded (the costly part) once everything else is right."""
        cleaned = super().clean()
        rows = self.collect_parts(cleaned) if self.hardware else []
        cleaned["parts"] = [part for _, part in rows]
        if any(cleaned.get(name) for name in self.upgrade_fields) and len(cleaned.get("user_note") or "") < MIN_UPGRADE_NOTE and "user_note" not in self.errors:
            self.add_error("user_note", NOTE_WITH_UPGRADES)
        if not self.errors:
            self.clean_pictures(cleaned, rows)
        return cleaned

    def collect_parts(self, cleaned):
        """The rows the person filled in, as (row number, Part). A row is filled when anything is in it, and then it needs a name, a link and a price."""
        rows = []
        for i in range(self.max_parts):
            name, url, price, shot = (cleaned.get(f"part_{i}_{key}") for key in ("name", "url", "price", "screenshot"))
            if not (name or url or price is not None or shot):
                continue
            for key, value in (("name", name), ("url", url), ("price", price)):
                if value in (None, "") and f"part_{i}_{key}" not in self.errors:
                    self.add_error(f"part_{i}_{key}", FILL_IN)
            if url and (problem := rules.url_problem(url)):
                self.add_error(f"part_{i}_url", problem)
            if shot:
                self.check_size(f"part_{i}_screenshot", shot)
            if name and url and price is not None:
                rows.append((i, Part(name.strip(), url.strip(), price, shot)))
        if problem := rules.parts_count_problem(len(rows), self.max_parts):
            self.add_error("part_0_name" if "part_0_name" not in self.errors else None, problem)
        return rows

    def check_size(self, field, upload):
        if upload.size > self.max_bytes:
            self.add_error(field, images.too_big_file(self.max_bytes))

    def clean_cart_screenshot(self):
        upload = self.cleaned_data.get("cart_screenshot")
        if upload and upload.size > self.max_bytes:
            raise ValidationError(images.too_big_file(self.max_bytes))
        return upload

    def clean_pictures(self, cleaned, rows):
        """Rebuild every upload from its pixels (EXIF and GPS gone, a random name). The first one that is no picture stops the work."""
        fields = ["cart_screenshot"] + [f"part_{i}_screenshot" for i, _ in rows]
        for field in fields:
            if cleaned.get(field):
                try:
                    cleaned[field] = images.clean_screenshot(cleaned[field], self.max_bytes, self.max_side, self.max_pixels)
                except ValidationError as error:
                    return self.add_error(field, error)
        cleaned["parts"] = [part._replace(screenshot=cleaned.get(f"part_{i}_screenshot") or None) for i, part in rows]

    def order_kwargs(self):
        """What orders.services.place_order takes, from a valid form. No price anywhere: the server reads it from the database."""
        cleaned = self.cleaned_data
        return {
            "nonce": cleaned["nonce"], "quantity": cleaned.get("quantity") or 1, "upgrades": {item_id: cleaned.get(name) or 0 for name, item_id in self.upgrade_fields.items()},
            "project_id": int(cleaned["project"]) if self.hardware else None, "product_url": cleaned.get("product_url", ""), "user_note": cleaned["user_note"],
            "cart_screenshot": cleaned.get("cart_screenshot") or None, "parts": cleaned["parts"], "max_parts": self.max_parts,
        }
