from models import Account

CURRENCY = "BRL"


class AccountDTO:

    @staticmethod
    def obj_to_dict(account: Account) -> dict:
        return {
            "account_key": account.account_key,
            "company_key": account.company.company_key,
            "legal_name": account.company.legal_name,
            "balance": account.balance,
            "currency": CURRENCY,
        }
