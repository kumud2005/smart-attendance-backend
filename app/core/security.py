from datetime import datetime, timedelta, timezone
from hashlib import sha256

from jose import JWTError, jwt

from app.core.config import settings


ALGORITHM = "HS256"


def create_access_token(
    user_id: int,
    email: str,
    role_name: str,
) -> str:

    now = datetime.now(timezone.utc)

    expires_delta = timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role_name,
        "type": "access",
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict:

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if payload.get("type") != "access":
            raise ValueError("Invalid token type.")

        subject = payload.get("sub")

        if subject is None:
            raise ValueError(
                "Token does not contain a user ID."
            )

        return payload

    except JWTError as exc:
        raise ValueError(
            "Invalid or expired access token."
        ) from exc


# ============================================================
# PASSWORD RESET TOKEN
# ============================================================

def password_hash_fingerprint(
    password_hash: str,
) -> str:
    """
    Return a non-secret fingerprint of the current password hash.

    The reset token stores this fingerprint. After the password changes,
    the fingerprint changes too, so the same reset token becomes invalid.
    This gives the local-testing token one-time behavior without adding a
    database table.
    """

    return sha256(
        password_hash.encode("utf-8")
    ).hexdigest()


def create_password_reset_token(
    user_id: int,
    email: str,
    password_hash: str,
) -> str:
    """
    Create a short-lived password-reset JWT.

    This is NOT an access token and cannot authenticate API requests.
    """

    now = datetime.now(timezone.utc)

    expires_delta = timedelta(
        minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    )

    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "password_reset",
        "pwd": password_hash_fingerprint(
            password_hash
        ),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_password_reset_token(
    token: str,
) -> dict:
    """
    Decode and validate a password-reset JWT.
    """

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if payload.get("type") != "password_reset":
            raise ValueError(
                "Invalid password reset token type."
            )

        if payload.get("sub") is None:
            raise ValueError(
                "Password reset token has no user ID."
            )

        if not payload.get("email"):
            raise ValueError(
                "Password reset token has no email."
            )

        if not payload.get("pwd"):
            raise ValueError(
                "Password reset token is incomplete."
            )

        return payload

    except JWTError as exc:
        raise ValueError(
            "Invalid or expired password reset token."
        ) from exc
