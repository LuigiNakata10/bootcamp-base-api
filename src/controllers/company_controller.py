from sqlalchemy.exc import IntegrityError

from controllers.base_controller import BaseController
from dtos import CompanyDTO
from errors import CnpjLegalNameMismatch, InvalidCnpj, InvalidSchema, NotFoundCompany
from repositories import CompanyRepository
from utils.cnpj import is_valid_cnpj, normalize_cnpj
from utils.identifiers import parse_key

MAX_LEGAL_NAME_LENGTH = 255
MAX_ATTEMPTS = 3


class CompanyController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.company_repository = CompanyRepository(self.context)

    def create(self, company_data: dict) -> tuple:
        """Devolve (chaves, criada). `criada` é False quando o CNPJ já existia com a mesma razão social."""
        legal_name = company_data["legal_name"].strip()
        cnpj = normalize_cnpj(company_data["cnpj"])

        if not 1 <= len(legal_name) <= MAX_LEGAL_NAME_LENGTH:
            raise InvalidSchema(f"legal_name must have 1 to {MAX_LEGAL_NAME_LENGTH} characters after trim")

        if not is_valid_cnpj(cnpj):
            raise InvalidCnpj(cnpj)

        with self.lock_timeout_guard():
            for _ in range(MAX_ATTEMPTS):
                self.start_write_transaction()

                existing = self.company_repository.get_by_cnpj(cnpj)
                if existing is not None:
                    return self._repeated(existing, legal_name), False

                try:
                    company = self.company_repository.create(legal_name, cnpj)
                    company_dto = CompanyDTO.only_keys(company)
                    self.session.commit()
                except IntegrityError as error:
                    if not self.is_unique_violation(error):
                        raise

                    # Outra requisição com o mesmo CNPJ chegou ao COMMIT primeiro.
                    # Desfaz a própria transação e relê: vira o 200 (ou o 409) da repetição.
                    self.session.rollback()
                    continue

                self.logger.info(f"Empresa cadastrada: company_key={company.company_key}")
                return company_dto, True

        raise RuntimeError(f"Nao consegui cadastrar o CNPJ {cnpj} em {MAX_ATTEMPTS} tentativas")

    def get_by_key(self, company_key: str) -> dict:
        company_key = parse_key(company_key, "company_key")

        company = self.company_repository.get_by_key(company_key)

        if company is None:
            raise NotFoundCompany(company_key)

        return CompanyDTO.obj_to_dict(company)

    def _repeated(self, company, legal_name: str) -> dict:
        if company.legal_name != legal_name:
            raise CnpjLegalNameMismatch(company.cnpj)

        return CompanyDTO.only_keys(company)
