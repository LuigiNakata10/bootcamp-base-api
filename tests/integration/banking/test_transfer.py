from tests.utils import ObjectGenerator, PayloadGenerator, RandomGenerator, RequestGenerator, assert_invariants

BIGINT_MAX = 2**63 - 1
FEE = 100


class TestTransferCreate:
    def test_moves_money_and_charges_the_fee_from_the_source(self):
        source = ObjectGenerator.create_account(balance=10000)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)

        status, response = RequestGenerator.POST_transfer(payload)

        assert status == 201
        assert response["operation_key"] == payload["operation_key"]
        assert response["type"] == "transfer"
        assert response["source_account_key"] == source
        assert response["destination_account_key"] == destination
        assert response["amount"] == 1000
        assert response["fee_amount"] == FEE
        assert ObjectGenerator.balance(source) == 10000 - 1000 - FEE
        assert ObjectGenerator.balance(destination) == 1000
        assert_invariants([source, destination])

    def test_generates_three_entries_across_the_two_accounts(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        operation = ObjectGenerator.transfer(source, destination, 2000)

        source_entries = {e["type"]: e for e in ObjectGenerator.all_entries(source)}
        destination_entries = ObjectGenerator.all_entries(destination)

        assert set(source_entries) == {"deposit", "transfer_out", "fee"}
        assert source_entries["transfer_out"]["amount"] == 2000
        assert source_entries["fee"]["amount"] == FEE
        assert source_entries["fee"]["operation_key"] == operation["operation_key"]
        assert [(e["type"], e["amount"]) for e in destination_entries] == [("transfer_in", 2000)]

    def test_smallest_transfer_still_pays_the_whole_fee(self):
        source = ObjectGenerator.create_account(balance=101)
        destination = ObjectGenerator.create_account()

        ObjectGenerator.transfer(source, destination, 1)

        assert ObjectGenerator.balance(source) == 0
        assert ObjectGenerator.balance(destination) == 1

    def test_exact_balance_for_amount_plus_fee_is_enough(self):
        source = ObjectGenerator.create_account(balance=1100)
        destination = ObjectGenerator.create_account()

        status, _ = RequestGenerator.POST_transfer(PayloadGenerator.create_transfer_payload(source, destination, 1000))

        assert status == 201
        assert ObjectGenerator.balance(source) == 0

    def test_repeating_returns_the_original_response_without_moving_money_again(self):
        source = ObjectGenerator.create_account(balance=10000)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)

        status, first = RequestGenerator.POST_transfer(payload)
        assert status == 201
        status, second = RequestGenerator.POST_transfer(payload)

        assert status == 200
        assert second == first
        assert ObjectGenerator.balance(source) == 8900
        assert ObjectGenerator.balance(destination) == 1000
        assert_invariants([source, destination])

    def test_repeating_after_the_balance_changed_is_still_200(self):
        """Confirmada, a repetição devolve o original — mesmo que o saldo de hoje já não permitisse."""
        source = ObjectGenerator.create_account(balance=1100)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)
        status, first = RequestGenerator.POST_transfer(payload)
        assert status == 201
        assert ObjectGenerator.balance(source) == 0

        status, second = RequestGenerator.POST_transfer(payload)

        assert status == 200
        assert second == first

    def test_same_key_with_other_data_is_conflict(self):
        source = ObjectGenerator.create_account(balance=10000)
        destination = ObjectGenerator.create_account()
        other = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)
        status, _ = RequestGenerator.POST_transfer(payload)
        assert status == 201

        changes = [
            {"amount": 1001},
            {"amount": 0},
            {"amount": -1},
            {"amount": BIGINT_MAX + 1},
            {"destination_account_key": source},
            {"destination_account_key": other},
            {"source_account_key": other},
            {"source_account_key": destination, "destination_account_key": source},
        ]
        for change in changes:
            status, response = RequestGenerator.POST_transfer({**payload, **change})
            assert status == 409, change
            assert response["code"] == "QIT002008"

        assert ObjectGenerator.balance(source) == 8900
        assert ObjectGenerator.balance(destination) == 1000
        assert ObjectGenerator.balance(other) == 0

    def test_a_deposit_key_cannot_be_reused_by_a_transfer(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        deposit = ObjectGenerator.deposit(source, 100)

        payload = PayloadGenerator.create_transfer_payload(
            source, destination, 100, operation_key=deposit["operation_key"]
        )
        status, response = RequestGenerator.POST_transfer(payload)

        assert status == 409
        assert response["code"] == "QIT002008"

    def test_insufficient_balance_is_refused_and_nothing_changes(self):
        source = ObjectGenerator.create_account(balance=1099)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)

        status, response = RequestGenerator.POST_transfer(payload)

        assert status == 422
        assert response["code"] == "QIT002007"
        assert ObjectGenerator.balance(source) == 1099
        assert ObjectGenerator.balance(destination) == 0
        assert len(ObjectGenerator.all_entries(source)) == 1
        assert ObjectGenerator.all_entries(destination) == []
        assert_invariants([source, destination])

    def test_insufficient_balance_releases_the_key(self):
        """A recusa desfaz a reserva da chave: com saldo, o MESMO pedido passa."""
        source = ObjectGenerator.create_account(balance=500)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)

        status, _ = RequestGenerator.POST_transfer(payload)
        assert status == 422
        status, response = RequestGenerator.GET_operation(payload["operation_key"])
        assert status == 404

        ObjectGenerator.deposit(source, 1000)
        status, _ = RequestGenerator.POST_transfer(payload)
        assert status == 201

    def test_same_account_is_unprocessable(self):
        account = ObjectGenerator.create_account(balance=5000)
        status, response = RequestGenerator.POST_transfer(PayloadGenerator.create_transfer_payload(account, account, 100))
        assert status == 422
        assert response["code"] == "QIT002006"
        assert ObjectGenerator.balance(account) == 5000

    def test_unknown_accounts_are_not_found(self):
        known = ObjectGenerator.create_account(balance=5000)
        unknown = RandomGenerator.generate_uuid()

        for source, destination in ((unknown, known), (known, unknown)):
            status, response = RequestGenerator.POST_transfer(
                PayloadGenerator.create_transfer_payload(source, destination, 100)
            )
            assert status == 404
            assert response["code"] == "QIT002004"

        assert ObjectGenerator.balance(known) == 5000

    def test_non_positive_amount_is_unprocessable(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        for amount in (0, -1, -1000):
            status, response = RequestGenerator.POST_transfer(
                PayloadGenerator.create_transfer_payload(source, destination, amount)
            )
            assert status == 422, amount
            assert response["code"] == "QIT002005"
        assert ObjectGenerator.balance(source) == 5000

    def test_amount_must_be_an_integer_number(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        for amount in (1.5, 1.0, "100", True, None):
            status, response = RequestGenerator.POST_transfer(
                PayloadGenerator.create_transfer_payload(source, destination, amount)
            )
            assert status == 400, repr(amount)
            assert response["code"] == "QIT000001"
        assert ObjectGenerator.balance(source) == 5000

    def test_amount_above_bigint_is_over_the_limit(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        status, response = RequestGenerator.POST_transfer(
            PayloadGenerator.create_transfer_payload(source, destination, BIGINT_MAX + 1)
        )
        assert status == 422
        assert response["code"] == "QIT002009"

    def test_credit_that_would_pass_the_limit_is_refused_and_nothing_changes(self):
        source = ObjectGenerator.create_account(balance=2000)
        destination = ObjectGenerator.create_account(balance=BIGINT_MAX)

        status, response = RequestGenerator.POST_transfer(PayloadGenerator.create_transfer_payload(source, destination, 1))

        assert status == 422
        assert response["code"] == "QIT002009"
        assert ObjectGenerator.balance(source) == 2000
        assert ObjectGenerator.balance(destination) == BIGINT_MAX

    def test_refuses_bad_bodies(self):
        a, b = ObjectGenerator.create_account(balance=1000), ObjectGenerator.create_account()
        valid = PayloadGenerator.create_transfer_payload(a, b, 100)
        bodies = [{}, {**valid, "unknown": 1}, {**valid, "operation_key": "x"}, {**valid, "source_account_key": "1"}]
        bodies += [{k: v for k, v in valid.items() if k != field} for field in valid]
        bodies += [{**valid, field: valid[field] + "\n"} for field in (
            "operation_key", "source_account_key", "destination_account_key"
        )]

        for body in bodies:
            status, response = RequestGenerator.POST_transfer(body)
            assert status == 400, body
            assert response["code"] == "QIT000001"

        assert ObjectGenerator.balance(a) == 1000
        assert ObjectGenerator.balance(b) == 0
        assert_invariants([a, b])

    def test_operation_can_be_fetched_after_the_transfer(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        created = ObjectGenerator.transfer(source, destination, 1000)

        status, response = RequestGenerator.GET_operation(created["operation_key"])

        assert status == 200
        assert response == created
