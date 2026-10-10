from models import Company


class CompanyDTO:

    @staticmethod
    def only_keys(company: Company) -> dict:
        return {
            "company_key": company.company_key,
            "account_key": company.account.account_key,
        }

    @staticmethod
    def obj_to_dict(company: Company) -> dict:
        dto = CompanyDTO.only_keys(company)
        dto["legal_name"] = company.legal_name
        dto["cnpj"] = company.cnpj
        dto["created_at"] = company.created_at.isoformat()

        return dto
