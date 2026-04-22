from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    user_id: str
    name: str = ""
    email: str = ""
    roles: list[str] = []

    @property
    def best_role(self) -> str:
        """Return the highest role from AAD app roles."""
        hierarchy = {"Admin": 2, "Contributor": 1, "Reader": 0}
        for role in sorted(self.roles, key=lambda r: hierarchy.get(r, -1), reverse=True):
            if role in hierarchy:
                return role.lower()
        return "reader"


class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str
    roles: list[str]
