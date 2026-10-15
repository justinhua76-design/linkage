from fastapi import Request


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)
