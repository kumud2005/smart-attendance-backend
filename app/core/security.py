from datetime import datetime, timedelta, timezone

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