import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import DATA_DIR
from app.database import get_db
from app.repositories import AuthRepo
from app.services import AuthService

router = APIRouter(prefix="/setup", tags=["setup"])


def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepo(db))


CREDENTIALS_FILE = Path(DATA_DIR) / ".credentials"
REVEALED_FLAG = Path(DATA_DIR) / ".credentials_revealed"


@router.get("", status_code=status.HTTP_200_OK)
def setup_page(auth_service: AuthService = Depends(get_auth_service)) -> dict[str, str]:

    if REVEALED_FLAG.exists():
        raise HTTPException(
            status_code=403, detail="admin credentials have already been revealed."
        )
    if not CREDENTIALS_FILE.exists():
        password = secrets.token_urlsafe(8)
        credentials = {"username": "admin", "password": password}
        try:
            auth_service.setup_admin_account(credentials["password"])
        except ValueError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
    else:
        credentials = json.loads(CREDENTIALS_FILE.read_text())
        password = credentials["password"]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CREDENTIALS_FILE.write_text(json.dumps(credentials))
    REVEALED_FLAG.touch()

    return {
        "message": (f"Admin credentials - Username: {credentials['username']}, "
                    f"Password: {password}. "
                    "Please change the password after first login.")
    }
