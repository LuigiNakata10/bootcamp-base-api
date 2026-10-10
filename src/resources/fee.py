from fastapi import Request
from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import FeeController


class FeeResource:
    """A arrecadação de tarifas de um período."""

    def on_get_list(self, request: Request) -> JSONResponse:
        controller = FeeController()
        params = request.query_params
        fees_page = controller.list_fees(params.get("start_date"), params.get("end_date"), params.get("page"))

        return JSONResponse(content=jsonable_encoder(fees_page), status_code=http_status.HTTP_200_OK)
