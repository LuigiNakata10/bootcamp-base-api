import re
from concurrent.futures import ThreadPoolExecutor

from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def with_wrong_check_digit(cnpj: str) -> str:
    """O mesmo CNPJ com o último verificador trocado: formato certo, valor impossível."""
    return cnpj[:-1] + str((int(cnpj[-1]) + 1) % 10)


class TestCompanyCreate:
    def test_creates_company_and_account(self):
        payload = PayloadGenerator.create_company_payload()

        status, response = RequestGenerator.POST_company(payload)

        assert status == 201
        assert set(response) == {"company_key", "account_key"}
        assert UUID_PATTERN.match(response["company_key"])
        assert UUID_PATTERN.match(response["account_key"])

    def test_accepts_numeric_and_alphanumeric_cnpj(self):
        for cnpj in (RandomGenerator.generate_cnpj(), RandomGenerator.generate_cnpj(alphanumeric=True)):
            status, _ = RequestGenerator.POST_company(PayloadGenerator.create_company_payload(cnpj=cnpj))
            assert status == 201, cnpj

    def test_same_cnpj_and_legal_name_returns_original_keys(self):
        """Idempotência do cadastro: repetir não cria outra empresa, devolve a primeira."""
        payload = PayloadGenerator.create_company_payload()

        status, first = RequestGenerator.POST_company(payload)
        assert status == 201

        status, second = RequestGenerator.POST_company(payload)
        assert status == 200
        assert second == first

    def test_lowercase_cnpj_is_the_same_company(self):
        """Minúsculas viram maiúsculas antes de validar, gravar e comparar."""
        cnpj = RandomGenerator.generate_cnpj(alphanumeric=True)
        status, first = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("Acme", cnpj))
        assert status == 201

        status, second = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("Acme", cnpj.lower()))
        assert status == 200
        assert second == first

        status, company = RequestGenerator.GET_company(first["company_key"])
        assert status == 200
        assert company["cnpj"] == cnpj.upper()

    def test_legal_name_is_trimmed_before_comparing(self):
        cnpj = RandomGenerator.generate_cnpj()
        status, first = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("  Acme Ltda  ", cnpj))
        assert status == 201

        status, second = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("Acme Ltda", cnpj))
        assert status == 200
        assert second == first

        status, company = RequestGenerator.GET_company(first["company_key"])
        assert company["legal_name"] == "Acme Ltda"

    def test_same_cnpj_with_other_legal_name_is_conflict(self):
        cnpj = RandomGenerator.generate_cnpj()
        status, _ = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("Acme Ltda", cnpj))
        assert status == 201

        status, response = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("Outra Ltda", cnpj))
        assert status == 409
        assert response["code"] == "QIT002002"

    def test_wrong_check_digits_is_unprocessable(self):
        cnpj = with_wrong_check_digit(RandomGenerator.generate_cnpj())
        status, response = RequestGenerator.POST_company(PayloadGenerator.create_company_payload(cnpj=cnpj))
        assert status == 422
        assert response["code"] == "QIT002001"

    def test_wrong_check_digits_on_alphanumeric_cnpj_is_unprocessable(self):
        cnpj = with_wrong_check_digit(RandomGenerator.generate_cnpj(alphanumeric=True))
        status, response = RequestGenerator.POST_company(PayloadGenerator.create_company_payload(cnpj=cnpj))
        assert status == 422
        assert response["code"] == "QIT002001"

    def test_refuses_malformed_cnpj(self):
        """Máscara, tamanho errado e verificador com letra são problema de formato: 400."""
        valid = RandomGenerator.generate_cnpj()
        malformed = [
            "11.222.333/0001-81",
            valid[:-1],
            valid + "0",
            valid[:12] + "AB",
            valid[:5] + "-" + valid[6:],
            "",
        ]
        for cnpj in malformed:
            status, response = RequestGenerator.POST_company(PayloadGenerator.create_company_payload(cnpj=cnpj))
            assert status == 400, cnpj
            assert response["code"] == "QIT000001"

    def test_legal_name_must_have_1_to_255_chars_after_trim(self):
        status, _ = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("a" * 255))
        assert status == 201

        status, _ = RequestGenerator.POST_company(PayloadGenerator.create_company_payload("  " + "a" * 255 + "  "))
        assert status == 201

        for legal_name in ("a" * 256, "", "    "):
            status, response = RequestGenerator.POST_company(PayloadGenerator.create_company_payload(legal_name))
            assert status == 400, repr(legal_name)
            assert response["code"] == "QIT000001"

    def test_refuses_bad_bodies(self):
        valid = PayloadGenerator.create_company_payload()
        bodies = [
            {},
            {"legal_name": valid["legal_name"]},
            {"cnpj": valid["cnpj"]},
            {**valid, "unknown": 1},
            {**valid, "legal_name": 10},
            {**valid, "cnpj": None},
        ]
        for body in bodies:
            status, response = RequestGenerator.POST_company(body)
            assert status == 400, body
            assert response["code"] == "QIT000001"

    def test_same_cnpj_in_parallel_creates_one_company(self):
        payload = PayloadGenerator.create_company_payload()

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: RequestGenerator.POST_company(payload), range(8)))

        statuses = sorted(status for status, _ in results)
        assert statuses == [200] * 7 + [201], statuses
        assert len({tuple(sorted(body.items())) for _, body in results}) == 1


class TestCompanyGet:
    def test_gets_company_with_its_account(self):
        created = ObjectGenerator.create_company(legal_name="Acme Ltda")

        status, response = RequestGenerator.GET_company(created["company_key"])

        assert status == 200
        assert response["company_key"] == created["company_key"]
        assert response["account_key"] == created["account_key"]
        assert response["legal_name"] == "Acme Ltda"
        assert "id" not in response and "company_id" not in response

    def test_key_is_compared_in_lowercase(self):
        created = ObjectGenerator.create_company()
        status, response = RequestGenerator.GET_company(created["company_key"].upper())
        assert status == 200
        assert response["company_key"] == created["company_key"]

    def test_unknown_key_is_not_found(self):
        status, response = RequestGenerator.GET_company(RandomGenerator.generate_uuid())
        assert status == 404
        assert response["code"] == "QIT002003"

    def test_key_out_of_format_is_invalid_parameter(self):
        for key in ("1", "abc", "not-a-uuid"):
            status, response = RequestGenerator.GET_company(key)
            assert status == 400, key
            assert response["code"] == "QIT000010"
