/* The public pages are the same for everybody and never read the session (accounts/signed_in_flag.py), so the header and the big sign up buttons come
   as "Sign in" and this swaps them for the signed in links when the plain hint cookie says so. The hint only picks which links are shown. */
const signedIn = () => document.cookie.split("; ").includes("hgo_in=1");

/* The Log out button is a POST and needs the CSRF token, which no script may read from its cookie: it is fetched when the button is pressed. */
async function leave(event) {
  const form = event.currentTarget;
  if (form.querySelector('[name="csrfmiddlewaretoken"]')) return;
  event.preventDefault();
  const answer = await fetch("/csrf/", { credentials: "same-origin", headers: { Accept: "application/json" } });
  const { token } = await answer.json();
  form.append(Object.assign(document.createElement("input"), { type: "hidden", name: "csrfmiddlewaretoken", value: token }));
  form.submit();
}

export function initAuth() {
  const on = signedIn();
  document.querySelectorAll('[data-auth="in"]').forEach((e) => { e.hidden = !on; });
  document.querySelectorAll('[data-auth="out"]').forEach((e) => { e.hidden = on; });
  document.querySelectorAll("form.nav-leave").forEach((form) => form.addEventListener("submit", leave));
}
