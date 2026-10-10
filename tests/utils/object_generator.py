from tests.utils.payload_generator import PayloadGenerator
from tests.utils.request_generator import RequestGenerator


class ObjectGenerator:
    """Monta cenário pela porta da frente (a API), nunca pelo banco."""

    @staticmethod
    def create_company(legal_name: str = None, cnpj: str = None) -> dict:
        payload = PayloadGenerator.create_company_payload(legal_name=legal_name, cnpj=cnpj)
        status, response = RequestGenerator.POST_company(payload)
        assert status == 201, response
        return response

    @staticmethod
    def create_account(balance: int = 0) -> str:
        """Cria uma empresa nova e devolve a account_key, já com o saldo pedido."""
        account_key = ObjectGenerator.create_company()["account_key"]
        if balance > 0:
            ObjectGenerator.deposit(account_key, balance)
        return account_key

    @staticmethod
    def deposit(account_key: str, amount: int) -> dict:
        status, response = RequestGenerator.POST_deposit(PayloadGenerator.create_deposit_payload(account_key, amount))
        assert status == 201, response
        return response

    @staticmethod
    def transfer(source_account_key: str, destination_account_key: str, amount: int) -> dict:
        payload = PayloadGenerator.create_transfer_payload(source_account_key, destination_account_key, amount)
        status, response = RequestGenerator.POST_transfer(payload)
        assert status == 201, response
        return response

    @staticmethod
    def balance(account_key: str) -> int:
        status, response = RequestGenerator.GET_account(account_key)
        assert status == 200, response
        return response["balance"]

    @staticmethod
    def all_entries(account_key: str) -> list:
        """Todas as páginas do extrato, da mais nova para a mais antiga."""
        entries, page = [], 0
        while True:
            status, response = RequestGenerator.GET_entries(account_key, {"page": page})
            assert status == 200, response
            entries.extend(response["data"])
            if response["is_last_page"]:
                return entries
            page += 1
