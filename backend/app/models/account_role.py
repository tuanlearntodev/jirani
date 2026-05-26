from app.database import Base
from sqlalchemy import Column, Integer, ForeignKey,UniqueConstraint, Boolean

class AccountRole(Base):
    __tablename__ = "account_roles"
    
    id = Column(Integer, primary_key=True) 
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (UniqueConstraint('account_id', 'role_id'),)
