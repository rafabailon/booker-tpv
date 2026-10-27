"""Authentication and authorization dependencies."""

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the signed session to an active database user."""
    raw_user_id = request.session.get("user_id")
    if not raw_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inicia sesión para continuar")
    try:
        user_id = UUID(raw_user_id)
    except (TypeError, ValueError):
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="La sesión ya no está activa")
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Build a dependency restricting an endpoint to selected roles."""
    def role_dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para esta operación")
        return user

    return role_dependency


staff_user = require_roles(UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.CASHIER)
catalog_manager = require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)
supervisor = require_roles(UserRole.ADMIN, UserRole.SUPERVISOR)
administrator = require_roles(UserRole.ADMIN)