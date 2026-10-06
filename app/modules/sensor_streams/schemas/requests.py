"""
Request DTOs for the ECG/ACC batch-ingestion flow.

Field names follow the same camelCase-alias convention as
`app.modules.heart_rate.schemas.requests` (`sessionId`, `recordedAt`, ...);
`BaseSchema.populate_by_name` means the snake_case names are accepted too.

Unlike `HrSampleBatchRequest`, `session_id` is set once per batch rather
than per sample: a batch is one upload from one live session, so there is
exactly one ownership check per request.

`batch_id` (`batchId`) is a client-generated UUID identifying one logical
upload batch. It is required, and it is the idempotency key: a client that
retries a batch (e.g. after a timeout) must resend the SAME `batchId`, and
the backend then stores that batch's samples at most once and answers the
retry with the original accepted count. A new batch must use a new UUID.
ECG and ACC batches are independent — the same UUID on both endpoints is
two different batches.

Bounds — deliberately permissive "obviously invalid" guards, not
physiological limits:

- ECG: the Polar H10 streams ECG in microvolts (µV) at 130 Hz (Polar BLE SDK
  `EcgSample.voltage` / `PolarEcgData`). Real ECG amplitudes are a few
  millivolts; ±100 mV (±100,000 µV) only rejects values no ECG electrode
  could produce, well inside the `integer` column.
- ACC: the Polar H10 streams per-axis acceleration in milli-g (mG,
  including gravity), with a configurable range of 2G, 4G or 8G (Polar
  SDK `documentation/products/PolarH10.md`). ±16,000 mG is twice the
  largest supported range, so no legitimate H10 sample can be rejected
  whichever range a later stage chooses.

Values and timestamps are validated strictly: a sample value must be a JSON
integer (no floats, strings or booleans), and `recordedAt` must be an ISO
8601 string carrying an explicit UTC offset — a naive timestamp is
rejected rather than silently interpreted in the server's local timezone.
"""

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, Field, StrictInt

from app.schemas.base import BaseSchema

MAX_BATCH_SIZE = 5000

_MAX_ABS_ECG_UV = 100_000
_MAX_ABS_ACC_MG = 16_000

_RecordedAt = Annotated[
    AwareDatetime,
    Field(
        alias="recordedAt",
        strict=True,
        description="When this sample was captured, as an ISO 8601 timestamp with a UTC offset.",
    ),
]
_AccAxis = Annotated[StrictInt, Field(ge=-_MAX_ABS_ACC_MG, le=_MAX_ABS_ACC_MG)]


class EcgSampleItem(BaseSchema):
    """One ECG sample as streamed off the Polar H10."""

    recorded_at: _RecordedAt
    ecg_value: StrictInt = Field(
        ...,
        alias="ecgValue",
        ge=-_MAX_ABS_ECG_UV,
        le=_MAX_ABS_ECG_UV,
        description="ECG voltage in microvolts (µV).",
        examples=[-120],
    )


class AccSampleItem(BaseSchema):
    """One accelerometer sample as streamed off the Polar H10."""

    recorded_at: _RecordedAt
    acc_x: _AccAxis = Field(..., alias="accX", description="X-axis acceleration in milli-g.", examples=[12])
    acc_y: _AccAxis = Field(..., alias="accY", description="Y-axis acceleration in milli-g.", examples=[-5])
    acc_z: _AccAxis = Field(..., alias="accZ", description="Z-axis acceleration in milli-g.", examples=[1001])


class EcgSampleBatchRequest(BaseSchema):
    """Request body for `POST /api/v2/ecg/samples` — one batch of ECG samples from one session."""

    session_id: UUID = Field(..., alias="sessionId", description="The live session these samples belong to.")
    batch_id: UUID = Field(
        ...,
        alias="batchId",
        description=(
            "Client-generated UUID for this batch — the idempotency key. Resend the same value "
            "when retrying the same batch; use a new one for every new batch."
        ),
    )
    samples: list[EcgSampleItem] = Field(
        ..., min_length=1, max_length=MAX_BATCH_SIZE, description="ECG samples to store, in any order."
    )


class AccSampleBatchRequest(BaseSchema):
    """Request body for `POST /api/v2/acc/samples` — one batch of accelerometer samples from one session."""

    session_id: UUID = Field(..., alias="sessionId", description="The live session these samples belong to.")
    batch_id: UUID = Field(
        ...,
        alias="batchId",
        description=(
            "Client-generated UUID for this batch — the idempotency key. Resend the same value "
            "when retrying the same batch; use a new one for every new batch."
        ),
    )
    samples: list[AccSampleItem] = Field(
        ...,
        min_length=1,
        max_length=MAX_BATCH_SIZE,
        description="Accelerometer samples to store, in any order.",
    )
