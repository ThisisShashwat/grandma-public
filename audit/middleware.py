import uuid
from contextvars import ContextVar

current = ContextVar("current", default="")


class RequestId:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = current.set(uuid.uuid4().hex)
        try:
            return self.get_response(request)
        finally:
            current.reset(token)
