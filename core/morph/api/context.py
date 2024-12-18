import contextvars

request_context: contextvars.ContextVar = contextvars.ContextVar(
    "request_context", default={}
)
