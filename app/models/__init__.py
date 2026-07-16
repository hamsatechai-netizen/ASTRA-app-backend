"""
ORM models (persistence layer).

Empty in this phase by design — no domain tables exist yet. Future models
(User, Athlete, OTP, Profile, ...) will inherit `Base` from
`app.database.base` plus the `UUIDMixin` / `TimestampMixin` defined in
`base.py` so every table gets a UUID primary key and UTC audit timestamps
for free, without repeating that logic per model.
"""
