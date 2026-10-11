from controllers.base_controller import BaseController
from dtos import AccountDTO, EntryDTO
from errors import InvalidParameter, NotFoundAccount
import re

from repositories import AccountRepository, EntryRepository
from utils.identifiers import parse_key

PAGE_SIZE = 20
PAGE_FORMAT = re.compile(r"^[0-9]{1,9}$")


class AccountController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.account_repository = AccountRepository(self.context)
        self.entry_repository = EntryRepository(self.context)

    def get_by_key(self, account_key: str) -> dict:
        account_key = parse_key(account_key, "account_key")

        account = self.account_repository.get_by_key(account_key)

        if account is None:
            raise NotFoundAccount(account_key)

        return AccountDTO.obj_to_dict(account)

    def list_entries(self, account_key: str, raw_page) -> dict:
        account_key = parse_key(account_key, "account_key")
        page = parse_page(raw_page)

        account = self.account_repository.get_by_key(account_key)

        if account is None:
            raise NotFoundAccount(account_key)

        # Lê uma linha a mais que a página: se ela existir, há próxima página.
        entries = self.entry_repository.list_by_account(account.id, PAGE_SIZE + 1, page * PAGE_SIZE)

        is_last_page = len(entries) <= PAGE_SIZE

        return {
            "data": EntryDTO.list_obj_to_list_dict(entries[:PAGE_SIZE]),
            "page": page,
            "page_size": PAGE_SIZE,
            "is_last_page": is_last_page,
        }


def parse_page(raw_page) -> int:
    """`page` começa em 0. Ausente vale 0; qualquer outra coisa que não seja inteiro sem sinal é 400."""
    if raw_page is None:
        return 0

    if not PAGE_FORMAT.fullmatch(raw_page):
        raise InvalidParameter("page must be an integer greater than or equal to 0")

    return int(raw_page)
