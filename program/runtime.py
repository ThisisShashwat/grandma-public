"""The settings staff edit in the Django admin (django-constance, database backend, "Constance" in the admin sidebar).

Data only, no Django import. The values here are the DEFAULTS: they apply until somebody saves another value, and they
equal what used to be hard-coded, so an untouched site renders exactly as before. Facts that belong in code (the payout
maths, the footer's Hack Club links, the site name) stay in payout.py and config.py. Why the split: docs/accounts.md.

grandma/settings.py hands CONFIG, FIELDS and FIELDSETS to constance. Read values with pages.live.live().
"""
from program import submission
from program.content import regions
from program.tutorial import DEPTHS

# key: (default, help text shown in the admin, optional name of a field in FIELDS)
CONFIG = {
    "LAUNCH": ("2026-10-15T15:00:00Z",
               "When the program opens, as a UTC time like 2026-10-15T15:00:00Z, which is 20:30 in India (or with an offset like +05:30). "
               "The countdown on the home page counts down to it.", "launch"),
    "BETA_MODE": (True, "While on, only people with beta access (and staff) can use the participant features: onboarding, the dashboard, Talk to Grandma, projects, "
                        "submitting and orders. Everybody else is sent to a page saying the kitchen is open to a few testers. Give access in the admin under Profiles. "
                        "Switch it off at the public launch."),

    "LINK_SIGNUP": ("/login/","Where the Sign up buttons go. The default /login/ is the Hack Club sign-in, whose first sign-in makes the account. "
                              "A web link, a mailto: link or a path on this site starting with / is accepted. Empty means a placeholder link that goes nowhere.", "link"),
    "LINK_SLACK": ("https://hackclub.com/slack/", "The Slack join link, for people who are not in the Hack Club Slack yet.", "link"),
    "LINK_SLACK_GRANDMA": ("https://hackclub.slack.com/channels/grandma", "The #grandma channel in Slack, where people chat. Empty means the guides show the name as plain text, not a link.", "link"),
    "LINK_SLACK_HELP": ("https://hackclub.slack.com/channels/grandma-help", "The #grandma-help channel in Slack, where people ask for help. Empty means the guides show the name as plain text, not a link. "
                            "The dashboard's Slack help button goes here.", "link"),
    "LINK_SLACK_BULLETIN": ("https://hackclub.slack.com/channels/grandma-bulletin", "The #grandma-bulletin channel in Slack, where the news goes. Empty means the guides show the name as plain text, not a link.", "link"),
    "LINK_BOARD": ("", "Where complaints (new demands) get sent.", "link"),
    "LINK_CONTACT": ("", "How to reach the organizer, for example mailto:you@example.com.", "link"),

    "DEAL_SIZE": (9, "How many notes Grandma deals in total when someone talks to her, split evenly over mild, medium and spicy (9 is 3 of each). They keep 1 to 3 of them, "
                     "that part is fixed. A category with fewer notes than this simply deals what it has.", "deal_size"),
    "REDEALS_FREE": (3, "How many times a person may ask Grandma to deal again, per project, for nothing. "
                        "It also sets how many free asks the fridge on the home page offers.", "redeals_free"),
    "REDEAL_COST": (10, "Cookies a re-deal costs once the free ones are used up. Whole cookies, 0 makes them all free.", "cookies"),
    "SUGGEST_COST": (5, "Cookies it costs to put a suggestion on the board (a new demand or a Pantry item). Whole cookies, 0 makes it free. Keep it above the vote cost.", "cookies"),
    "VOTE_COST": (1, "Cookies it costs to vote for somebody's suggestion. Whole cookies, 0 makes voting free. A vote does nothing but move the suggestion up the list.", "cookies"),
    "MAX_NEW_PROJECTS_PER_DAY": (20, "The most projects one person may start in a rolling 24 hours, abandoned ones included. This is a generous limit against abuse (a script filling the "
                                     "database), not a program rule: people may make as many projects as they like, one at a time. 0 means no limit. Whole numbers, 0 to 1000.", "per_person_cap"),
    "DEALING_EXPIRY_DAYS": (7, "How many days a hand may sit on Grandma's table, never confirmed, before the project is given up (it becomes abandoned and its person may start "
                               "another). Counted from when the hand was dealt. A project already being built is never touched. Whole days, 1 to 90.", "expiry_days"),

    "SUBMISSION_CHECKS": (submission.default_checks_json(),
                          'The boxes a person must tick before they can hand a project in, as JSON: a list of {"key": "...", "text": "..."}. '
                          "Every box has to be ticked. The key is what gets stored, so keep one stable once people have ticked it.", "checks"),
    "BLOCKED_HOSTS": (submission.default_hosts_text(),
                      "Hosts a playable link may not be on (free tiers that fall asleep when idle, tunnels to a laptop, notebooks), one per line. A host also blocks its "
                      "subdomains: streamlit.app blocks myapp.streamlit.app.", "hosts"),
    "SCREENSHOT_MAX_MB": (5, "The biggest screenshot a person may upload, in megabytes. Whatever is uploaded is shrunk before it is kept: no side over 2000 pixels and at most 4 million pixels in all.", "megabytes"),
    "MAX_ROUNDS": (3, "How many times one project may be handed in, counting the first time. When you ask for changes, the person fixes it and hands it in again as the next round; "
                      "on the last round you can only approve or reject. Between 1 and 10.", "rounds"),
    "MAX_IN_REVIEW": (3, "The most hand-ins one person may have waiting for a reviewer at once, across all their projects. A hand-in that has been decided no longer counts, "
                         "even before the person has collected it. At the limit Grandma tells them to wait. 0 means no limit. Whole numbers, 0 to 1000.", "per_person_cap"),

    "ORDER_CART_SCREENSHOT": (True, "Ask for a screenshot of the cart with a grant, and keep it privately. Off: a person gives only the link to the product, no picture is asked for, uploaded or stored (use it while there is nowhere safe to keep the pictures). Pictures already kept are not touched, and staff can still open them."),
    "ORDER_SCREENSHOT_MAX_MB": (5, "The biggest cart or part screenshot a person may upload with an order, in megabytes. Whatever is uploaded is shrunk before it is kept: no side over 2000 pixels and at most 4 million pixels in all.", "megabytes"),
    "ORDER_SCREENSHOT_MAX_SIDE": (6000, "The longest side of an order screenshot, in pixels. Anything bigger is refused.", "pixels"),
    "ORDER_SCREENSHOT_MAX_MEGAPIXELS": (10, "The most pixels (width times height, in millions) an order screenshot may have when it is uploaded. Checked before it is decoded. "
                                            "10 lets a 4K monitor screenshot (8.3 million) through; it is shrunk to 4 million before it is kept.", "megapixels"),
    "MAX_ORDERS_PER_DAY": (10, "The most orders one person may place in a rolling 24 hours. Orders they took back and orders that were turned down count too, so placing and cancelling "
                               "cannot be used to fill the disk. 0 means no limit. Whole numbers, 0 to 1000.", "per_person_cap"),

    "SHOW_REJECTED_PUBLICLY": (True, "Show rejected projects on the public profile and project pages (only after the person has heard the result). Off hides them."),
    "LEADERBOARD_SIZE": (50, "How many people the cookie board lists, the most cookies earned all time first.", "leaderboard_size"),
    "PUBLIC_PAGES_INDEXABLE": (False, "Let search engines list the public profiles, project pages, Blue Ribbon wall and cookie board. "
                                      "Off (the default) puts noindex, nofollow on them: the pages stay open to anyone with the link, but they are not found by searching, "
                                      "because the people on them are 13 to 18."),

    "HOME_PANTRY_PEEK": (True, "Show a few Pantry items on the home page, in a section called A peek in the Pantry, right after Grandma's Demands. "
                               "They are picked from the real shop, in shop order, never a ribbon only item, and only items ticked Show on the home page in the shop's admin list. "
                               "On is the default; off shows nothing."),
    "HOME_RIBBON_PEEK": (False, "Show the newest projects of the Blue Ribbon wall on the home page, in a section called Pinned on Grandma's wall, right after the Pantry peek. "
                                "It shows exactly what the wall shows (only ribbons their makers have collected). Off (the default) shows nothing and the home page is as it was."),
    "HOME_PEEK_COUNT": (4, "How many items each home page peek shows, 1 to 12 (the Pantry peek and the Blue Ribbon wall peek). The Pantry peek takes the first ticked ones in shop order "
                           "and skips by hand items and sold out items; the wall peek takes the newest.", "peek_count"),

    "SLACK_NOTIFICATIONS": (False, "Send a Slack direct message from the program's bot when a project is approved, rejected or needs changes (the message only says to come to the dashboard). "
                                   "It needs the bot token in the environment (SLACK_BOT_TOKEN, never set here) and the person's Slack ID. Off (the default) sends nothing."),
    "SLACK_CHANNEL_IDS": ("", "The Slack channels onboarding offers to add a new person to, as channel IDs (C followed by capital letters and digits, from the bottom of each channel's "
                              "About tab in Slack), separated by commas, at most 5. The bot must already be a member of each channel (add the app to it by hand). Empty (the default) "
                              "means the question is never asked and nobody is added. It needs the bot token in the environment (SLACK_BOT_TOKEN, never set here).", "slack_channels"),

    "HCA_LOGIN": (False, "When on, /login/ redirects everybody straight to Hack Club (there is no password form), "
                         "the first sign-in makes their account which stays outside the beta until staff give it access, "
                         "and it needs the three environment values (HCA_CLIENT_ID, HCA_CLIENT_SECRET, HCA_ISSUER; the id and secret are never set here)."),
    "HCA_REQUIRE_ELIGIBLE": (True, "A person's first Hack Club sign-in must have ysws_eligible true or no account is made; later sign-ins are never re-checked. "
                                   "Off lets in anyone with a valid Slack ID on their first sign-in. A Slack ID listed in STAFF_SLACK_IDS (the environment) is never refused by it."),
    "HACKATIME_ENABLED": (False, "Make the Hackatime step of onboarding real and mandatory: people connect their Hackatime account and cannot go on until they have. "
                                 "It needs the environment values (HACKATIME_CLIENT_ID, HACKATIME_CLIENT_SECRET, HACKATIME_BASE_URL; the id and secret are never set here). "
                                 "While it is on, a person whose connection fails (wrong credentials, a wrong redirect address, Hackatime down, no Hackatime account) cannot finish onboarding: "
                                 "test with a fresh person before leaving it on. "
                                 "Off (the default) keeps the greyed-out button and lets people carry on."),
    "HACKATIME_REQUIRED": (False, "A project cannot be handed in without checked Hackatime hours: the person has to press Check my hours on the note, "
                                  "and the check must show at least ten minutes on that project, made after it started (and after its last hand-in) and within the last 24 hours. "
                                  "It needs HACKATIME_ENABLED on (and does nothing without it). "
                                  "Off (the default) lets people hand in with or without a check; a check that was made is still kept and shown to reviewers."),

    "ARI_ENABLED": (False, "Send every hand-in to Ari (HQ's review tool) and apply the decisions it sends back to /ari/result/. It needs ARI_PROGRAM_ID, ARI_INGEST_SECRET and "
                           "ARI_OUTBOUND_SECRET in the environment (never set here). Off (the default) sends nothing and the address answers 404. "
                           "Hand-ins made while it was off are not sent later: review those in the Review form."),

    "REGIONS": (regions.default_text(), "Where a person can say they live, asked once in onboarding: one per line as CODE: Label, shown in this order. "
                                        "A code is two capital letters or digits (people keep their code if you rename its label). At least two lines, and the XX line "
                                        "(the catch-all, XX: Somewhere else) must stay.", "regions"),

    "TUTORIAL_ENABLED": (True, "Play the tutorial at the end of onboarding. Off skips ALL of it for everyone. On, the two lessons about this program (how Help Grandma Out works, cookies and the Pantry) always play for everybody."),
    "TUTORIAL_FOR_NEW": ("play", "The Hack Club basics (what shipping means, You Ship We Ship, what a grant is) for someone who is new to Hack Club.", "tutorial_depth"),
    "TUTORIAL_FOR_SOME": ("offer", "The Hack Club basics for someone who has shipped a project or two.", "tutorial_depth"),
    "TUTORIAL_FOR_VETERAN": ("offer", "The Hack Club basics for someone who ships all the time.", "tutorial_depth"),
}

# the admin's groups, in this order (a tuple, because constance sorts a plain dict by title)
FIELDSETS = (
    ("Launch", ("LAUNCH", "BETA_MODE")),
    ("Program links", ("LINK_SIGNUP", "LINK_SLACK", "LINK_SLACK_GRANDMA", "LINK_SLACK_HELP", "LINK_SLACK_BULLETIN", "LINK_BOARD", "LINK_CONTACT")),
    ("Talk to Grandma (dealing notes)", ("DEAL_SIZE", "REDEALS_FREE", "REDEAL_COST", "MAX_NEW_PROJECTS_PER_DAY", "DEALING_EXPIRY_DAYS")),
    ("Submitting", ("SUBMISSION_CHECKS", "BLOCKED_HOSTS", "SCREENSHOT_MAX_MB", "MAX_ROUNDS", "MAX_IN_REVIEW")),
    ("Orders", ("ORDER_CART_SCREENSHOT", "ORDER_SCREENSHOT_MAX_MB", "ORDER_SCREENSHOT_MAX_SIDE", "ORDER_SCREENSHOT_MAX_MEGAPIXELS", "MAX_ORDERS_PER_DAY")),
    ("Suggestion board", ("SUGGEST_COST", "VOTE_COST")),
    ("Public pages", ("SHOW_REJECTED_PUBLICLY", "LEADERBOARD_SIZE", "PUBLIC_PAGES_INDEXABLE")),
    ("Home page", ("HOME_PANTRY_PEEK", "HOME_RIBBON_PEEK", "HOME_PEEK_COUNT")),
    ("Notifications", ("SLACK_NOTIFICATIONS", "SLACK_CHANNEL_IDS")),
    ("Accounts", ("HCA_LOGIN", "HCA_REQUIRE_ELIGIBLE", "HACKATIME_ENABLED", "HACKATIME_REQUIRED", "ARI_ENABLED")),
    ("Onboarding questions", ("REGIONS",)),
    ("Onboarding tutorial", ("TUTORIAL_ENABLED", "TUTORIAL_FOR_NEW", "TUTORIAL_FOR_SOME", "TUTORIAL_FOR_VETERAN")),
)

# the admin form field behind each named type: (dotted path, keyword arguments)
FIELDS = {
    "launch": ("pages.fields.LaunchField",),
    "link": ("pages.fields.LinkField",),
    "deal_size": ("django.forms.IntegerField", {"min_value": 3, "max_value": 28}),
    "redeals_free": ("django.forms.IntegerField", {"min_value": 0, "max_value": 20}),
    "cookies": ("django.forms.IntegerField", {"min_value": 0, "max_value": 1000}),
    "per_person_cap": ("django.forms.IntegerField", {"min_value": 0, "max_value": 1000}),
    "expiry_days": ("django.forms.IntegerField", {"min_value": 1, "max_value": 90}),
    "peek_count": ("django.forms.IntegerField", {"min_value": 1, "max_value": 12}),
    "checks": ("pages.fields.ChecksField",),
    "hosts": ("pages.fields.HostsField",),
    "regions": ("pages.fields.RegionsField",),
    "slack_channels": ("pages.fields.SlackChannelsField",),
    "megabytes": ("django.forms.IntegerField", {"min_value": 1, "max_value": 20}),
    "rounds": ("django.forms.IntegerField", {"min_value": 1, "max_value": 10}),         # the ceiling is submissions.rules.MAX_ROUND_LIMIT (a test pins them)
    "pixels": ("django.forms.IntegerField", {"min_value": 500, "max_value": 10000}),
    "megapixels": ("django.forms.IntegerField", {"min_value": 1, "max_value": 40}),
    "leaderboard_size": ("django.forms.IntegerField", {"min_value": 1, "max_value": 500}),
    "tutorial_depth": ("django.forms.ChoiceField", {"choices": DEPTHS}),
}
