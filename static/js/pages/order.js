/* The order page (templates/pages/order.html): the sums, a way to add more part rows, and a lock against a double click. The sums are a PREVIEW:
   the server works out the real price, the upgrades and the balance again from the database. Money is counted in whole cents, never in floats. */
import { $, $$ } from "../core/dom.js";

const form = $("[data-order]");
if (form) init(form);

function init(form) {
  const base = { cookies: Number(form.dataset.baseCookies), cents: Number(form.dataset.baseCents) };
  const balance = Number(form.dataset.balance);
  const hardware = "hardware" in form.dataset;
  const up = { cookies: Number(form.dataset.upCookies || 0), cents: Number(form.dataset.upCents || 0), most: form.dataset.upMost === "" ? Infinity : Number(form.dataset.upMost) };
  const button = $("[data-confirm]", form);
  const out = (name) => $(`[data-sum="${name}"]`, form);

  const whole = (input) => Math.max(parseInt(input?.value, 10) || 0, 0);
  const cents = (input) => { const n = Math.round(parseFloat(input.value) * 100); return Number.isFinite(n) && n > 0 ? n : 0; };
  const dollars = (c) => "$" + (c / 100).toLocaleString("en-US", { minimumFractionDigits: c % 100 ? 2 : 0, maximumFractionDigits: 2 });

  function sums() {
    let cookies, value, warn = "";
    if (hardware) {
      const parts = $$("[data-part-price]", form).reduce((total, input) => total + cents(input), 0);
      const needed = parts > base.cents && up.cents ? Math.ceil((parts - base.cents) / up.cents) : 0;
      cookies = base.cookies + needed * up.cookies;
      value = base.cents + needed * up.cents;
      out("parts").textContent = dollars(parts);
      if (out("upgrades")) out("upgrades").textContent = needed;
      if (parts > base.cents && !up.cents) warn = "Those parts cost more than this grant, dear, and it has no upgrades to make up the difference.";
      else if (needed > up.most) warn = "That needs more upgrades than I allow on one grant, dear.";
    } else {
      const quantity = $("[data-quantity]", form) ? Math.max(whole($("[data-quantity]", form)), 1) : 1;
      const upgrades = $$("[data-upgrade]", form).map((input) => [whole(input), Number(input.dataset.cookies), Number(input.dataset.cents)]);
      cookies = quantity * base.cookies + upgrades.reduce((total, [n, c]) => total + n * c, 0);
      value = quantity * base.cents + upgrades.reduce((total, [n, , c]) => total + n * c, 0);
    }
    const left = balance - cookies;
    out("cookies").textContent = cookies.toLocaleString("en-US");
    out("value").textContent = dollars(value);
    out("left").textContent = left.toLocaleString("en-US");
    if (left < 0) warn = `You'd be ${(-left).toLocaleString("en-US")} cookies short, dear. I don't do credit.`;
    const note = out("warn");
    note.textContent = warn;
    note.hidden = !warn;
    $(".order-sums", form).classList.toggle("is-short", left < 0);
    button.disabled = left < 0 || "sent" in form.dataset;
  }

  function parts() {
    const spare = $$("[data-part][data-extra]", form).filter((row) => ![...$$("input", row)].some((input) => (input.type === "file" ? input.files.length : input.value)));
    spare.forEach((row) => { row.hidden = true; });
    const more = $("[data-more-parts]", form);
    if (!more || !spare.length) return;
    more.parentElement.hidden = false;
    more.addEventListener("click", () => {
      const next = spare.find((row) => row.hidden);
      if (next) { next.hidden = false; $("input", next).focus(); }
      more.parentElement.hidden = !spare.some((row) => row.hidden);
    });
  }

  form.addEventListener("input", sums);
  form.addEventListener("submit", (event) => {
    if ("sent" in form.dataset) return event.preventDefault();
    form.dataset.sent = "1";
    button.disabled = true;
  });
  addEventListener("pageshow", () => { delete form.dataset.sent; sums(); });   // the back button shows the page again: unlock it
  parts();
  sums();
}
