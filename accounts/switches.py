"""Admin switches that also need values in the environment. A switch that is on while its environment is empty does nothing,
silently (onboarding keeps saying "not ready"), so staff are told on the settings page which values are missing."""
from django.conf import settings

NEEDS = (      # (the admin switch, what it is, the settings names that must be non empty)
    ("HCA_LOGIN", "Sign in with Hack Club", ("HCA_CLIENT_ID", "HCA_CLIENT_SECRET")),
    ("HACKATIME_ENABLED", "Hackatime", ("HACKATIME_CLIENT_ID", "HACKATIME_CLIENT_SECRET", "HACKATIME_TOKEN_KEYS")),
    ("SLACK_NOTIFICATIONS", "Slack notices", ("SLACK_BOT_TOKEN",)),
    ("ARI_ENABLED", "Ari reviews", ("ARI_PROGRAM_ID", "ARI_INGEST_SECRET", "ARI_OUTBOUND_SECRET")),
)


def problems(cfg):
    """One sentence for every switch that is on but whose environment values are missing. `cfg` is pages.live.live()."""
    found = []
    for switch, what, names in NEEDS:
        missing = [name for name in names if not getattr(settings, name, None)]
        if getattr(cfg, switch) and missing:
            found.append(f"{what} is switched on ({switch}) but nothing happens: {', '.join(missing)} must be set in the server's environment (never here), "
                         "then the site restarted. Until then the site behaves as if it were off.")
    return found
