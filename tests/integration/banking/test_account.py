from tests.utils import ObjectGenerator, RandomGenerator, RequestGenerator


class TestAccountGet:
    def test_new_account_has_zero_balance(self):
        company = ObjectGenerator.create_company(legal_name="Acme Ltda")

        status, response = RequestGenerator.GET_account(company["account_key"])

        assert status == 200
        assert response["account_key"] == company["account_key"]
        assert response["company_key"] == company["company_key"]
        assert response["legal_name"] == "Acme Ltda"
        assert response["balance"] == 0
        assert response["currency"] == "BRL"

    def test_does_not_expose_internal_ids(self):
        company = ObjectGenerator.create_company()

        status, response = RequestGenerator.GET_account(company["account_key"])

        assert status == 200
        assert not {"id", "company_id", "account_id"} & set(response)

    def test_key_is_compared_in_lowercase(self):
        company = ObjectGenerator.create_company()
        status, response = RequestGenerator.GET_account(company["account_key"].upper())
        assert status == 200
        assert response["account_key"] == company["account_key"]

    def test_unknown_key_is_not_found(self):
        status, response = RequestGenerator.GET_account(RandomGenerator.generate_uuid())
        assert status == 404
        assert response["code"] == "QIT002004"

    def test_company_key_is_not_an_account_key(self):
        company = ObjectGenerator.create_company()
        status, response = RequestGenerator.GET_account(company["company_key"])
        assert status == 404
        assert response["code"] == "QIT002004"

    def test_key_out_of_format_is_invalid_parameter(self):
        for key in ("1", "abc", RandomGenerator.generate_uuid() + "%0A"):
            status, response = RequestGenerator.GET_account(key)
            assert status == 400, key
            assert response["code"] == "QIT000010"
