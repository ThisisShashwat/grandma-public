/* "Are you sure?" before a form that spends cookies: any form with data-confirm="the question" asks first, in Grandma's voice, in a native <dialog>.
   Yes sends the form, Not now closes the dialog and sends nothing. Without JavaScript the form just sends (the price is on the button), so the page works
   without any of this. It listens before core/once.js does, so the first, stopped submit never counts as sent. */
let dialog;

function build() {
  const box = document.createElement("dialog");
  box.className = "confirm";
  box.innerHTML = '<form method="dialog"><p class="confirm-ask"></p><p class="confirm-actions"><button class="btn" value="yes">Yes, dear</button> <button class="btn btn--plain" value="no">Not now</button></p></form>';
  document.body.append(box);
  return box;
}

function ask(question, then) {
  dialog ??= build();
  dialog.querySelector(".confirm-ask").textContent = question;
  dialog.addEventListener("close", () => { if (dialog.returnValue === "yes") then(); }, { once: true });
  dialog.returnValue = "";
  dialog.showModal();
}

export function confirmForms() {
  document.addEventListener("submit", (event) => {
    const form = event.target;
    const question = form.dataset?.confirm;
    if (!question || form.dataset.confirmed) return;
    event.preventDefault();
    ask(question, () => { form.dataset.confirmed = "1"; form.requestSubmit(event.submitter); });
  }, true);
  addEventListener("pageshow", () => document.querySelectorAll("form[data-confirmed]").forEach((form) => delete form.dataset.confirmed));
}
