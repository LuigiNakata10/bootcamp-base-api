import re
from concurrent.futures import ThreadPoolExecutor

from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator, assert_invariants

BIGINT_MAX = 2**63 - 1
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)$")


class TestDepositCreate:
    def test_creates_deposit_and_credits_the_account(self):
        account_key = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_deposit_payload(account_key, 2500)

        status, response = RequestGenerator.POST_deposit(payload)

        assert status == 201
        assert response["operation_key"] == payload["operation_key"]
        assert response["type"] == "deposit"
        assert response["source_account_key"] is None
        assert response["destination_account_key"] == account_key
        assert response["amount"] == 2500
        assert response["fee_amount"] == 0
        assert ISO_UTC.match(response["completed_at"])
        assert ObjectGenerator.balance(account_key) == 2500

    def test_deposit_generates_a_single_entry(self):
        account_key = ObjectGenerator.create_account()
        operation = ObjectGenerator.deposit(account_key, 700)

        entries = ObjectGenerator.all_entries(account_key)

        assert len(entries) == 1
        assert entries[0]["type"] == "deposit"
        assert entries[0]["amount"] == 700
        assert entries[0]["operation_key"] == operation["operation_key"]
        assert_invariants([account_key])

    def test_operation_key_is_stored_in_lowercase(self):
        account_key = ObjectGenerator.create_account()
        operation_key = RandomGenerator.generate_uuid()
        payload = PayloadGenerator.create_deposit_payload(account_key, 100, operation_key=operation_key.upper())

        status, response = RequestGenerator.POST_deposit(payload)

        assert status == 201
        assert response["operation_key"] == operation_key

    def test_repeating_returns_the_original_response_without_crediting_again(self):
        account_key = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_deposit_payload(account_key, 1000)

        status, first = RequestGenerator.POST_deposit(payload)
        assert status == 201

        status, second = RequestGenerator.POST_deposit(payload)
        assert status == 200
        assert second == first
        assert ObjectGenerator.balance(account_key) == 1000
        assert len(ObjectGenerator.all_entries(account_key)) == 1

    def test_same_key_with_other_data_is_conflict(self):
        account_key = ObjectGenerator.create_account()
        other_account_key = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_deposit_payload(account_key, 1000)
        status, _ = RequestGenerator.POST_deposit(payload)
        assert status == 201

        changes = [{"amount": amount} for amount in (1001, 0, -1, BIGINT_MAX + 1)]
        changes.append({"account_key": other_account_key})
        for changed in changes:
            status, response = RequestGenerator.POST_deposit({**payload, **changed})
            assert status == 409, changed
            assert response["code"] == "QIT002008"

        assert ObjectGenerator.balance(account_key) == 1000
        assert ObjectGenerator.balance(other_account_key) == 0

    def test_refused_deposit_does_not_reserve_the_key(self):
        account_key = ObjectGenerator.create_account()
        operation_key = RandomGenerator.generate_uuid()

        status, _ = RequestGenerator.POST_deposit(
            PayloadGenerator.create_deposit_payload(account_key, 0, operation_key=operation_key)
        )
        assert status == 422

        status, _ = RequestGenerator.POST_deposit(
            PayloadGenerator.create_deposit_payload(account_key, 300, operation_key=operation_key)
        )
        assert status == 201
        assert ObjectGenerator.balance(account_key) == 300

    def test_non_positive_amount_is_unprocessable(self):
        account_key = ObjectGenerator.create_account()
        for amount in (0, -1, -1000):
            status, response = RequestGenerator.POST_deposit(PayloadGenerator.create_deposit_payload(account_key, amount))
            assert status == 422, amount
            assert response["code"] == "QIT002005"
        assert ObjectGenerator.balance(account_key) == 0

    def test_amount_above_bigint_is_over_the_limit(self):
        account_key = ObjectGenerator.create_account()
        for amount in (BIGINT_MAX + 1, 10**30):
            status, response = RequestGenerator.POST_deposit(PayloadGenerator.create_deposit_payload(account_key, amount))
            assert status == 422, amount
            assert response["code"] == "QIT002009"

    def test_credit_that_would_pass_the_limit_is_refused_and_nothing_is_written(self):
        account_key = ObjectGenerator.create_account()
        ObjectGenerator.deposit(account_key, BIGINT_MAX)

        status, response = RequestGenerator.POST_deposit(PayloadGenerator.create_deposit_payload(account_key, 1))

        assert status == 422
        assert response["code"] == "QIT002009"
        assert ObjectGenerator.balance(account_key) == BIGINT_MAX
        assert len(ObjectGenerator.all_entries(account_key)) == 1

    def test_amount_must_be_an_integer_number(self):
        """Fração, `1.0`, texto, booleano e nulo são formato errado: 400, nunca arredondados."""
        account_key = ObjectGenerator.create_account()
        for amount in (1.5, 1.0, 100.0, "100", True, False, None, [100]):
            status, response = RequestGenerator.POST_deposit(PayloadGenerator.create_deposit_payload(account_key, amount))
            assert status == 400, repr(amount)
            assert response["code"] == "QIT000001"
        assert ObjectGenerator.balance(account_key) == 0

    def test_unknown_account_is_not_found(self):
        payload = PayloadGenerator.create_deposit_payload(RandomGenerator.generate_uuid(), 100)
        status, response = RequestGenerator.POST_deposit(payload)
        assert status == 404
        assert response["code"] == "QIT002004"

    def test_refuses_bad_bodies(self):
        account_key = ObjectGenerator.create_account()
        valid = PayloadGenerator.create_deposit_payload(account_key, 100)
        bodies = [
            {},
            {k: v for k, v in valid.items() if k != "operation_key"},
            {k: v for k, v in valid.items() if k != "account_key"},
            {k: v for k, v in valid.items() if k != "amount"},
            {**valid, "unknown": 1},
            {**valid, "operation_key": "not-a-uuid"},
            {**valid, "operation_key": valid["operation_key"] + "\n"},
            {**valid, "account_key": valid["account_key"] + "\n"},
            {**valid, "account_key": "123"},
            {**valid, "account_key": None},
        ]
        for body in bodies:
            status, response = RequestGenerator.POST_deposit(body)
            assert status == 400, body
            assert response["code"] == "QIT000001"

        assert ObjectGenerator.balance(account_key) == 0
        assert ObjectGenerator.all_entries(account_key) == []

    def test_same_key_in_parallel_credits_once(self):
        account_key = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_deposit_payload(account_key, 1000)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: RequestGenerator.POST_deposit(payload), range(8)))

        statuses = sorted(status for status, _ in results)
        assert statuses == [200] * 7 + [201], statuses
        assert len({body["completed_at"] for _, body in results}) == 1
        assert ObjectGenerator.balance(account_key) == 1000
        assert_invariants([account_key])


class TestOperationGet:
    def test_gets_the_original_response(self):
        account_key = ObjectGenerator.create_account()
        created = ObjectGenerator.deposit(account_key, 900)

        status, response = RequestGenerator.GET_operation(created["operation_key"])

        assert status == 200
        assert response == created

    def test_key_is_compared_in_lowercase(self):
        account_key = ObjectGenerator.create_account()
        created = ObjectGenerator.deposit(account_key, 900)
        status, response = RequestGenerator.GET_operation(created["operation_key"].upper())
        assert status == 200
        assert response == created

    def test_unknown_key_is_not_found(self):
        status, response = RequestGenerator.GET_operation(RandomGenerator.generate_uuid())
        assert status == 404
        assert response["code"] == "QIT002011"

    def test_refused_operation_leaves_nothing_to_find(self):
        account_key = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_deposit_payload(account_key, -5)
        status, _ = RequestGenerator.POST_deposit(payload)
        assert status == 422

        status, response = RequestGenerator.GET_operation(payload["operation_key"])
        assert status == 404
        assert response["code"] == "QIT002011"

    def test_key_out_of_format_is_invalid_parameter(self):
        for key in ("1", "abc", RandomGenerator.generate_uuid() + "%0A"):
            status, response = RequestGenerator.GET_operation(key)
            assert status == 400, key
            assert response["code"] == "QIT000010"
