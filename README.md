# Protótipo bancário — Bootcamp QI Tech 2026

API REST em **Python + FastAPI**, com **PostgreSQL**, rodando em **Docker**. Um operador (banco ou
fintech) cadastra **empresas** (cada uma com uma conta), faz **depósitos** e **transferências com
tarifa**, consulta o **extrato paginado** e confere a **arrecadação de tarifas** de um período.

O desenho completo, com as decisões tomadas e as descartadas, está na RFC:
[docs/RFC-prototipo-bancario-v6.4.md](docs/RFC-prototipo-bancario-v6.4.md) (revisão proposta; o PDF
correspondente é [docs/RFC-prototipo-bancario-v6.4.pdf](docs/RFC-prototipo-bancario-v6.4.pdf), e as
versões anteriores ficam em `docs/` como histórico). Este README só diz como subir, testar e chamar.

As três garantias do serviço:

- **Nada pela metade:** débito, crédito e tarifa acontecem juntos ou nenhum acontece (uma transação só).
- **Nada duas vezes:** a `operation_key` (e o CNPJ, no cadastro) torna qualquer reenvio seguro.
- **Nada sem saldo:** as contas são travadas em ordem crescente de `account_key`, e o saldo é lido
  depois da trava.

---

## 1. O que você precisa ter

| O quê | Para quê | Como conferir |
|---|---|---|
| **Docker** com `docker compose` | roda a API e o banco | `docker compose version` |
| **Python 3.11 ou mais novo** | roda os testes | `python3 --version` |

## 2. Subindo

```bash
docker compose up
```

Um comando, sem criar arquivo nenhum antes: as configurações têm valor padrão no próprio
`docker-compose.yml`. A API fica em http://localhost:3000. Espere o `(healthy)` antes de testar.

```bash
docker compose down        # desliga, mantendo os dados
docker compose down -v     # desliga E apaga o banco (obrigatório ao mudar database/database.sql)
```

## 3. Testando

Os testes rodam **na sua máquina**, só por HTTP, contra a API que está de pé no Docker. Nenhum deles
importa nada de `src/`.

```bash
python3 -m venv .venv
source .venv/bin/activate              # no Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt    # uma vez só

pytest                                                    # tudo (~40 s)
pytest -v tests/integration/banking/test_transfer.py      # um arquivo
pytest tests/integration/banking/test_transfer.py::TestTransferCreate::test_same_account_is_unprocessable   # um teste
```

O que a suíte cobre: cada recusa da RFC tem um teste; cada cenário de dinheiro termina conferindo as
**invariantes** (nenhum saldo negativo, saldo igual ao extrato, soma dos saldos igual a depósitos
menos tarifas, 1 lançamento por depósito e 3 por transferência); e há testes de **concorrência**
(saldo disputado, A→B e B→A ao mesmo tempo, mesma chave em paralelo).

Dois testes (`test_resilience.py`) abrem uma conexão direta ao Postgres para provocar uma trava
presa e uma falha no meio da gravação; o cenário em si continua nascendo pela API.

## 4. As rotas

Todas, exceto `/` e `/health_check`, exigem o cabeçalho `INTERNAL-TOKEN` (padrão `default_token`;
sem ele, `403 QIT000002`). Valores em **centavos inteiros**. Chaves são UUIDs; nenhum id interno sai.

| Método | Caminho | O que faz | Sucesso |
|---|---|---|---|
| `GET` | `/`, `/health_check` | identifica o serviço / diz que está de pé (sem tocar no banco) | `200` / `204` |
| `POST` | `/companies` | cria empresa e conta (saldo zero). Idempotente por CNPJ | `201` nova, `200` repetida |
| `GET` | `/companies/{company_key}` | empresa e conta | `200` |
| `GET` | `/accounts/{account_key}` | titular e saldo | `200` |
| `POST` | `/deposits` | depósito, sem tarifa. Idempotente por `operation_key` | `201` novo, `200` repetido |
| `POST` | `/transfers` | transferência; a origem paga `amount + 100` de tarifa. Idempotente por `operation_key` | `201` nova, `200` repetida |
| `GET` | `/operations/{operation_key}` | confere uma movimentação (para quando a resposta se perdeu) | `200` |
| `GET` | `/accounts/{account_key}/entries?page=0` | extrato, 20 por página, mais novo primeiro | `200` |
| `GET` | `/fees?start_date=&end_date=&page=0` | tarifas do período (dias UTC inclusivos) e `total_amount` | `200` |

Erros têm sempre `title`, `description`, `translation` e `code`. Os do protótipo:

| Código | Status | Quando |
|---|---|---|
| `QIT002001` | 422 | CNPJ com formato certo e dígitos verificadores errados |
| `QIT002002` | 409 | CNPJ já cadastrado com outra razão social |
| `QIT002003` | 404 | empresa não encontrada |
| `QIT002004` | 404 | conta não encontrada |
| `QIT002005` | 422 | valor zero ou negativo |
| `QIT002006` | 422 | transferência para a própria conta |
| `QIT002007` | 422 | saldo insuficiente para `amount + tarifa` |
| `QIT002008` | 409 | `operation_key` já usada com outros dados |
| `QIT002009` | 422 | valor acima do limite (BIGINT) |
| `QIT002010` | 503 | espera de trava acima de 5 s (com `Retry-After: 1`); reenvie a mesma chave |
| `QIT002011` | 404 | operação não encontrada (nunca chegou ao `COMMIT`) |
| `QIT000001` | 400 | corpo fora do formato (campo faltando, a mais, `amount` fracionário...) |
| `QIT000010` | 400 | parâmetro de caminho ou de query fora do formato |
| `QIT000002` | 403 | sem `INTERNAL-TOKEN` |

### Exemplo, do começo ao fim

```bash
H='-H INTERNAL-TOKEN:default_token -H Content-Type:application/json'

# 1. duas empresas (o CNPJ pode ser alfanumérico)
curl -s $H -X POST localhost:3000/companies -d '{"legal_name":"Acme Ltda","cnpj":"11222333000181"}'
curl -s $H -X POST localhost:3000/companies -d '{"legal_name":"Beta SA","cnpj":"12ABC34501DE35"}'
# → {"company_key":"...","account_key":"..."}   (repetir o mesmo pedido devolve 200 com as mesmas chaves)

# 2. a operation_key é gerada por QUEM CHAMA, antes de enviar (um UUID)
OP=$(python3 -c 'import uuid;print(uuid.uuid4())')
curl -s $H -X POST localhost:3000/deposits \
  -d "{\"operation_key\":\"$OP\",\"account_key\":\"<account_key da Acme>\",\"amount\":10000}"
# → 201. Reenviar o MESMO corpo devolve 200 e não credita de novo; outro valor com a mesma chave é 409.

# 3. transferência de R$ 25,00: a origem perde 2500 + 100 de tarifa
curl -s $H -X POST localhost:3000/transfers \
  -d "{\"operation_key\":\"$(python3 -c 'import uuid;print(uuid.uuid4())')\",\"source_account_key\":\"<Acme>\",\"destination_account_key\":\"<Beta>\",\"amount\":2500}"

# 4. saldo, extrato e tarifas
curl -s $H localhost:3000/accounts/<account_key>
curl -s $H "localhost:3000/accounts/<account_key>/entries?page=0"
curl -s $H "localhost:3000/fees?start_date=2026-10-01&end_date=2026-10-31"
```

Timeout ou `5xx` não provam que nada aconteceu. Consulte `GET /operations/{operation_key}`
(`404 QIT002011` quer dizer que não houve `COMMIT`) ou reenvie os mesmos dados.

Toda resposta traz o cabeçalho `X-Request-ID`; para achar a requisição no log:
`docker compose logs api | grep <id>`. Cada movimentação também escreve uma linha
`MOVIMENTACAO type=... operation_key=... result=...` (nunca o token).

## 5. Quando dá errado

**`port is already allocated`** — outro programa usa a porta (é comum já ter um Postgres na 5432).
Copie o `.env.example` para `.env` e troque as portas, **nos dois lugares** do banco:

```
API_PORT=3001
DB_PORT=5434
DATABASE_URL=postgresql+psycopg2://bootcamp:bootcamp@localhost:5434/bootcamp
```

O `DB_PORT` é a porta do banco **na sua máquina**; a `DATABASE_URL` é o endereço que os testes usam
de fora do Docker. A API lá dentro continua falando com `db:5432`. O `.env` fica fora do Git.

**`relation "..." does not exist`** — você mexeu em `database/database.sql`. Ele só roda **quando o
banco nasce**: `docker compose down -v && docker compose up`.

**Mexeu em `requirements.txt`** — a dependência mora na imagem: `docker compose build --no-cache api`.
Mexeu em `requirements-dev.txt`: reinstale no `.venv`.

**`failed to connect to the docker API`** — o Docker não está ligado.

**`Não consegui falar com a API` / `com o banco`** (nos testes) — suba com `docker compose up`,
espere o `(healthy)` e confira as portas do `.env`.

Para recomeçar do zero: `docker compose down -v && docker compose up`.

## 6. Como o código é organizado

Cada requisição atravessa as camadas sempre na mesma ordem, e cada uma só faz o seu papel:

`middlewares → resources → (schemas/*.json) → controllers → repositories → models → banco → dtos`

- `resources/` recebe a requisição, confere o schema e define o status de sucesso.
- `controllers/` decide (regras, travas, idempotência) e é o **único** que dá `commit`.
- `repositories/` é o único lugar com consulta; `models/` descreve as tabelas; `dtos/` monta a resposta.
- `errors/` define cada recusa com código e status; `src/app.py` lista todas as rotas e a ordem dos middlewares.

Mais detalhes em [docs/como-o-projeto-e-organizado.md](docs/como-o-projeto-e-organizado.md).
O schema do banco está em `database/database.sql` (não há migrations).

## 7. Configuração

Tudo tem valor padrão no `docker-compose.yml`; o `.env` é opcional (copie do `.env.example`) e ganha
do padrão. O `INTERNAL_TOKEN` vem de variável de ambiente, nunca do código — em produção, troque o
`default_token`.

## 8. Licença

Veja [LICENSE](LICENSE).
