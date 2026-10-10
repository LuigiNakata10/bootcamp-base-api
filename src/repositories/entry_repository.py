from datetime import datetime

from sqlalchemy import func

from database import Context
from models import Entry, Operation


class EntryRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def list_by_account(self, account_id: int, limit: int, offset: int) -> list:
        """Mais novo primeiro. O `Entry.id` desempata lançamentos da mesma operação."""
        return (
            self.session.query(Entry)
            .join(Operation, Entry.operation_id == Operation.id)
            .filter(Entry.account_id == account_id)
            .order_by(Operation.completed_at.desc(), Entry.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def list_fees(self, start: datetime, end: datetime, limit: int, offset: int) -> list:
        """Lançamentos de tarifa com `start <= completed_at < end`, mais novo primeiro."""
        return (
            self._fees_between(self.session.query(Entry), start, end)
            .order_by(Operation.completed_at.desc(), Entry.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def sum_fees(self, start: datetime, end: datetime) -> int:
        total = self._fees_between(self.session.query(func.coalesce(func.sum(Entry.amount), 0)), start, end).scalar()
        return int(total)

    def _fees_between(self, query, start: datetime, end: datetime):
        return (
            query.join(Operation, Entry.operation_id == Operation.id)
            .filter(Entry.type == Entry.FEE)
            .filter(Operation.completed_at >= start)
            .filter(Operation.completed_at < end)
        )
