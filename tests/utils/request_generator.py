from os import environ

from tests.utils.requisition import ClientRequisition


INTERNAL_TOKEN = environ.get("INTERNAL_TOKEN", "default_token")


def _send(method: str, endpoint: str, payload=None, params=None):
    response = ClientRequisition.send(
        method,
        endpoint,
        payload=payload,
        query_params=params,
        headers={"INTERNAL-TOKEN": INTERNAL_TOKEN},
    )
    return response.response_status, response.response_json


class RequestGenerator:
    """Uma função por rota. Todas devolvem (status, corpo em JSON)."""

    @staticmethod
    def POST_company(payload: dict):
        return _send("POST", "/companies", payload=payload)

    @staticmethod
    def GET_company(company_key: str):
        return _send("GET", f"/companies/{company_key}")

    @staticmethod
    def GET_account(account_key: str):
        return _send("GET", f"/accounts/{account_key}")

    @staticmethod
    def POST_deposit(payload: dict):
        return _send("POST", "/deposits", payload=payload)

    @staticmethod
    def POST_transfer(payload: dict):
        return _send("POST", "/transfers", payload=payload)

    @staticmethod
    def GET_operation(operation_key: str):
        return _send("GET", f"/operations/{operation_key}")

    @staticmethod
    def GET_entries(account_key: str, params: dict = None):
        return _send("GET", f"/accounts/{account_key}/entries", params=params)

    @staticmethod
    def GET_fees(params: dict = None):
        return _send("GET", "/fees", params=params)
