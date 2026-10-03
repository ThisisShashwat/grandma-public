from accounts.models import Profile


def profile_of(user):
    """The user's Profile, made empty on first use."""
    return Profile.objects.get_or_create(user=user)[0]
