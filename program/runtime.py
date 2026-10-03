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

    "LINK_SIGNUP": ("", "Where the Sign up buttons go (a form). Empty means a placeholder link that goes nowhere.", "link"),
    "LINK_SLACK": ("", "The Slack join link.", "link"),
    "LINK_REPO": ("", "The code repository.", "link"),
    "LINK_BOARD": ("", "Where complaints (new demands) get sent.", "link"),
    "LINK_RULES": ("", "The fine print and Hack Club policies.", "link"),
    "LINK_CONTACT": ("", "How to reach the organizer, for example mailto:you@example.com.", "link"),

    "DEAL_SIZE": (6, "How many notes Grandma deals in total when someone talks to her. They keep 1 to 3 of them, "
                     "that part is fixed. A category with fewer notes than this simply deals what it has.", "deal_size"),
    "REDEALS_FREE": (3, "How many times a person may ask Grandma to deal again, per project, for nothing.", "redeals_free"),
    "REDEAL_COST": (10, "Cookies a re-deal costs once the free ones are used up. Whole cookies, 0 makes them all free.", "cookies"),

    "PROJECT_MIN_DAYS": (10, "The earliest a project may be handed in, in days after it starts. Shown on the project page, not enforced yet.", "days"),
    "PROJECT_MAX_DAYS": (15, "The project's deadline, in days after it starts. The page counts down to it. Not enforced yet.", "days"),

    "SUBMISSION_CHECKS": (submission.default_checks_json(),
                          'The boxes a person must tick before they can hand a project in, as JSON: a list of {"key": "...", "text": "..."}. '
                          "Every box has to be ticked. The key is what gets stored, so keep one stable once people have ticked it.", "checks"),
    "BLOCKED_HOSTS": (submission.default_hosts_text(),
                      "Hosts a playable link may not be on (free tiers that fall asleep when idle), one per line. A host also blocks its "
                      "subdomains: streamlit.app blocks myapp.streamlit.app.", "hosts"),
    "SCREENSHOT_MAX_MB": (5, "The biggest screenshot a person may upload, in megabytes.", "megabytes"),

    "SLACK_WORKSPACE_URL": ("https://hackclub.slack.com", "The address of the Slack workspace. A public profile links to this address plus /team/ and the person's Slack ID. "
                                                         "Just the address, nothing after it.", "workspace"),
    "SHOW_REJECTED_PUBLICLY": (True, "Show rejected projects on the public profile and project pages (only after the person has heard the result). Off hides them."),
    "LEADERBOARD_SIZE": (50, "How many people the cookie board lists, the most cookies earned all time first.", "leaderboard_size"),
    "PUBLIC_PAGES_INDEXABLE": (False, "Let search engines list the public profiles, project pages, Blue Ribbon wall and cookie board. "
                                      "Off (the default) puts noindex, nofollow on them: the pages stay open to anyone with the link, but they are not found by searching, "
                                      "because the people on them are 13 to 18."),

    "TUTORIAL_ENABLED": (True, "Play the tutorial at the end of onboarding. Off skips it for everyone."),
    "TUTORIAL_FOR_NEW": ("both", "What someone who is new to Hack Club sees.", "tutorial_depth"),
    "TUTORIAL_FOR_SOME": ("second", "What someone who has shipped a project or two sees.", "tutorial_depth"),
    "TUTORIAL_FOR_VETERAN": ("offer", "What someone who ships all the time sees.", "tutorial_depth"),
}

# the admin's groups, in this order (a tuple, because constance sorts a plain dict by title)
FIELDSETS = (
    ("Launch", ("LAUNCH", "FREE_ASKS")),
    ("Program links", ("LINK_SIGNUP", "LINK_SLACK", "LINK_REPO", "LINK_BOARD", "LINK_RULES", "LINK_CONTACT")),
    ("Talk to Grandma (dealing notes)", ("DEAL_SIZE", "REDEALS_FREE", "REDEAL_COST")),
    ("Projects", ("PROJECT_MIN_DAYS", "PROJECT_MAX_DAYS")),
    ("Submitting", ("SUBMISSION_CHECKS", "BLOCKED_HOSTS", "SCREENSHOT_MAX_MB")),
    ("Public pages", ("SLACK_WORKSPACE_URL", "SHOW_REJECTED_PUBLICLY", "LEADERBOARD_SIZE", "PUBLIC_PAGES_INDEXABLE")),
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
    "days": ("django.forms.IntegerField", {"min_value": 1, "max_value": 90}),
    "checks": ("pages.fields.ChecksField",),
    "hosts": ("pages.fields.HostsField",),
    "megabytes": ("django.forms.IntegerField", {"min_value": 1, "max_value": 20}),
    "workspace": ("pages.fields.WorkspaceField",),
    "leaderboard_size": ("django.forms.IntegerField", {"min_value": 1, "max_value": 500}),
    "tutorial_depth": ("django.forms.ChoiceField", {"choices": DEPTHS}),
}
