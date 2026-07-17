"""
Authentication module (phone + OTP based, for the Flutter mobile client).

Phase 1 status: infrastructure only. This package defines the auth
module's full shape — schemas, security utilities, exceptions, dependency
signatures, repository/service interfaces, and a router with two
placeholder endpoints — with no OTP generation, verification, token
issuance, or persistence logic implemented yet. Every entry point that
would require real business logic raises `NotImplementedError` or returns
HTTP 501, clearly marked for Phase 2.

Submodules:
    constants/    Fixed values (OTP length/expiry, JWT algorithm/expiry, regex patterns).
    schemas/      Request/response DTOs (SendOTPRequest, VerifyOTPRequest, AuthResponse).
    validators/   Reusable Pydantic field validators (phone number / OTP code format).
    security/     JWT + secure-random + OTP + expiry infrastructure (no business logic).
    exceptions/   Auth-specific AppException subclasses.
    dependencies/ FastAPI DI providers (current athlete, authorization, ...) — stubs.
    repositories/ Abstract repository contract for future persistence.
    services/     Abstract service contracts (AuthService, OTPService, TokenService).
    routers/      The versioned auth router, mounted under `/api/v2/auth`.
"""
