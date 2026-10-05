"""/api/v1/auth — email + password sign-in, two-step verification, password changes.

Issues the same sessions (rotating refresh tokens, HttpOnly cookies, CSRF)
as Google sign-in. See ADR-0012.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response, status

from saige_api.api.deps import ResourcesDep, SessionDep
from saige_api.api.v1.auth import ERROR_RESPONSES, _client, _rate_limit, _start_session_response
from saige_api.audit import client_ip, record_audit, record_security_event
from saige_api.auth import passwords
from saige_api.auth.deps import CurrentUserDep
from saige_api.auth.password_accounts import (
    InvalidCredentialsError,
    PasswordAccountService,
)
from saige_api.auth.sessions import RevokeReason, SessionService
from saige_api.core.errors import AppError, ForbiddenError, NotFoundError
from saige_api.core.logging import get_logger
from saige_api.models import User
from saige_api.models.enums import AuditAction, SecuritySeverity
from saige_api.resources import Resources
from saige_api.schemas.auth import (
    ChangePasswordRequest,
    MfaLoginRequest,
    PasswordLoginRequest,
    PasswordLoginResponse,
    RecoveryCodesResponse,
    RegisterRequest,
    SecurityOverview,
    SessionResponse,
    StepUpRequest,
    TotpCodeRequest,
    TotpDisableRequest,
    TotpSetupResponse,
    UserProfile,
)
from saige_api.schemas.system import ErrorResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger("saige_api.auth.password")

RESPONSES: dict[int | str, dict[str, object]] = {
    **ERROR_RESPONSES,
    400: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def _require_enabled_and_same_origin(request: Request, resources: Resources) -> None:
    """Refuse cross-site form posts (login CSRF). Native clients send no Origin."""
    settings = resources.settings
    if not settings.password_login_enabled:
        raise NotFoundError("Not Found")
    origin = request.headers.get("origin")
    if origin is None:
        return
    allowed = {
        _origin(settings.web_public_url),
        *(_origin(o) for o in settings.cors_allowed_origins),
    }
    if origin.lower() not in allowed:
        raise ForbiddenError("Cross-site request refused")


async def _check_new_password(resources: Resources, password: str, *, email: str) -> None:
    passwords.check_policy(password, email=email)
    if resources.settings.password_breach_check and await passwords.is_breached(
        resources.external_http, password
    ):
        raise passwords.WeakPasswordError(
            "This password has appeared in a data breach. Please choose a different one."
        )


def _service(resources: Resources, db: SessionDep) -> PasswordAccountService:
    return PasswordAccountService(db, resources.kv, resources.cipher)


async def _signed_in(
    request: Request,
    response: Response,
    resources: Resources,
    db: SessionDep,
    user: User,
    method: str,
) -> SessionResponse:
    issued = await SessionService(db, resources.refresh_ttl).create(user.id, _client(request))
    record_audit(
        db,
        request,
        AuditAction.LOGIN,
        user_id=user.id,
        details={"method": method, "session_id": str(issued.session_id)},
    )
    profile = UserProfile.model_validate(user, from_attributes=True)
    await db.commit()
    expires = _start_session_response(response, resources, issued)
    return SessionResponse(user=profile, session_id=issued.session_id, access_expires_at=expires)


@router.post(
    "/register",
    summary="Create an account with email and password",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=RESPONSES,
)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    resources: ResourcesDep,
    db: SessionDep,
) -> SessionResponse:
    _require_enabled_and_same_origin(request, resources)
    await _rate_limit(resources, request, "register")
    await resources.rate_limiter.hit(
        "register_hourly",
        client_ip(request) or "unknown",
        limit=resources.settings.registrations_per_hour_per_ip,
        window_seconds=3600,
    )
    email = str(body.email)
    await _check_new_password(resources, body.password, email=email)
    user = await _service(resources, db).register(email, body.password, body.display_name)
    return await _signed_in(request, response, resources, db, user, "password_signup")


@router.post(
    "/login",
    summary="Sign in with email and password",
    response_model=PasswordLoginResponse,
    responses=RESPONSES,
)
async def password_login(
    body: PasswordLoginRequest,
    request: Request,
    response: Response,
    resources: ResourcesDep,
    db: SessionDep,
) -> PasswordLoginResponse:
    _require_enabled_and_same_origin(request, resources)
    await _rate_limit(resources, request, "password_login")
    try:
        result = await _service(resources, db).authenticate(str(body.email), body.password)
    except InvalidCredentialsError:
        record_audit(
            db, request, AuditAction.LOGIN, user_id=None, outcome="failure",
            details={"method": "password", "reason": "invalid_credentials"},
        )  # fmt: skip
        await db.commit()
        raise
    if result.mfa_ticket is not None:
        await db.commit()  # persists an Argon2 rehash, if any
        return PasswordLoginResponse(mfa_required=True, mfa_token=result.mfa_ticket)
    session = await _signed_in(request, response, resources, db, result.user, "password")
    return PasswordLoginResponse(session=session)


@router.post(
    "/login/mfa",
    summary="Finish signing in with an authenticator or recovery code",
    response_model=PasswordLoginResponse,
    responses=RESPONSES,
)
async def password_login_mfa(
    body: MfaLoginRequest,
    request: Request,
    response: Response,
    resources: ResourcesDep,
    db: SessionDep,
) -> PasswordLoginResponse:
    _require_enabled_and_same_origin(request, resources)
    await _rate_limit(resources, request, "password_login_mfa")
    try:
        user = await _service(resources, db).complete_mfa(body.mfa_token, body.code)
    except AppError:
        await db.rollback()
        raise
    session = await _signed_in(request, response, resources, db, user, "password_totp")
    return PasswordLoginResponse(session=session)


# -- account security (signed in) --------------------------------------------


@router.get(
    "/security",
    summary="Password and two-step verification status",
    response_model=SecurityOverview,
    responses=ERROR_RESPONSES,
)
async def security_overview(
    auth: CurrentUserDep, resources: ResourcesDep, db: SessionDep
) -> SecurityOverview:
    credential = await _service(resources, db).credential_for(auth.user_id)
    enabled = credential is not None and credential.totp_enabled_at is not None
    return SecurityOverview(
        has_password=credential is not None,
        email_verified=auth.user.email_verified_at is not None,
        password_changed_at=credential.password_changed_at if credential else None,
        totp_enabled=enabled,
        recovery_codes_remaining=len(credential.recovery_code_hashes)
        if credential and enabled
        else 0,
    )


@router.put(
    "/password",
    summary="Set or change your password (signs out your other devices)",
    status_code=204,
    responses=RESPONSES,
)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: SessionDep,
) -> Response:
    if not resources.settings.password_login_enabled:
        raise NotFoundError("Not Found")
    await _rate_limit(resources, request, "change_password")
    service = _service(resources, db)
    existing = await service.credential_for(auth.user_id)
    if existing is not None:
        await service.verify_password_for(auth.user_id, body.current_password or "")
    elif auth.user.email_verified_at is None:
        raise ForbiddenError("Verify your email with Google before adding a password.")
    await _check_new_password(resources, body.new_password, email=auth.user.email)
    await service.set_password(auth.user_id, body.new_password)
    ended = await SessionService(db, resources.refresh_ttl).revoke_all(
        auth.user_id, RevokeReason.PASSWORD_CHANGED, except_family=auth.session_id
    )
    record_security_event(
        db, request, "password_changed" if existing else "password_added", SecuritySeverity.INFO,
        "Account password was set.", user_id=auth.user_id,
        details={"other_sessions_ended": ended},
    )  # fmt: skip
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/mfa/totp/setup",
    summary="Start authenticator-app setup (returns the secret to scan)",
    response_model=TotpSetupResponse,
    responses=RESPONSES,
)
async def totp_setup(
    body: StepUpRequest,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: SessionDep,
) -> TotpSetupResponse:
    await _rate_limit(resources, request, "totp")
    service = _service(resources, db)
    credential = await service.verify_password_for(auth.user_id, body.password)
    secret, uri = await service.begin_totp_setup(credential, auth.user.email)
    await db.commit()
    return TotpSetupResponse(secret=secret, otpauth_uri=uri)


@router.post(
    "/mfa/totp/enable",
    summary="Confirm a code from the app to turn on two-step verification",
    response_model=RecoveryCodesResponse,
    responses=RESPONSES,
)
async def totp_enable(
    body: TotpCodeRequest,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: SessionDep,
) -> RecoveryCodesResponse:
    await _rate_limit(resources, request, "totp")
    codes = await _service(resources, db).enable_totp(auth.user_id, body.code)
    ended = await SessionService(db, resources.refresh_ttl).revoke_all(
        auth.user_id, RevokeReason.ACCOUNT_SECURED, except_family=auth.session_id
    )
    record_security_event(
        db, request, "totp_enabled", SecuritySeverity.INFO,
        "Two-step verification was turned on.", user_id=auth.user_id,
        details={"other_sessions_ended": ended},
    )  # fmt: skip
    await db.commit()
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post(
    "/mfa/totp/disable",
    summary="Turn off two-step verification (needs password and a code)",
    status_code=204,
    responses=RESPONSES,
)
async def totp_disable(
    body: TotpDisableRequest,
    request: Request,
    auth: CurrentUserDep,
    resources: ResourcesDep,
    db: SessionDep,
) -> Response:
    await _rate_limit(resources, request, "totp")
    service = _service(resources, db)
    credential = await service.verify_password_for(auth.user_id, body.password)
    await service.disable_totp(credential, body.code)
    record_security_event(
        db, request, "totp_disabled", SecuritySeverity.MEDIUM,
        "Two-step verification was turned off.", user_id=auth.user_id,
    )  # fmt: skip
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
