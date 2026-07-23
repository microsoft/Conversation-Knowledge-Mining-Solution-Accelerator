from pydantic import BaseModel


class User(BaseModel):
    user_id: str
    name: str = ""
    email: str = ""
    roles: list[str] = []

    @property
    def best_role(self) -> str:
        """Return the highest role from AAD app roles.
        Falls back to 'contributor' when no roles are assigned (authenticated users get full access)."""
        hierarchy = {"Admin": 2, "Contributor": 1, "Reader": 0}
        for role in sorted(self.roles, key=lambda r: hierarchy.get(r, -1), reverse=True):
            if role in hierarchy:
                return role.lower()
        return "contributor"


class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str
    roles: list[str]
