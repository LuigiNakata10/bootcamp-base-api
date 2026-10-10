-- Protótipo bancário. A fonte de verdade do schema (não há migrations):
-- este arquivo só roda quando o banco nasce. Mudou? `docker compose down -v`.

CREATE TABLE company(
    id                              SERIAL PRIMARY KEY,
    company_key                     CHAR(36) NOT NULL,
    legal_name                      VARCHAR(255) NOT NULL,
    cnpj                            CHAR(14) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(company_key),
    UNIQUE(cnpj),
    CONSTRAINT legal_name_not_blank CHECK (char_length(btrim(legal_name)) BETWEEN 1 AND 255)
);

CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL,
    company_id                      INTEGER NOT NULL REFERENCES company(id),
    balance                         BIGINT NOT NULL DEFAULT 0,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(account_key),
    UNIQUE(company_id),
    CONSTRAINT balance_not_negative CHECK (balance >= 0)
);

CREATE TABLE operation(
    id                              SERIAL PRIMARY KEY,
    operation_key                   CHAR(36) NOT NULL,
    type                            VARCHAR(50) NOT NULL,
    source_account_id               INTEGER REFERENCES account(id),
    destination_account_id          INTEGER NOT NULL REFERENCES account(id),
    amount                          BIGINT NOT NULL,
    fee_amount                      BIGINT NOT NULL,
    completed_at                    TIMESTAMP NOT NULL DEFAULT(NOW() AT TIME ZONE 'UTC'),
    UNIQUE(operation_key),
    CONSTRAINT operation_type_valid CHECK (type IN ('deposit', 'transfer')),
    CONSTRAINT operation_amount_positive CHECK (amount > 0),
    CONSTRAINT operation_fee_valid CHECK (fee_amount IN (0, 100)),
    -- depósito não tem origem e não paga tarifa; transferência tem as duas
    -- contas, distintas, e paga a tarifa fixa
    CONSTRAINT operation_shape CHECK (
        (type = 'deposit' AND source_account_id IS NULL AND fee_amount = 0)
        OR
        (type = 'transfer' AND source_account_id IS NOT NULL
            AND source_account_id <> destination_account_id AND fee_amount = 100)
    )
);

CREATE TABLE entry(
    id                              SERIAL PRIMARY KEY,
    entry_key                       CHAR(36) NOT NULL,
    operation_id                    INTEGER NOT NULL REFERENCES operation(id),
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    type                            VARCHAR(50) NOT NULL,
    amount                          BIGINT NOT NULL,
    UNIQUE(entry_key),
    UNIQUE(operation_id, account_id, type),
    CONSTRAINT entry_type_valid CHECK (type IN ('deposit', 'transfer_in', 'transfer_out', 'fee')),
    CONSTRAINT entry_amount_positive CHECK (amount > 0)
);

CREATE INDEX entry_account_id_idx ON entry(account_id);
CREATE INDEX operation_completed_at_idx ON operation(completed_at);
