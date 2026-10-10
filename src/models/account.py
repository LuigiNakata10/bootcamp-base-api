from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from models.base import Base
from models import Company


class Account(Base):
    __tablename__ = "account"

    id = Column(Integer, primary_key=True)
    account_key = Column(CHAR(36), nullable=False)
    company_id = Column(Integer, ForeignKey(Company.id), nullable=False)
    balance = Column(BigInteger, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("account_key"),
        UniqueConstraint("company_id"),
    )

    company = relationship("Company", back_populates="account", lazy="selectin")
