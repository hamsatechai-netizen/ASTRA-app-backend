"""
ASGI middleware stack.

Order matters (outermost added last, runs first): security headers →
access logging → request-context/correlation ID. Registered centrally in
`main.py` so the stack is explicit and easy to audit.
"""
