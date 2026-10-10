from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import OperationDTO
from errors import (
    AmountLimitExceeded,
    InsufficientBalance,
    InvalidAmount,
    NotFoundAccount,
    NotFoundOperation,
    OperationKeyConflict,
    QIException,
    SameAccountTransfer,
)
from models import Entry, Operation
from repositories import AccountRepository, OperationRepository
from utils.identifiers import parse_key

BIGINT_MAX = 2**63 - 1
TRANSFER_FEE = 100
MAX_ATTEMPTS = 3


class OperationController(BaseController):
    """Depósito e transferência: a mesma receita, com uma conta a mais na transferência.

    O roteiro de cada movimentação, em ordem (o commit é a última linha):
      1. recusa o que dá para recusar sem consultar o banco;
      2. procura a operation_key — repetida, devolve a resposta original (200) ou o conflito (409);
      3. confere que as contas existem (sem travar);
      4. reserva a chave com INSERT sob UNIQUE, na mesma transação do dinheiro;
      5. trava as contas em ordem crescente de account_key e só então lê os saldos;
      6. confere saldo e limite, move o dinheiro, grava os lançamentos;
      7. COMMIT — débito, crédito, tarifa e lançamentos viram uma coisa só.
    Qualquer recusa depois do passo 4 desfaz tudo, inclusive a reserva da chave.
    """

    def __init__(self) -> None:
        super().__init__(__name__)
        self.operation_repository = OperationRepository(self.context)
        self.account_repository = AccountRepository(self.context)

    def deposit(self, deposit_data: dict) -> tuple:
        return self._process(
            Operation.DEPOSIT,
            deposit_data["operation_key"],
            None,
            deposit_data["account_key"],
            deposit_data["amount"],
        )

    def transfer(self, transfer_data: dict) -> tuple:
        return self._process(
            Operation.TRANSFER,
            transfer_data["operation_key"],
            transfer_data["source_account_key"],
            transfer_data["destination_account_key"],
            transfer_data["amount"],
        )

    def get_by_key(self, operation_key: str) -> dict:
        operation_key = parse_key(operation_key, "operation_key")

        operation = self.operation_repository.get_by_key(operation_key)

        if operation is None:
            raise NotFoundOperation(operation_key)

        return OperationDTO.obj_to_dict(operation)

    def _process(self, operation_type: str, operation_key: str, source_key, destination_key: str, amount: int) -> tuple:
        """Devolve (operação, criada). `criada` é False numa repetição confirmada."""
        operation_key = operation_key.lower()
        source_key = source_key.lower() if source_key is not None else None
        destination_key = destination_key.lower()

        try:
            operation, created = self._execute(operation_type, operation_key, source_key, destination_key, amount)
        except QIException as error:
            self._log_movement(operation_type, operation_key, source_key, destination_key, amount, error.code)
            raise

        result = "CREATED" if created else "REPEATED"
        self._log_movement(operation_type, operation_key, source_key, destination_key, amount, result)
        return operation, created

    def _execute(self, operation_type: str, operation_key: str, source_key, destination_key: str, amount: int) -> tuple:
        fee_amount = TRANSFER_FEE if operation_type == Operation.TRANSFER else 0

        if amount <= 0:
            raise InvalidAmount(amount)

        if amount > BIGINT_MAX:
            raise AmountLimitExceeded(amount)

        if source_key is not None and source_key == destination_key:
            raise SameAccountTransfer(source_key)

        account_keys = [key for key in (source_key, destination_key) if key is not None]

        with self.lock_timeout_guard():
            for _ in range(MAX_ATTEMPTS):
                self.start_write_transaction()

                existing = self.operation_repository.get_by_key(operation_key)
                if existing is not None:
                    return self._repeated(existing, operation_type, source_key, destination_key, amount), False

                found = {account.account_key: account for account in self.account_repository.get_by_keys(account_keys)}
                for account_key in account_keys:
                    if account_key not in found:
                        raise NotFoundAccount(account_key)

                try:
                    operation = self.operation_repository.reserve(
                        operation_key,
                        operation_type,
                        found.get(source_key),
                        found[destination_key],
                        amount,
                        fee_amount,
                    )
                except IntegrityError as error:
                    if not self.is_unique_violation(error):
                        raise

                    # Outra requisição reservou a mesma chave e confirmou antes. Desfaz a
                    # própria transação e recomeça: a releitura devolve 200 (ou 409).
                    self.session.rollback()
                    continue

                locked = {
                    account.account_key: account for account in self.account_repository.lock_by_keys(account_keys)
                }
                source = locked.get(source_key)
                destination = locked[destination_key]

                if source is not None and source.balance < amount + fee_amount:
                    self.session.rollback()
                    raise InsufficientBalance(source_key, source.balance, amount + fee_amount)

                if destination.balance + amount > BIGINT_MAX:
                    self.session.rollback()
                    raise AmountLimitExceeded(amount)

                self._move_money(operation, source, destination, amount, fee_amount)

                operation_dto = OperationDTO.obj_to_dict(operation)
                self.session.commit()

                return operation_dto, True

        raise RuntimeError(f"Nao consegui processar a operacao {operation_key} em {MAX_ATTEMPTS} tentativas")

    def _move_money(self, operation: Operation, source, destination, amount: int, fee_amount: int) -> None:
        if source is None:
            self.operation_repository.add_entry(operation, destination, Entry.DEPOSIT, amount)
        else:
            source.balance = source.balance - (amount + fee_amount)
            self.operation_repository.add_entry(operation, source, Entry.TRANSFER_OUT, amount)
            self.operation_repository.add_entry(operation, destination, Entry.TRANSFER_IN, amount)
            self.operation_repository.add_entry(operation, source, Entry.FEE, fee_amount)

        destination.balance = destination.balance + amount

    def _repeated(self, operation: Operation, operation_type: str, source_key, destination_key: str, amount: int) -> dict:
        """Mesma chave: com os mesmos dados é a resposta original; com qualquer dado diferente, conflito."""
        source = operation.source_account
        same_source = (source.account_key if source is not None else None) == source_key

        same_data = (
            operation.type == operation_type
            and same_source
            and operation.destination_account.account_key == destination_key
            and operation.amount == amount
        )

        if not same_data:
            raise OperationKeyConflict(operation.operation_key)

        return OperationDTO.obj_to_dict(operation)

    def _log_movement(self, operation_type, operation_key, source_key, destination_key, amount, result) -> None:
        # Nunca o token, nunca o corpo inteiro: só o que identifica a movimentação.
        self.logger.info(
            f"MOVIMENTACAO type={operation_type} operation_key={operation_key} "
            f"source={source_key} destination={destination_key} amount={amount} result={result}"
        )
