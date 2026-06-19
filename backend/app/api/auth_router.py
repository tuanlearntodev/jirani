import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.repositories import AuthRepo
from app.schemas import TokenResponse, LoginRequest, ResetPasswordRequest, ChangePasswordRequest
from app.schemas import AccountCreateRequest
from app.schemas.account_schema import BulkCreateRequest, BulkCreateResponse
from app.services import AuthService
from app.models import Account, RoleEnum
from app.dependencies.auth import get_current_user, RoleChecker

router = APIRouter(prefix="/auth", tags=["authentication"])

def get_auth_service(db: Session = Depends(get_db))-> AuthService:
    return AuthService(AuthRepo(db))

@router.post("/token", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(login_data: LoginRequest, 
                auth_service: AuthService = Depends(get_auth_service)):
    user = auth_service.authenticate_user(login_data.username, login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = auth_service.create_token_for_user(user)
    return TokenResponse(access_token=access_token, token_type="bearer", username=user.username, role=user.role)


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset_data: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Account = Depends(RoleChecker([RoleEnum.teacher, RoleEnum.admin]))
):
    try:
        updated, password = auth_service.reset_password(reset_data.account_id)
        return {"message": f"Password reset for {updated.username}", "new_password": password}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    change_data: ChangePasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Account = Depends(RoleChecker([RoleEnum.student, RoleEnum.teacher, RoleEnum.admin]))
):
    if not auth_service.verify_password(change_data.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
    auth_service.change_password(current_user.username, change_data.new_password)
    return {"message": "Password changed successfully"}

@router.post("/user", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: AccountCreateRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    try:
        new_user = auth_service.create_user(user_data)
        return {"message": "User created successfully", "user": new_user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

@router.post("/users/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_create_users(
    bulk_data: BulkCreateRequest,
    auth_service: AuthService = Depends(get_auth_service)
)-> BulkCreateResponse:
    try:
        response = auth_service.bulk_create_users(bulk_data)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))