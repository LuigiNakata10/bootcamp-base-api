# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Protótipo bancário do Bootcamp QI Tech 2026 (README e docs em português): API REST em FastAPI + PostgreSQL, rodando em Docker. O contrato (tabelas, rotas, status, códigos de erro, mecanismos) está na RFC mais recente em `docs/` (hoje `RFC-prototipo-bancario-v6.5.md`); **a RFC vence** se código e texto divergirem - corrija um dos dois e suba a versão da RFC. O PDF da banca (`docs/RFC-prototipo-bancario-v6.5.pdf`) é gerado a partir do `.md` fora do repositório: ao mudar a RFC, suba a versão no `.md` e gere o PDF de novo (as versões anteriores são histórico).

## Comandos

```bash
docker compose up -d                   # API (porta 3000) + Postgres; espere o healthcheck (healthy)
docker compose logs -f api             # toda resposta traz X-Request-ID; cada movimentação loga "MOVIMENTACAO ..."
docker compose down -v                 # OBRIGATÓRIO ao mudar database/database.sql (só roda quando o banco nasce)
docker compose build --no-cache api    # ao mudar requirements.txt (a dependência mora na imagem)

# testes: rodam NA MÁQUINA, por HTTP, contra a API já de pé no Docker
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt   # uma vez
pytest                                                            # ~40 s
pytest tests/integration/banking/test_transfer.py                 # um arquivo
pytest tests/integration/banking/test_transfer.py::TestTransferCreate::test_same_account_is_unprocessable   # um teste

flake8   # config em .flake8 (max-line-length 140)
```

- Configuração: defaults no `docker-compose.yml`; `.env` (fora do Git, copie de `.env.example`) é opcional e ganha do padrão. Se a 5432 do host estiver ocupada, ponha `DB_PORT=<livre>` **e** a mesma porta na `DATABASE_URL` do `.env` (os testes usam a `DATABASE_URL` de fora do Docker).
- Rotas (menos `/` e `/health_check`) exigem `INTERNAL-TOKEN` (padrão `default_token`).
- Docs automáticas do FastAPI estão desligadas de propósito. As versões em `requirements.txt` valem para a imagem (Python 3.11) **e** para o `.venv` de quem roda os testes (o README aceita Python ≥ 3.11, inclusive 3.14).

## Arquitetura

Código em `src/` (imports a partir de `src/`, ex.: `from errors import ...`; o container roda `uvicorn app:app`). Cada requisição atravessa camadas em ordem fixa (detalhe em `docs/como-o-projeto-e-organizado.md`):

middlewares → resources → (validação por `schemas/*.json`) → controllers → repositories → models → banco → dtos

- `resources/`: valida o schema (`@SchemaHandler.validate`), chama **um** controller e decide o status de sucesso (201 novo / 200 repetição). Sem SQL nem regra.
- `controllers/`: regra de negócio e **o único lugar que faz `commit`**; é quem chama `get_context()` (via `BaseController`). `OperationController` concentra depósito e transferência.
- `repositories/`: único lugar com consultas. `models/`: tabelas (ordem em `models/__init__.py` importa: company → account → operation → entry). `dtos/`: objeto → dict de resposta, nunca expõe `id` interno, só `*_key` (UUID).
- `errors/`: uma classe por recusa, com `code` único (`QIT002001`–`QIT002011` são do protótipo); `error_verification()` e `check_variables()` abortam a subida se algo estiver inconsistente. `QIException.headers` permite cabeçalhos extras (ex.: `Retry-After` no 503).
- `src/app.py` é o mapa: **todas** as rotas (uma linha por endereço E verbo) e a ordem dos middlewares.

### Ordem dos middlewares

Registrados de dentro para fora (o último registrado executa primeiro): na execução, request_context (id) → request_logger → internal_token → session_manager → rota. Não troque: nenhum teste a protege. O `session_manager` faz rollback em erro e fecha a sessão, **nunca** dá commit.

### Como uma movimentação é protegida (o miolo da RFC)

Após validar o formato no resource, `OperationController._execute` segue esta ordem: procura a `operation_key` (repetida: 200 com a resposta original, ou 409 se os dados diferem) → confere valor positivo no limite e contas distintas (422) → confere contas (404) → **reserva a chave** com `INSERT` sob `UNIQUE(operation_key)` na mesma transação do dinheiro → **trava as contas** `ORDER BY account_key` e só então lê os saldos → confere saldo/limite → move o dinheiro e grava os lançamentos → `COMMIT`. Qualquer recusa depois da reserva faz `rollback` explícito (desfaz também a chave). Pontos não óbvios:

- As contas são travadas com `FOR NO KEY UPDATE` (`with_for_update(key_share=True)`), **não** `FOR UPDATE`: o `INSERT` da operação tem FK para as contas e pega `FOR KEY SHARE`, que conflita com `FOR UPDATE` e causava deadlock entre transferências concorrentes mesmo com a ordem certa.
- `BaseController.start_write_transaction()` faz `SET LOCAL lock_timeout = '5s'`; `lock_timeout_guard()` converte SQLSTATE `55P03` em `503 QIT002010`. Chave repetida em paralelo: o `IntegrityError` (`23505`) faz rollback e o laço relê a operação.
- `SchemaHandler.validate` rejeita qualquer float no corpo (`reject_floats`): o jsonschema aceita `1.0` como `integer`. Dinheiro é sempre centavos inteiros (BIGINT).
- `GET /fees` abre `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ` como primeiro comando, para total e página virem da mesma fotografia.
- Parâmetros de caminho/query inválidos (UUID, `page`, datas) são `400 QIT000010` sem consultar o banco (`utils/identifiers.py`, `parse_page`, `parse_date`).

### Testes

Em `tests/integration/banking/`, só HTTP via `tests/utils/` (`RequestGenerator` uma função por rota; `ObjectGenerator` monta cenário pela API; `assert_invariants` confere saldo × extrato × depósitos − tarifas). Nunca importe `src/`. Exceções: `DbUtils.rollback()` zera o banco (necessário em `test_fees.py`, que depende de totais globais) e `test_resilience.py` usa conexão direta ao Postgres só para provocar a falha (trava presa, trigger). Testes de concorrência usam até 8 threads: o pool da API tem 5+10 conexões.
