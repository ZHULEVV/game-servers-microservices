"""Выдача JWT для демонстраций (в системе токен выдаёт Users Service: POST /api/users:login).
python scripts/make_token.py [user|provider|admin] [user_id]"""
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

role = sys.argv[1] if len(sys.argv) > 1 else "user"
user_id = UUID(sys.argv[2]) if len(sys.argv) > 2 else uuid4()
payload = {"sub": str(user_id), "role": role, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
print(jwt.encode(payload, "game-servers-jwt-secret-key-32-bytes", algorithm="HS256"))
