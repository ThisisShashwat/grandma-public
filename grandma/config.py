"""Site-wide settings. Edit these instead of the templates."""

SITE = {
    "name": "Help Grandma Out",
    "description": "[TODO: one sentence about the program]",
    "og_description": "[TODO: same sentence]",
    "og_image": "[TODO: absolute URL of a 1200 by 630 image]",
    "theme_color": "#c8a2d8",
}

LAUNCH = "2026-10-05T12:00:00Z"   # TODO: real launch moment (ISO, with timezone)
FREE_ASKS = 3

# Empty string = placeholder "#". Fill these in and every page picks them up.
LINKS = {
    "signup": "",     # Fillout form or Submit link
    "slack": "",
    "repo": "",
    "board": "",      # where complaints (new demands) get sent
    "rules": "",      # fine print / HQ policies
    "contact": "",    # e.g. "mailto:you@example.com"
}

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
