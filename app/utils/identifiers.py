"""UUID helpers. Every entity in the system is identified by a UUID4, never an auto-increment int."""

import uuid


def generate_uuid() -> uuid.UUID:
    return uuid.uuid4()
