# ADR-0012: Email + password sign-in with optional TOTP

**Status:** Accepted · **Date:** 2026-10-05

## Context

Google sign-in (ADR-0009) is the only way in so far. Some users want an account that doesn't depend on Google. Passwords add risks that Google sign-in avoids: credential stuffing, brute force, leaked databases, and account pre-hijacking.

## Decision

**Storage:**
- A `password_credentials` table holds at most one row per user.
- Passwords are hashed with **Argon2id** (m = 19 MiB, t = 2, p = 1; OWASP baseline). Hashes are upgraded on sign-in if the parameters change.
- Input is NFKC-normalised.

**Policy (NIST SP 800-63B):**
- Length is 12–128 characters, with no composition rules.
- Trivial, repetitive and email-derived passwords are rejected.
- Passwords seen in breaches are rejected via the Have I Been Pwned range API. This uses k-anonymity: only 5 hex characters of the SHA-1 leave the server, with padding requested. The check fails open on outage, and `PASSWORD_BREACH_CHECK=false` disables it.

**Sign-in (`POST /auth/login`):**
- Wrong password and unknown email return the same 401 `invalid_credentials` message.
- Unknown emails are verified against a dummy Argon2 hash, so timing doesn't reveal which accounts exist.
- Limits:
  - **Per IP:** the existing auth rate limit applies.
  - **Per account:** 5 failures lock the address for 15 minutes, even against the correct password.
  - **Registration:** additionally limited per IP per hour.
- Requests whose `Origin` isn't the web app are refused (login CSRF). Native clients send no Origin.
- Success issues the same rotating-refresh session and cookies as Google sign-in.

**Two-step verification (TOTP, RFC 6238):**
- Opt-in from Settings.
- Setup:
  - Confirming the password is required (step-up).
  - The secret is encrypted with the application key (AES-GCM, row-bound AAD).
  - The user confirms a code before it takes effect.
  - Enabling ends all other sessions.
- When TOTP is on, `/auth/login` returns a 5-minute, single-use `mfa_token` instead of a session. `/auth/login/mfa` then accepts:
  - an authenticator code, with ±1 step drift and replay refused;
  - or one of ten single-use recovery codes, stored as SHA-256 hashes.
- Each ticket allows 5 attempts. Turning TOTP off needs both the password and a code.

**Account changes:**
- Changing a password requires the current one and ends every other session.
- A Google user can add a password only because Google verified their email (`users.email_verified_at`).

**Pre-hijacking defence:**
- Password sign-up never marks an email verified.
- When Google later proves ownership of an address held by an unverified account, that account's password is deleted and its sessions are ended. A squatter therefore never shares the real owner's vault.

**Errors:**
- Wrong passwords or codes during signed-in changes return **400**, not 401, so the client doesn't mistake them for an expired session.
- Signed-in account endpoints under `/auth/` refresh the session like any other call.

## Consequences

- **No email-based password reset.** There's no email service yet, so registration doesn't prove address ownership and can reveal that an address is registered (409). A user who forgets their password can sign in with Google using the same address, then set a new one. Email verification and reset are the follow-up once a mail provider is chosen.
- **Lockout counters and MFA tickets** live in Redis, or in-process without it (single instance only, see `kv.py`). They reset on restart.
- **Google sign-in doesn't ask for the TOTP code.** It relies on the Google account's own security (including Google's 2-Step Verification).
