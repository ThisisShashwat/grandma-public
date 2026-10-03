"""Where a person's place in a dialogue is kept. A store is any object with these two methods:

    load(request) -> State
    save(request, state)        may raise django.core.exceptions.ValidationError, which the page shows as an error

SessionStore keeps it in the server-side session (the browser only holds the session id). A caller that wants answers in
its own tables (onboarding writes the Profile) subclasses it or writes its own.
"""
from talk.dialogue import State


class SessionStore:
    def __init__(self, name):
        self.key = f"talk:{name}"

    def load(self, request):
        saved = request.session.get(self.key)
        return State(**saved) if saved else State()

    def save(self, request, state):
        request.session[self.key] = {"position": state.position, "answers": state.answers}
