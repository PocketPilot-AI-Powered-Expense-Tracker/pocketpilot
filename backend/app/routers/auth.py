from fastapi import APIRouter, Depends, Request, Response, status

from app.core.deps import get_current_user
from app.core.rate_limit import check_login_rate
from app.db.mongo import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db=Depends(get_db)):
    return await auth_service.register(db, data)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, request: Request, db=Depends(get_db)):
    check_login_rate(data.email, request.client.host if request.client else "unknown")
    return await auth_service.login(db, data)


@router.get("/me", response_model=UserOut)
async def me(user=Depends(get_current_user), db=Depends(get_db)):
    return await auth_service.user_out(db, user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT,
               summary="Permanently delete my account and all my data")
async def delete_me(user=Depends(get_current_user), db=Depends(get_db)):
    await auth_service.delete_account(db, user["_id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Logout: JWTs are stateless, so the client simply discards its token.
# Tokens expire after ACCESS_TOKEN_EXPIRE_MINUTES.
