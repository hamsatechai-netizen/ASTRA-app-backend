"""
Security infrastructure.

Distinct from `app/middleware`: this package holds security *policy*
objects (the rate limiter instance, and, in later phases, password
hashing/JWT signing utilities) that middleware and dependencies wire up,
rather than HTTP plumbing itself.
"""
