"""Site-wide settings. Edit these instead of the templates."""

SITE = {
    "name": "Help Grandma Out",
    "description": "[TODO: one sentence about the program]",
    "og_description": "[TODO: same sentence]",
    "og_image": "[TODO: absolute URL of a 1200 by 630 image]",
    "theme_color": "#c8a2d8",
}

# Launch time, free asks and the program links are admin-editable (Django admin, "Constance"): program/runtime.py.

# Standard Hack Club footer links: (key, label, url), one row per line.
FOOTER = [
    [("philosophy", "Philosophy", "https://hackclub.com/philosophy"),
     ("team", "Our Team", "https://hackclub.com/team"),
     ("jobs", "Jobs", "https://hackclub.com/jobs"),
     ("press", "Press", "https://hackclub.com/press")],
    [("donate", "Donate", "https://hackclub.com/philanthropy"),
     ("events", "Events", "https://events.hackclub.com/"),
     ("jams", "Jams", "https://jams.hackclub.com/"),
     ("toolbox", "Toolbox", "https://toolbox.hackclub.com/")],
    [("conduct", "Code of Conduct", "https://hackclub.com/conduct/"),
     ("terms", "Terms & Conditions", "https://hackclub.com/privacy-and-terms#hack-club-standard-terms-and-conditions"),
     ("privacy", "Privacy Notice", "https://hackclub.com/privacy-and-terms#hack-club-privacy-notice"),
     ("bounty", "Fulfillment Bounty", "https://forms.hackclub.com/bounty")],
]
