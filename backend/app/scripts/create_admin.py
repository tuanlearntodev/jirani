# app/scripts/create_admin.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from app.models.account import Account
from app.models.role import Role
from app.models.account_role import AccountRole
from app.schemas.auth_service import AuthService

db = SessionLocal()

# Check if admin role exists, if not create it
admin_role = db.query(Role).filter(Role.name == "admin").first()
if not admin_role:
    admin_role = Role(name="admin")
    db.add(admin_role)
    db.commit()
    db.refresh(admin_role)
    print("Created admin role")
else:
    print("Admin role already exists")

# Check if admin user exists, if not create it
admin_user = db.query(Account).filter(Account.username == "admin").first()
if not admin_user:
    hashed_password = AuthService.get_password_hash("admin123")
    admin_user = Account(
        username="admin",
        hashed_password=hashed_password,
        first_name="Admin",
        last_name="User",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    print("Created admin user: username='admin', password='admin123'")
else:
    print("Admin user already exists")

# Check if admin has admin role, if not assign it
has_admin_role = db.query(AccountRole).filter(
    AccountRole.account_id == admin_user.id,
    AccountRole.role_id == admin_role.id
).first()

if not has_admin_role:
    account_role = AccountRole(
        account_id=admin_user.id,
        role_id=admin_role.id,
        is_active=True
    )
    db.add(account_role)
    db.commit()
    print("Assigned admin role to admin user")
else:
    print("Admin user already has admin role")

print("Setup complete! You can now login with:")
print("   Username: admin")
print("   Password: admin123")
db.close()