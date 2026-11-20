from pydantic import BaseModel, Field


class User(BaseModel):
    user_id: str
    name: str = ""
    email: str = ""
    roles: list[str] = Field(default_factory=list)

    @property
    def best_role(self) -> str | None:
        """Return the highest explicitly assigned, recognized application role."""
        hierarchy = {"Admin": 2, "Contributor": 1, "Reader": 0}
        for role in sorted(self.roles, key=lambda r: hierarchy.get(r, -1), reverse=True):
            if role in hierarchy:
                return role.lower()
        return None


class UserInfo(BaseModel):
    user_id: str
    name: str
    email: str
    roles: list[str]
