from database import Context
from models import Account


class AccountRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def get_by_key(self, account_key: str) -> Account:
        return self.session.query(Account).filter(Account.account_key == account_key).first()
