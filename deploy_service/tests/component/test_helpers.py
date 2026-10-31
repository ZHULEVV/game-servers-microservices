from uuid import UUID

from app.security import create_token


def user_headers(user_id: UUID, role: str = "user") -> dict:
    return {"Authorization": f"Bearer {create_token(user_id, role)}"}
