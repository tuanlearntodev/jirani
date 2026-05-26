from app.database import SessionLocal
from app.models.account import Account
from app.models.role import Role
from app.models.account_role import AccountRole
from app.schemas.auth_service import AuthService

db = SessionLocal()

print("Creating or getting roles...")
admin_role = db.query(Role).filter(Role.name == "admin").first()
if not admin_role:
    admin_role = Role(name="admin")
    db.add(admin_role)
    print("Created admin role")
else:
    print("Admin role already exists")

teacher_role = db.query(Role).filter(Role.name == "teacher").first()
if not teacher_role:
    teacher_role = Role(name="teacher")
    db.add(teacher_role)
    print("Created teacher role")
else:
    print("Teacher role already exists")

student_role = db.query(Role).filter(Role.name == "student").first()
if not student_role:
    student_role = Role(name="student")
    db.add(student_role)
    print("Created student role")
else:
    print("Student role already exists")

db.commit()
db.refresh(admin_role)
db.refresh(teacher_role)
db.refresh(student_role)

print("\nCreating or getting teacher...")
existing_teacher = db.query(Account).filter(Account.username == "teacher1").first()
if existing_teacher:
    print("Teacher already exists")
    teacher = existing_teacher
else:
    teacher = Account(
        username="teacher1",
        hashed_password=AuthService.get_password_hash("teacherpassword123"),
        first_name="Test",
        last_name="Teacher",
        is_active=True
    )
    db.add(teacher)
    db.commit()
    db.refresh(teacher)
    
    teacher_role_assignment = AccountRole(account_id=teacher.id, role_id=teacher_role.id)
    db.add(teacher_role_assignment)
    db.commit()
    print("Created teacher account")

print("\nCreating or getting student...")
existing_student = db.query(Account).filter(Account.username == "student1").first()
if existing_student:
    print("Student already exists")
    student = existing_student
else:
    student = Account(
        username="student1",
        hashed_password=AuthService.get_password_hash("studentpassword123"),
        first_name="Test",
        last_name="Student",
        is_active=True
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    
    student_role_assignment = AccountRole(account_id=student.id, role_id=student_role.id)
    db.add(student_role_assignment)
    db.commit()
    print("Created student account")

print("\nTest users ready!")
print("Teacher: teacher1 / teacherpassword123")
print("Student: student1 / studentpassword123")

db.close()