import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

if not JWT_SECRET:
    raise RuntimeError(
        "JWT_SECRET is missing. Add a generated secret key to backend/.env."
    )

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: str, role: str) -> str:
    expiry_time = datetime.now(timezone.utc) + timedelta(
        hours=ACCESS_TOKEN_EXPIRE_HOURS
    )

    payload = {
        "sub": user_id,
        "role": role,
        "exp": expiry_time,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except InvalidTokenError as error:
        raise ValueError("Invalid or expired access token.") from error