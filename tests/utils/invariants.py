from tests.utils.object_generator import ObjectGenerator

SIGN = {"deposit": 1, "transfer_in": 1, "transfer_out": -1, "fee": -1}


def assert_invariants(account_keys: list) -> None:
    """As contas do cenário, vistas só pela API, têm de fechar a conta.

    Vale para um conjunto FECHADO: toda transferência que aparece no extrato
    tem origem e destino dentro de `account_keys`.
    """
    total_balance = 0
    deposits = 0
    fees = 0
    entries_per_operation = {}

    for account_key in account_keys:
        balance = ObjectGenerator.balance(account_key)
        entries = ObjectGenerator.all_entries(account_key)

        assert balance >= 0, f"saldo negativo em {account_key}"
        assert balance == sum(SIGN[e["type"]] * e["amount"] for e in entries), f"extrato não fecha o saldo de {account_key}"

        total_balance += balance
        for entry in entries:
            entries_per_operation.setdefault(entry["operation_key"], []).append(entry)
            if entry["type"] == "deposit":
                deposits += entry["amount"]
            if entry["type"] == "fee":
                fees += entry["amount"]

    assert total_balance == deposits - fees, "soma dos saldos diferente de depósitos menos tarifas"

    for operation_key, entries in entries_per_operation.items():
        types = sorted(e["type"] for e in entries)
        assert types in (["deposit"], ["fee", "transfer_in", "transfer_out"]), f"{operation_key}: lançamentos {types}"
