from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import OperationController
from utils.schema_handler import SchemaHandler


class OperationResource:
    """Depósitos, transferências e consulta de operações. O 201 é de operação nova; o 200, de repetição."""

    @SchemaHandler.validate("post_deposit.json")
    def on_post_deposit(self, payload: dict) -> JSONResponse:
        controller = OperationController()
        operation, created = controller.deposit(payload)

        return JSONResponse(content=jsonable_encoder(operation), status_code=success_status(created))

    @SchemaHandler.validate("post_transfer.json")
    def on_post_transfer(self, payload: dict) -> JSONResponse:
        controller = OperationController()
        operation, created = controller.transfer(payload)

        return JSONResponse(content=jsonable_encoder(operation), status_code=success_status(created))

    def on_get_by_key(self, operation_key: str) -> JSONResponse:
        controller = OperationController()
        operation = controller.get_by_key(operation_key)

        return JSONResponse(content=jsonable_encoder(operation), status_code=http_status.HTTP_200_OK)


def success_status(created: bool) -> int:
    if created:
        return http_status.HTTP_201_CREATED

    return http_status.HTTP_200_OK
