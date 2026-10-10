from uuid import uuid4

from database import Context
from models import Account, Company


class CompanyRepository:

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, legal_name: str, cnpj: str) -> Company:
        """Insere a empresa e a conta de saldo zero. O `flush` leva o INSERT ao banco agora,
        para que um CNPJ repetido estoure aqui e não no commit."""
        company = Company()
        company.company_key = str(uuid4())
        company.legal_name = legal_name
        company.cnpj = cnpj

        account = Account()
        account.account_key = str(uuid4())
        account.balance = 0
        company.account = account

        self.session.add(company)
        self.session.flush()
        return company

    def get_by_cnpj(self, cnpj: str) -> Company:
        return self.session.query(Company).filter(Company.cnpj == cnpj).first()

    def get_by_key(self, company_key: str) -> Company:
        return self.session.query(Company).filter(Company.company_key == company_key).first()
