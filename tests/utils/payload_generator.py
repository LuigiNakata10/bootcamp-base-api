from tests.utils.random_generator import RandomGenerator


class PayloadGenerator:
    @staticmethod
    def create_company_payload(legal_name: str = None, cnpj: str = None) -> dict:
        """Um cadastro válido, com CNPJ e razão social novos, salvo o que for pedido."""
        return {
            "legal_name": legal_name if legal_name is not None else RandomGenerator.generate_legal_name(),
            "cnpj": cnpj if cnpj is not None else RandomGenerator.generate_cnpj(),
        }

    @staticmethod
    def create_deposit_payload(account_key: str, amount: int = 1000, operation_key: str = None) -> dict:
        return {
            "operation_key": operation_key if operation_key is not None else RandomGenerator.generate_uuid(),
            "account_key": account_key,
            "amount": amount,
        }

    @staticmethod
    def create_transfer_payload(
        source_account_key: str,
        destination_account_key: str,
        amount: int = 1000,
        operation_key: str = None,
    ) -> dict:
        return {
            "operation_key": operation_key if operation_key is not None else RandomGenerator.generate_uuid(),
            "source_account_key": source_account_key,
            "destination_account_key": destination_account_key,
            "amount": amount,
        }
