/* The order page (templates/pages/order.html): the sums and a lock against a double click. The sums are a PREVIEW:
   the server works out the real price, the upgrades and the balance again from the database. Money is counted in whole cents, never in floats. */
import { $, $$ } from "../core/dom.js";

const form = $("[data-order]");
if (form) init(form);

function init(form) {
  const base = { cookies: Number(form.dataset.baseCookies), cents: Number(form.dataset.baseCents) };
  const balance = Number(form.dataset.balance);
  const button = $("[data-confirm]", form);
  const out = (name) => $(`[data-sum="${name}"]`, form);

  const whole = (input) => Math.max(parseInt(input?.value, 10) || 0, 0);
  const dollars = (c) => "$" + (c / 100).toLocaleString("en-US", { minimumFractionDigits: c % 100 ? 2 : 0, maximumFractionDigits: 2 });

  function sums() {
    let warn = "";
    const quantity = $("[data-quantity]", form) ? Math.max(whole($("[data-quantity]", form)), 1) : 1;
    const upgrades = $$("[data-upgrade]", form).map((input) => [whole(input), Number(input.dataset.cookies), Number(input.dataset.cents)]);
    const cookies = quantity * base.cookies + upgrades.reduce((total, [n, c]) => total + n * c, 0);
    const value = quantity * base.cents + upgrades.reduce((total, [n, , c]) => total + n * c, 0);
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

  form.addEventListener("input", sums);
  form.addEventListener("submit", (event) => {
    if ("sent" in form.dataset) return event.preventDefault();
    form.dataset.sent = "1";
    button.disabled = true;
  });
  addEventListener("pageshow", () => { delete form.dataset.sent; sums(); });   // the back button shows the page again: unlock it
  sums();
}
