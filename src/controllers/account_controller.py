from controllers.base_controller import BaseController
from dtos import AccountDTO
from errors import NotFoundAccount
from repositories import AccountRepository
from utils.identifiers import parse_key


class AccountController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)

    def get_by_key(self, account_key: str) -> dict:
        account_key = parse_key(account_key, "account_key")

        account = self.account_repository.get_by_key(account_key)

        if account is None:
            raise NotFoundAccount(account_key)

        return AccountDTO.obj_to_dict(account)
