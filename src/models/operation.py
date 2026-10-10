from sqlalchemy import BigInteger, CHAR, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from models.base import Base
from models import Account


class Operation(Base):
    __tablename__ = "operation"

    DEPOSIT = "deposit"
    TRANSFER = "transfer"

    id = Column(Integer, primary_key=True)
    operation_key = Column(CHAR(36), nullable=False)
    type = Column(String(50), nullable=False)
    source_account_id = Column(Integer, ForeignKey(Account.id), nullable=True)
    destination_account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    amount = Column(BigInteger, nullable=False)
    fee_amount = Column(BigInteger, nullable=False)
    completed_at = Column(DateTime, nullable=False)

    __table_args__ = (UniqueConstraint("operation_key"),)

    source_account = relationship("Account", foreign_keys=[source_account_id], lazy="selectin")
    destination_account = relationship("Account", foreign_keys=[destination_account_id], lazy="selectin")
