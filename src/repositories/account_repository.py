from database import Context
from models import Account


class AccountRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_key(self, account_key: str) -> Account:
        return self.session.query(Account).filter(Account.account_key == account_key).first()

    def get_by_keys(self, account_keys: list) -> list:
        """Lê as contas sem travar. Serve para saber se existem antes de reservar a chave."""
        return self.session.query(Account).filter(Account.account_key.in_(account_keys)).all()

    def lock_by_keys(self, account_keys: list) -> list:
        """Trava as contas (`FOR NO KEY UPDATE`), SEMPRE em ordem crescente de `account_key`.

        A ordem é a defesa contra deadlock: X→Y e Y→X simultâneas pedem as
        duas travas na mesma sequência, então uma espera a outra em vez de
        cada uma segurar uma ponta. O `populate_existing` força a releitura
        do saldo DEPOIS da trava, ignorando o que a sessão já tinha lido.

        Por que `NO KEY UPDATE` e não `UPDATE`: o INSERT da operação, feito
        ANTES da trava para reservar a chave, tem FK para as contas e por
        isso pega `FOR KEY SHARE` nelas. O `FOR UPDATE` conflita com o
        `KEY SHARE` das outras transferências, e duas transferências sobre
        as mesmas contas se bloqueavam mutuamente (deadlock, mesmo com a
        ordem das travas certa). O `NO KEY UPDATE` continua excluindo outra
        transferência na mesma conta, mas deixa passar o `KEY SHARE` das FKs.
        """
        return (
            self.session.query(Account)
            .filter(Account.account_key.in_(account_keys))
            .order_by(Account.account_key)
            .with_for_update(key_share=True)
            .populate_existing()
            .all()
        )
