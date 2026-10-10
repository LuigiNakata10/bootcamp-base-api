# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Projeto base de um bootcamp (README e docs em português): API REST em FastAPI + PostgreSQL, rodando em Docker. A entidade de exemplo é `sample_entity`. A pasta `docs/` guarda as versões da RFC do protótipo bancário (v1.0–v5.0 versionadas; v6.0 ainda não commitada); não são código.

## Comandos

```bash
docker compose up                      # sobe API (porta 3000) + Postgres; espere o healthcheck (healthy)
docker compose logs api | grep <id>    # toda resposta traz um protocolo/identificador de requisição
docker compose down

# testes: rodam NA MÁQUINA, por HTTP, contra a API já de pé no Docker
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt   # uma vez
pytest
pytest -v tests/integration/test_healthcheck.py                   # um arquivo
pytest tests/integration/sample_entity/test_sample_entity_get.py::<Classe>::<teste>   # um teste

flake8   # config em .flake8 (max-line-length 140)
```

- Configuração vem de `.env` (copie de `.env.example` só para trocar valores; os defaults já estão no `docker-compose.yml`). Para mudar a porta da API, ajuste `API_PORT` no `.env`; os testes leem o mesmo `.env` via `tests/conftest.py`.
- Rotas exigem o cabeçalho `INTERNAL-TOKEN` (sem ele, 403). Exemplos de curl de cada rota estão no README.
- A documentação automática do FastAPI (docs/redoc/openapi) está desligada de propósito.

## Arquitetura

Código em `src/` (o import é a partir de `src/`, ex.: `from constants import ...`; o container roda `uvicorn app:app` com `src` como WORKDIR). Cada requisição atravessa camadas em ordem fixa, e cada camada só faz o seu papel (detalhado em `docs/como-o-projeto-e-organizado.md`):

middlewares → resources → (validação por `schemas/*.json`) → controllers → repositories → models → banco → dtos → resposta

- `resources/`: recebe a requisição, valida o schema, chama **um** controller, define o status HTTP da resposta. Sem SQL nem regra de negócio.
- `controllers/`: regra de negócio e **o único lugar que faz `commit`**. Sem consulta SQL e sem conhecimento de HTTP.
- `repositories/`: único lugar com consultas. Não decide permissões.
- `models/`: tabelas SQLAlchemy. `dtos/`: objeto do banco → dict de resposta.
- `errors/`: cada erro definido com código, mensagem e status HTTP; `error_verification()` e `check_variables()` rodam na subida e abortam se algo estiver faltando/inconsistente.
- `connectors/`: clientes de serviços externos (REST, boleto).
- `src/app.py` é o mapa central: lista **todas** as rotas (uma linha por endereço E verbo, FastAPI não descobre `on_get/on_post` sozinho como o Falcon) e a ordem dos middlewares.

### Ordem dos middlewares (regra, não gosto)

Registrados de dentro para fora (o último registrado executa primeiro): `session_manager` → `internal_token` → `request_logger` → `request_context` no código; na execução: request_context (id) → request_logger → internal_token → session_manager → rota. Não troque a ordem: nenhum teste a protege, mas o log perde o id da requisição ou deixa de registrar tentativas com 403. O `session_manager` faz rollback em erro e fecha a sessão, **nunca** dá commit.

### Testes

Testes de integração em `tests/integration/`, sem importar nada de `src/` (só falam HTTP via `tests/utils/requisition.py`). Exceção: `tests/utils/db_utils.py` acessa o banco por SQLAlchemy apenas para zerar dados entre testes; cenários são sempre montados via API (`POST`). Mantenha esse contrato ao adicionar testes.
