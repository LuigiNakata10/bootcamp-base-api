from fastapi import status as http_status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from controllers import CompanyController
from utils.schema_handler import SchemaHandler


class CompanyResource:
    """Cadastro e consulta de empresas. Cada empresa nasce com uma conta."""

    @SchemaHandler.validate("post_company.json")
    def on_post(self, payload: dict) -> JSONResponse:
        controller = CompanyController()
        company, created = controller.create(payload)

        if created:
            status_code = http_status.HTTP_201_CREATED
        else:
            status_code = http_status.HTTP_200_OK

        return JSONResponse(content=jsonable_encoder(company), status_code=status_code)

    def on_get_by_key(self, company_key: str) -> JSONResponse:
        controller = CompanyController()
        company = controller.get_by_key(company_key)

        return JSONResponse(content=jsonable_encoder(company), status_code=http_status.HTTP_200_OK)
