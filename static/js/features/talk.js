/* Browser hints for a dialogue's text boxes (templates/components/talk.html). The server validates everything again:
   a hint only saves typing. A box marked data-prefill="timezone" starts with the browser's own zone when it is empty. */
import { $$ } from "../core/dom.js";

const hints = { timezone: () => Intl.DateTimeFormat().resolvedOptions().timeZone };

export function prefillHints() {
  for (const input of $$("input[data-prefill]")) {
    if (!input.value) input.value = hints[input.dataset.prefill]?.() ?? "";
  }
}
