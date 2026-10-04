"""Plain-word durations in hours and minutes for Grandma's notes and the Hackatime picker.
Pure Python, no Django import."""


def text(seconds):
    """Format seconds into plain words (hours and minutes only, minutes rounded down).
    Negative or non-integer input is treated as 0."""
    if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
        return "0 minutes"

    total_minutes = seconds // 60
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours == 0 and minutes == 0:
        return "0 minutes"

    parts = []
    if hours > 0:
        parts.append(f"{hours} hour" if hours == 1 else f"{hours} hours")
    if minutes > 0:
        parts.append(f"{minutes} minute" if minutes == 1 else f"{minutes} minutes")

    return " ".join(parts) if parts else "0 minutes"


def of_hours(hours):
    """Format a Decimal, int or float number of hours into plain words. None or negative gives '0 minutes'."""
    if hours is None or isinstance(hours, bool):
        return "0 minutes"
    try:
        if hours <= 0:
            return "0 minutes"
        return text(int(hours * 3600))
    except (TypeError, ValueError):
        return "0 minutes"
