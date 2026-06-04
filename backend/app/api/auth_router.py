import random
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import TokenResponse, LoginRequest, ResetPasswordRequest, ChangePasswordRequest
from app.services.auth_service import AuthService
from app.models.account import Account
from app.dependencies.auth import get_current_user, RoleChecker

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(db, login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = AuthService.create_token_for_user(user)
    return TokenResponse(access_token=access_token, token_type="bearer", username=user.username, roles=user.role)


# auth_router.py
@router.post("/forgot-password/verify-code")
async def verify_recovery_code(
    username: str,
    otp: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    user = AuthService.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.recovery_code_hash:
        raise HTTPException(status_code=400, detail="No recovery code set for this account")
    if not AuthService.verify_password(otp, user.recovery_code_hash):
        raise HTTPException(status_code=400, detail="Invalid recovery code")

    user.hashed_password = AuthService.get_password_hash(new_password)
    db.commit()
    db.refresh(user)

    if not AuthService.verify_password(new_password, user.hashed_password):
        raise HTTPException(status_code=500, detail="Password update failed — try again")

    return {"message": "Password reset successfully"}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(RoleChecker(["admin"]))
):
    try:
        updated = AuthService.reset_password(db, reset_data.username, reset_data.new_password)
        return {"message": f"Password reset for {updated.username}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_own_password(
    change_data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: Account = Depends(RoleChecker(["admin"]))
):
    if not AuthService.verify_password(change_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    current_user.hashed_password = AuthService.get_password_hash(change_data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}