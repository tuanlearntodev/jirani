import enum


class RoleEnum(str, enum.Enum):
    admin = "admin"
    student = "student"
    teacher = "teacher"
