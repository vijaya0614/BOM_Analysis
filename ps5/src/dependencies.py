from fastapi import Depends, HTTPException, status
from src.auth import get_current_user, User

def get_user_dependency(user: User = Depends(get_current_user)):
    """Dependency that ensures a valid authenticated user is present."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")
    return user

# Placeholder for role‑based access – extend as needed
def require_role(role: str):
    def role_dependency(user: User = Depends(get_user_dependency)):
        if role not in user.roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return role_dependency
