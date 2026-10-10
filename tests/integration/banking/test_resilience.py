"""Os dois cenários que a caixa-preta não alcança sozinha.

Segurar uma trava por mais de 5 s e fazer o banco falhar no meio da gravação
exigem mexer no Postgres por fora da API — a mesma exceção que o `DbUtils`
já abre (conexão direta pela DATABASE_URL). O CENÁRIO continua nascendo pela
API (empresa, conta, depósito); o banco só é usado para provocar a falha.
"""
from sqlalchemy import create_engine, text

from tests.utils import DbUtils, INTERNAL_TOKEN, ObjectGenerator, PayloadGenerator, RequestGenerator
from tests.utils.requisition import ClientRequisition

FAILING_AMOUNT = 777


def post_transfer_with_headers(payload: dict):
    return ClientRequisition.send(
        "POST", "/transfers", payload=payload, headers={"INTERNAL-TOKEN": INTERNAL_TOKEN}
    )


class TestResilience:
    def test_lock_held_for_more_than_five_seconds_is_503_and_the_same_key_can_be_resent(self):
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_transfer_payload(source, destination, 1000)

        engine = create_engine(DbUtils.database_url())
        try:
            with engine.connect() as connection:
                # Esta conexão "é" uma transferência travada: segura a linha da conta de origem.
                connection.execute(
                    text("SELECT id FROM account WHERE account_key = :key FOR UPDATE"), {"key": source}
                )

                response = post_transfer_with_headers(payload)

                assert response.response_status == 503
                assert response.response_json["code"] == "QIT002010"
                assert response.response.headers["Retry-After"] == "1"

                connection.rollback()
        finally:
            engine.dispose()

        # Nada foi gravado: o saldo é o de antes e a chave nem chegou a existir.
        assert ObjectGenerator.balance(source) == 5000
        assert ObjectGenerator.balance(destination) == 0
        status, _ = RequestGenerator.GET_operation(payload["operation_key"])
        assert status == 404

        # Liberada a trava, o reenvio com a mesma chave é seguro e confirma.
        status, _ = RequestGenerator.POST_transfer(payload)
        assert status == 201
        assert ObjectGenerator.balance(source) == 5000 - 1000 - 100

    def test_database_failure_in_the_middle_of_the_write_is_500_and_nothing_is_stored(self):
        account_key = ObjectGenerator.create_account()
        payload = PayloadGenerator.create_deposit_payload(account_key, FAILING_AMOUNT)

        engine = create_engine(DbUtils.database_url(), isolation_level="AUTOCOMMIT")
        try:
            with engine.connect() as connection:
                connection.execute(
                    text(
                        f"""
                        CREATE OR REPLACE FUNCTION fail_entry_insert() RETURNS trigger AS $$
                        BEGIN
                            IF NEW.amount = {FAILING_AMOUNT} THEN
                                RAISE EXCEPTION 'falha provocada pelo teste';
                            END IF;
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql
                        """
                    )
                )
                connection.execute(
                    text("CREATE TRIGGER fail_entry_insert BEFORE INSERT ON entry FOR EACH ROW EXECUTE FUNCTION fail_entry_insert()")
                )

                try:
                    status, response = RequestGenerator.POST_deposit(payload)
                finally:
                    connection.execute(text("DROP TRIGGER IF EXISTS fail_entry_insert ON entry"))
                    connection.execute(text("DROP FUNCTION IF EXISTS fail_entry_insert()"))
        finally:
            engine.dispose()

        assert status == 500
        assert response["code"] == "QIT000500"

        # Nada pela metade: nem saldo, nem lançamento, nem a operação (a chave também foi desfeita).
        assert ObjectGenerator.balance(account_key) == 0
        assert ObjectGenerator.all_entries(account_key) == []
        status, _ = RequestGenerator.GET_operation(payload["operation_key"])
        assert status == 404

        status, _ = RequestGenerator.POST_deposit(payload)
        assert status == 201
