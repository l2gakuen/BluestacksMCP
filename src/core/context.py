import contextvars

request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
