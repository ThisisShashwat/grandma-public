/* Guide pages that embed the payout calculator (the guide lists the widget in its front matter, templates/pages/guide.html loads this). */
import { $ } from "../core/dom.js";
import { data } from "../core/data.js";
import { createPay } from "../modules/pay/math.js";
import { mount } from "../modules/pay/widget.js";

mount($("[data-pay-root]"), { pay: createPay(data.pay), faces: data.faces, tiers: data.tiers, levels: data.levels });
