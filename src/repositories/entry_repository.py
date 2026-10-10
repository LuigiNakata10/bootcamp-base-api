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
