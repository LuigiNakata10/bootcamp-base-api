from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import AccountController


class AccountResource:
    """Consulta de contas: titular e saldo."""

    def on_get_by_key(self, account_key: str) -> JSONResponse:
        controller = AccountController()
        account = controller.get_by_key(account_key)

        return JSONResponse(content=jsonable_encoder(account), status_code=http_status.HTTP_200_OK)
