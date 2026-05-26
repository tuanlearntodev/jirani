from app.database import Base
from sqlalchemy import Column, Integer, String, CheckConstraint
from sqlalchemy.orm import relationship

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    accounts = relationship("Account", secondary="account_roles", back_populates="roles")

    __table_args__ = (
        CheckConstraint(
            "name IN ('admin', 'teacher', 'student')",
            name = "checking_valid_role"
        ),
    )  