from concurrent.futures import ThreadPoolExecutor

from tests.utils import ObjectGenerator, PayloadGenerator, RequestGenerator, assert_invariants

FEE = 100


def run_in_parallel(payloads: list) -> list:
    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        return list(pool.map(RequestGenerator.POST_transfer, payloads))


class TestTransferConcurrency:
    def test_only_the_transfers_that_fit_the_balance_pass(self):
        """8 pedidos de 1.000 (+100 de tarifa) contra um saldo de 3.500: passam exatamente 3."""
        source = ObjectGenerator.create_account(balance=3500)
        destination = ObjectGenerator.create_account()
        payloads = [PayloadGenerator.create_transfer_payload(source, destination, 1000) for _ in range(8)]

        results = run_in_parallel(payloads)

        statuses = sorted(status for status, _ in results)
        assert statuses == [201] * 3 + [422] * 5, statuses
        assert {body["code"] for status, body in results if status == 422} == {"QIT002007"}
        assert ObjectGenerator.balance(source) == 3500 - 3 * (1000 + FEE)
        assert ObjectGenerator.balance(destination) == 3000
        assert_invariants([source, destination])

    def test_crossed_transfers_do_not_deadlock(self):
        """A→B e B→A ao mesmo tempo: as travas em ordem crescente de account_key evitam o deadlock."""
        account_a = ObjectGenerator.create_account(balance=10000)
        account_b = ObjectGenerator.create_account(balance=10000)
        payloads = []
        for _ in range(4):
            payloads.append(PayloadGenerator.create_transfer_payload(account_a, account_b, 1000))
            payloads.append(PayloadGenerator.create_transfer_payload(account_b, account_a, 1000))

        results = run_in_parallel(payloads)

        assert [status for status, _ in results] == [201] * 8, results
        assert ObjectGenerator.balance(account_a) == 10000 - 4 * FEE
        assert ObjectGenerator.balance(account_b) == 10000 - 4 * FEE
        assert_invariants([account_a, account_b])

    def test_same_key_in_parallel_moves_money_once(self):
        source = ObjectGenerator.create_account(balance=10000)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)

        results = run_in_parallel([payload] * 8)

        statuses = sorted(status for status, _ in results)
        assert statuses == [200] * 7 + [201], statuses
        assert len({body["completed_at"] for _, body in results}) == 1
        assert ObjectGenerator.balance(source) == 10000 - 1000 - FEE
        assert ObjectGenerator.balance(destination) == 1000
        assert_invariants([source, destination])

    def test_many_sources_into_one_destination(self):
        destination = ObjectGenerator.create_account()
        sources = [ObjectGenerator.create_account(balance=2000) for _ in range(6)]
        payloads = [PayloadGenerator.create_transfer_payload(source, destination, 1000) for source in sources]

        results = run_in_parallel(payloads)

        assert [status for status, _ in results] == [201] * 6
        assert ObjectGenerator.balance(destination) == 6000
        assert_invariants(sources + [destination])
