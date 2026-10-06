/* A form is sent once: a second click or Enter before the next page arrives is dropped (the server is idempotent as well; this only saves the round trip).
   Nothing is disabled, so the clicked button still travels with the form. The back button shows the page again, so it unlocks then. */
export function initOnce() {
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form.method.toLowerCase() !== "post" || event.defaultPrevented) return;
    if ("once" in form.dataset) return event.preventDefault();
    form.dataset.once = "1";
  });
  addEventListener("pageshow", () => document.querySelectorAll("form[data-once]").forEach((form) => delete form.dataset.once));
}
