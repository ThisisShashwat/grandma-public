"""What Grandma says on each error page (pages/views.py). `face` and `alt` come from static/assets; `scene` is a core/layout.css scene;
`hint` is a pink note under the yellow one; `guides` adds a second link, to the guides. Nothing here ever comes from the request."""

ERRORS = {
    "400": {"status": 400, "code": "400", "label": "Bad request", "scene": "lilac",
            "face": "mood-2-sideeye.png", "alt": "Grandma giving the side-eye, a question mark over her head",
            "line": "I can't make head nor tail of that, dear. Did your message get muddled on the way?",
            "hint": "", "guides": False},
    "403": {"status": 403, "code": "403", "label": "Not for you", "scene": "sky",
            "face": "grandma-finger-wag.png", "alt": "Grandma wagging her finger",
            "line": "That drawer isn't yours, dear. Nobody goes in there without asking me first.",
            "hint": "Think Grandma got it wrong? Reload the page and try again.", "guides": False},
    "404": {"status": 404, "code": "404", "label": "Not found", "scene": "lilac",
            "face": "grandma-magnifier.png", "alt": "Grandma squinting through a magnifying glass",
            "line": "I looked in every drawer and that page isn't in any of them. Are you sure you wrote it down right, dear?",
            "hint": "", "guides": True},
    "405": {"status": 405, "code": "405", "label": "Wrong way in", "scene": "lilac",
            "face": "mood-3-eyeroll.png", "alt": "Grandma rolling her eyes and tossing a crumpled note",
            "line": "That's not how you knock, dear. Go back round to the front door and try it properly.",
            "hint": "", "guides": False},
    "500": {"status": 500, "code": "500", "label": "Grandma dropped it", "scene": "blush",
            "face": "grandma-shocked.png", "alt": "Grandma shocked, hands on her cheeks, a bitten cookie on the floor",
            "line": "Oh my goodness, I dropped the whole tray! Give me a minute to sweep up, dear.",
            "hint": "That one was on our side, not yours. Try again in a little while.", "guides": False},
    "csrf": {"status": 403, "code": "403", "label": "Stale slip", "scene": "sky",
             "face": "mood-0-asleep.png", "alt": "Grandma fast asleep with a snot bubble",
             "line": "You took so long I dozed off, dear, and that slip has gone stale.",
             "hint": "Reload the page and try again.", "guides": False},
}
