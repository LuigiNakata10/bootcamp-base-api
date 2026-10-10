from datetime import datetime, timezone
from uuid import uuid4

from database import Context
from models import Account, Entry, Operation


def utc_now() -> datetime:
    """O instante atual em UTC, sem fuso (a coluna é TIMESTAMP e só guarda UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OperationRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_key(self, operation_key: str) -> Operation:
        return self.session.query(Operation).filter(Operation.operation_key == operation_key).first()

    def reserve(
        self,
        operation_key: str,
        operation_type: str,
        source_account: Account,
        destination_account: Account,
        amount: int,
        fee_amount: int,
    ) -> Operation:
        """Reserva a chave: o INSERT sob UNIQUE(operation_key), dentro da transação do dinheiro.

        O `flush` leva o INSERT ao banco agora. Se outra transação já
        reservou a mesma chave, este INSERT espera no índice até ela
        confirmar (e estoura o UNIQUE) ou desfazer (e segue).
        """
        operation = Operation()
        operation.operation_key = operation_key
        operation.type = operation_type
        operation.source_account = source_account
        operation.destination_account = destination_account
        operation.amount = amount
        operation.fee_amount = fee_amount
        # O instante é o da reserva e é gravado uma única vez: a linha nunca é atualizada.
        # Só vira visível quando a transação confirma, e `operation` sem COMMIT não existe.
        operation.completed_at = utc_now()

        self.session.add(operation)
        self.session.flush()
        return operation

    def add_entry(self, operation: Operation, account: Account, entry_type: str, amount: int) -> Entry:
        entry = Entry()
        entry.entry_key = str(uuid4())
        entry.operation = operation
        entry.account = account
        entry.type = entry_type
        entry.amount = amount

        self.session.add(entry)
        return entry
