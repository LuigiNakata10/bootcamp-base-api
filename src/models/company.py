from sqlalchemy import CHAR, Column, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.base import Base


class Company(Base):
    __tablename__ = "company"

    id = Column(Integer, primary_key=True)
    company_key = Column(CHAR(36), nullable=False)
    legal_name = Column(String(255), nullable=False)
    cnpj = Column(CHAR(14), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_key"),
        UniqueConstraint("cnpj"),
    )

    account = relationship("Account", back_populates="company", uselist=False, lazy="selectin")
