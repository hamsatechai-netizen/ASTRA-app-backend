"""SMS delivery provider contract — lets `OTPService` depend on an abstraction, not a specific vendor."""

from abc import ABC, abstractmethod


class SMSProviderInterface(ABC):
    @abstractmethod
    async def send(self, phone_number: str, message: str) -> None:
        """Send `message` via SMS to `phone_number`. Raises `SMSDeliveryException` on failure."""
