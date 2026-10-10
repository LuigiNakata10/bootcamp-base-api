from sqlalchemy import BigInteger, CHAR, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from models.base import Base
from models import Account, Operation


class Entry(Base):
    __tablename__ = "entry"

    DEPOSIT = "deposit"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    FEE = "fee"

    id = Column(Integer, primary_key=True)
    entry_key = Column(CHAR(36), nullable=False)
    operation_id = Column(Integer, ForeignKey(Operation.id), nullable=False)
    account_id = Column(Integer, ForeignKey(Account.id), nullable=False)
    type = Column(String(50), nullable=False)
    amount = Column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("entry_key"),
        UniqueConstraint("operation_id", "account_id", "type"),
    )

    operation = relationship("Operation", lazy="selectin")
    account = relationship("Account", lazy="selectin")
