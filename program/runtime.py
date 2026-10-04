"""The settings staff edit in the Django admin (django-constance, database backend, "Constance" in the admin sidebar).

Data only, no Django import. The values here are the DEFAULTS: they apply until somebody saves another value, and they
equal what used to be hard-coded, so an untouched site renders exactly as before. Facts that belong in code (the payout
maths, the footer's Hack Club links, the site name) stay in payout.py and config.py. Why the split: docs/accounts.md.

grandma/settings.py hands CONFIG, FIELDS and FIELDSETS to constance. Read values with pages.live.live().
"""
from program import submission
from program.tutorial import DEPTHS

# key: (default, help text shown in the admin, optional name of a field in FIELDS)
CONFIG = {
    "LAUNCH": ("2026-10-05T12:00:00Z",   # TODO: real launch moment
               "When the program opens, as a UTC time like 2026-10-05T12:00:00Z (or with an offset like +05:30). "
               "The countdown on the home page counts down to it.", "launch"),
    "FREE_ASKS": (3, "How many free asks the fridge on the home page offers.", "free_asks"),
    "BETA_MODE": (True, "While on, only people with beta access (and staff) can use the participant features: onboarding, the dashboard, Talk to Grandma, projects, "
                        "submitting and orders. Everybody else is sent to a page saying the kitchen is open to a few testers. Give access in the admin under Profiles. "
                        "Switch it off at the public launch."),

    "LINK_SIGNUP": ("", "Where the Sign up buttons go (a form). Empty means a placeholder link that goes nowhere.", "link"),
    "LINK_SLACK": ("", "The Slack join link.", "link"),
    "LINK_SLACK_GRANDMA": ("", "The #grandma channel in Slack, where people chat. Empty means the guides show the name as plain text, not a link.", "link"),
    "LINK_SLACK_HELP": ("", "The #grandma-help channel in Slack, where people ask for help. Empty means the guides show the name as plain text, not a link. "
                            "The dashboard's Slack help button goes here.", "link"),
    "LINK_REPO": ("", "The code repository.", "link"),
    "LINK_BOARD": ("", "Where complaints (new demands) get sent.", "link"),
    "LINK_RULES": ("", "The fine print and Hack Club policies.", "link"),
    "LINK_CONTACT": ("", "How to reach the organizer, for example mailto:you@example.com.", "link"),

    "DEAL_SIZE": (6, "How many notes Grandma deals in total when someone talks to her. They keep 1 to 3 of them, "
                     "that part is fixed. A category with fewer notes than this simply deals what it has.", "deal_size"),
    "REDEALS_FREE": (3, "How many times a person may ask Grandma to deal again, per project, for nothing.", "redeals_free"),
    "REDEAL_COST": (10, "Cookies a re-deal costs once the free ones are used up. Whole cookies, 0 makes them all free.", "cookies"),

    "SUBMISSION_CHECKS": (submission.default_checks_json(),
                          'The boxes a person must tick before they can hand a project in, as JSON: a list of {"key": "...", "text": "..."}. '
                          "Every box has to be ticked. The key is what gets stored, so keep one stable once people have ticked it.", "checks"),
    "BLOCKED_HOSTS": (submission.default_hosts_text(),
                      "Hosts a playable link may not be on (free tiers that fall asleep when idle, tunnels to a laptop, notebooks), one per line. A host also blocks its "
                      "subdomains: streamlit.app blocks myapp.streamlit.app.", "hosts"),
    "SCREENSHOT_MAX_MB": (5, "The biggest screenshot a person may upload, in megabytes.", "megabytes"),
    "MAX_ROUNDS": (3, "How many times one project may be handed in, counting the first time. When you ask for changes, the person fixes it and hands it in again as the next round; "
                      "on the last round you can only approve or reject. Between 1 and 10.", "rounds"),

    "ORDER_SCREENSHOT_MAX_MB": (5, "The biggest cart or part screenshot a person may upload with an order, in megabytes.", "megabytes"),
    "ORDER_SCREENSHOT_MAX_SIDE": (6000, "The longest side of an order screenshot, in pixels. Anything bigger is refused.", "pixels"),
    "ORDER_SCREENSHOT_MAX_MEGAPIXELS": (20, "The most pixels (width times height, in millions) an order screenshot may have. Checked before it is decoded.", "megapixels"),

    "SHOW_REJECTED_PUBLICLY": (True, "Show rejected projects on the public profile and project pages (only after the person has heard the result). Off hides them."),
    "LEADERBOARD_SIZE": (50, "How many people the cookie board lists, the most cookies earned all time first.", "leaderboard_size"),
    "PUBLIC_PAGES_INDEXABLE": (False, "Let search engines list the public profiles, project pages, Blue Ribbon wall and cookie board. "
                                      "Off (the default) puts noindex, nofollow on them: the pages stay open to anyone with the link, but they are not found by searching, "
                                      "because the people on them are 13 to 18."),

    "SLACK_NOTIFICATIONS": (False, "Send a Slack direct message from the program's bot when you ask for changes on a project. It needs the bot token in the environment "
                                   "(SLACK_BOT_TOKEN, never set here) and the person's Slack ID. Off (the default) sends nothing."),

    "HCA_LOGIN": (False, "When on, /login/ redirects everybody straight to Hack Club (there is no password form), "
                         "the first sign-in makes their account which stays outside the beta until staff give it access, "
                         "and it needs the three environment values (HCA_CLIENT_ID, HCA_CLIENT_SECRET, HCA_ISSUER; the id and secret are never set here)."),
    "HCA_REQUIRE_ELIGIBLE": (True, "A person's first Hack Club sign-in must have ysws_eligible true or no account is made; later sign-ins are never re-checked. "
                                   "Off lets in anyone with a valid Slack ID on their first sign-in."),
    "HACKATIME_ENABLED": (False, "Make the Hackatime step of onboarding real and mandatory: people connect their Hackatime account and cannot go on until they have. "
                                 "It needs the environment values (HACKATIME_CLIENT_ID, HACKATIME_CLIENT_SECRET, HACKATIME_BASE_URL; the id and secret are never set here). "
                                 "While it is on, a person whose connection fails (wrong credentials, a wrong redirect address, Hackatime down, no Hackatime account) cannot finish onboarding: "
                                 "test with a fresh person before leaving it on. "
                                 "Off (the default) keeps the greyed-out button and lets people carry on."),
    "HACKATIME_REQUIRED": (False, "A project cannot be handed in without checked Hackatime hours: the person has to press Check my hours on the note, "
                                  "and the check must show at least ten minutes on that project, made after it started (and after its last hand-in) and within the last 24 hours. "
                                  "It needs HACKATIME_ENABLED on (and does nothing without it). "
                                  "Off (the default) lets people hand in with or without a check; a check that was made is still kept and shown to reviewers."),

    "TUTORIAL_ENABLED": (True, "Play the tutorial at the end of onboarding. Off skips it for everyone."),
    "TUTORIAL_FOR_NEW": ("both", "What someone who is new to Hack Club sees.", "tutorial_depth"),
    "TUTORIAL_FOR_SOME": ("second", "What someone who has shipped a project or two sees.", "tutorial_depth"),
    "TUTORIAL_FOR_VETERAN": ("offer", "What someone who ships all the time sees.", "tutorial_depth"),
}

# the admin's groups, in this order (a tuple, because constance sorts a plain dict by title)
FIELDSETS = (
    ("Launch", ("LAUNCH", "FREE_ASKS", "BETA_MODE")),
    ("Program links", ("LINK_SIGNUP", "LINK_SLACK", "LINK_SLACK_GRANDMA", "LINK_SLACK_HELP", "LINK_REPO", "LINK_BOARD", "LINK_RULES", "LINK_CONTACT")),
    ("Talk to Grandma (dealing notes)", ("DEAL_SIZE", "REDEALS_FREE", "REDEAL_COST")),
    ("Submitting", ("SUBMISSION_CHECKS", "BLOCKED_HOSTS", "SCREENSHOT_MAX_MB", "MAX_ROUNDS")),
    ("Orders", ("ORDER_SCREENSHOT_MAX_MB", "ORDER_SCREENSHOT_MAX_SIDE", "ORDER_SCREENSHOT_MAX_MEGAPIXELS")),
    ("Public pages", ("SHOW_REJECTED_PUBLICLY", "LEADERBOARD_SIZE", "PUBLIC_PAGES_INDEXABLE")),
    ("Notifications", ("SLACK_NOTIFICATIONS",)),
    ("Accounts", ("HCA_LOGIN", "HCA_REQUIRE_ELIGIBLE", "HACKATIME_ENABLED", "HACKATIME_REQUIRED")),
    ("Onboarding tutorial", ("TUTORIAL_ENABLED", "TUTORIAL_FOR_NEW", "TUTORIAL_FOR_SOME", "TUTORIAL_FOR_VETERAN")),
)

# the admin form field behind each named type: (dotted path, keyword arguments)
FIELDS = {
    "launch": ("pages.fields.LaunchField",),
    "link": ("pages.fields.LinkField",),
    "free_asks": ("django.forms.IntegerField", {"min_value": 0, "max_value": 20}),
    "deal_size": ("django.forms.IntegerField", {"min_value": 3, "max_value": 28}),
    "redeals_free": ("django.forms.IntegerField", {"min_value": 0, "max_value": 20}),
    "cookies": ("django.forms.IntegerField", {"min_value": 0, "max_value": 1000}),
    "checks": ("pages.fields.ChecksField",),
    "hosts": ("pages.fields.HostsField",),
    "megabytes": ("django.forms.IntegerField", {"min_value": 1, "max_value": 20}),
    "rounds": ("django.forms.IntegerField", {"min_value": 1, "max_value": 10}),         # the ceiling is submissions.rules.MAX_ROUND_LIMIT (a test pins them)
    "pixels": ("django.forms.IntegerField", {"min_value": 500, "max_value": 10000}),
    "megapixels": ("django.forms.IntegerField", {"min_value": 1, "max_value": 40}),
    "workspace": ("pages.fields.WorkspaceField",),
    "leaderboard_size": ("django.forms.IntegerField", {"min_value": 1, "max_value": 500}),
    "tutorial_depth": ("django.forms.ChoiceField", {"choices": DEPTHS}),
}
