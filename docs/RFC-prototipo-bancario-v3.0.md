# RFC - Protótipo bancário empresarial

| | |
|---|---|
| **Time** | Bootcamp QI Tech |
| **Data** | 05/10/2026 |
| **Versão** | 3.0 |

## Contextualização

### Entendendo o problema

Empresas precisam de cadastro, conta vinculada, movimentação com saldo, tarifa na transferência e extrato paginado. O sistema contratante atende essas empresas. O adicional é a consulta de arrecadação do operador, para conferir cobranças e identificar operação e pagador; não se presume receita direta da QI. O dinheiro deve permanecer correto diante de falhas, pedidos repetidos e simultâneos. Ficam fora: interface, escalabilidade, pagamentos reais, integrações externas, múltiplas contas, crédito, estornos e agendamentos.

### Explicando a solução de forma macro

A API e o PostgreSQL guardam empresas, contas, operações e lançamentos. A conta guarda saldo em centavos; a transferência debita principal mais tarifa fixa de 100 e credita o principal no destino. Bloqueios e chave única protegem o saldo; a transação confirma tudo junto. A arrecadação soma as tarifas, sem conta movimentável do operador.

- Tarifa percentual: descartada pelo arredondamento; ganharia com preços comerciais diferenciados.
- Saldo calculado pelo extrato: exige somas a cada operação; ganharia para dispensar saldo armazenado.
- Conta/tabela de arrecadação separada: duplica estado; ganharia se o operador movimentasse esses recursos.
- Integrações reais e filas: introduzem falhas externas e estados intermediários; ganhariam em pagamentos externos.

## Implementação

### Rotas

JSON sem campos desconhecidos; UUIDs públicos. Valores monetários inteiros, sem strings, booleanos ou frações. CNPJ é string de 14 dígitos sem máscara, validada localmente; razão social: 1 a 255 caracteres após trim. Negócio exige `INTERNAL-TOKEN` (`403` inválido). Erros: `title`, `description`, `translation`, `code`.

| Método | Caminho | O que faz | Entrada (campos que importam) | Saídas (status e quando) |
|---|---|---|---|---|
| `GET` | `/` | Identifica o serviço; pública | - | `200` |
| `GET` | `/health_check` | Verifica a API; pública | - | `204`; não verifica o banco |
| `POST` | `/companies` | Cria empresa e conta zero | `legal_name`, `cnpj` | `201` chaves da empresa/conta; `400` formato; `409` CNPJ repetido; `422` dígitos inválidos |
| `GET` | `/companies/{company_key}` | Consulta cadastro e conta | `company_key` | `200` cadastro e conta; `400` chave inválida; `404` inexistente |
| `GET` | `/accounts/{account_key}` | Consulta titular e saldo | `account_key` | `200` conta, empresa, `balance`, BRL; `400` chave inválida; `404` inexistente |
| `POST` | `/deposits` | Depósito gratuito; idempotente | `operation_key`, `account_key`, `amount` | `201` novo; `200` repetido; `400` formato; `404` conta; `409` chave conflitante; `422` valor/limite; `503` trava; `500` falha interna |
| `POST` | `/transfers` | Transferência + tarifa; idempotente | `operation_key`, `source_account_key`, `destination_account_key`, `amount` | `201` nova; `200` repetida; `400` formato; `404` conta; `409` chave conflitante; `422` valor, contas iguais, saldo/limite; `503` trava; `500` falha interna |
| `GET` | `/accounts/{account_key}/statement` | Extrato paginado | `account_key`, `page=0` | `200`, inclusive vazio; `400` chave/página; `404` conta |
| `GET` | `/fees` | Tarifas e total do período | `start_date`, `end_date`, `page=0` | `200`, inclusive vazio; `400` datas, página ou intervalo invertido |

Páginas têm 20 itens, iniciam em zero: `data`, `page`, `page_size`, `is_last_page`. Datas: `YYYY-MM-DD`; instantes: UTC. Valores individuais usam BIGINT assinado; crédito excedente é recusado. Total é inteiro JSON, podendo exceder o limite individual sem perda.

<!-- pagebreak -->

**Idempotência:** depósitos/transferências usam `operation_key` única (`UNIQUE` global). Mesma chave, tipo, contas e valor recuperam a resposta original com `200`; divergência: `409`. Outra operação legítima usa chave nova; CNPJ repetido recebe `409`. O fluxo de repetição não movimenta saldo nem cobra tarifa.

**Ordenação:** extrato e tarifas usam `OPERATION.completed_at` e `ENTRY.id` decrescentes. Entradas e saídas são identificadas pelo tipo; principal e tarifa ficam separados.

**Operação e retentativa:** qualquer horário, sem rate limiting/`429`, sem promessa de capacidade/disponibilidade ilimitadas. UUID canônico de 36 caracteres, guardado antes do envio, persistente e sem expiração. Timeout/`5xx`/COMMIT incerto: mesma chave/dados após ao menos 1 segundo, respeitando `Retry-After`. `X-Request-ID` é só log. `503` usa `Retry-After: 1`.

### Banco de Dados (Somente diagrama)

```mermaid
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#e3f1fd","primaryBorderColor":"#5683ab","attributeBackgroundColorOdd":"#e3f1fd","attributeBackgroundColorEven":"#f1f7fc"}}}%%
erDiagram
    COMPANY ||--|| ACCOUNT : possui
    ACCOUNT o|--o{ OPERATION : origem
    ACCOUNT ||--o{ OPERATION : destino
    OPERATION ||--|{ ENTRY : gera
    ACCOUNT ||--o{ ENTRY : recebe_lancamentos

    COMPANY {
        serial id PK "interno"
        char(36) company_key UK "sai na resposta"
        varchar(255) legal_name "1 a 255 caracteres"
        char(14) cnpj UK "14 digitos"
        timestamp created_at "default NOW()"
    }
    ACCOUNT {
        serial id PK "interno"
        char(36) account_key UK "sai na resposta"
        integer company_id FK,UK "uma conta por empresa"
        bigint balance "centavos BRL, CHECK >= 0"
        timestamp created_at "default NOW()"
    }
    OPERATION {
        serial id PK "interno"
        char(36) operation_key UK "chave do solicitante"
        varchar(50) type "deposit ou transfer"
        integer source_account_id FK "nulo somente no deposito"
        integer destination_account_id FK "obrigatorio"
        bigint amount "centavos, CHECK > 0"
        bigint fee_amount "deposito 0, transferencia 100"
        timestamp completed_at "instante UTC"
        timestamp created_at "default NOW()"
    }
    ENTRY {
        serial id PK "desempate da ordenacao"
        char(36) entry_key UK "sai na resposta"
        integer operation_id FK "UNIQUE com account_id e type"
        integer account_id FK "conta do lancamento"
        varchar(50) type "deposit, transfer_in, transfer_out, fee"
        bigint amount "centavos, CHECK > 0"
        timestamp created_at "default NOW()"
    }
```

<!-- pagebreak -->

### Fluxos

**Movimentações - validação e idempotência: sucesso e falhas**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Solicitante["Solicitante"]
        I1[/"Depósito / transferência<br/>chave + dados"/]
        I6(["400 formato / 403 token<br/>sem gravação"])
        I7(["M: chave nova<br/>seguir depósito ou<br/>transferência"])
        I8(["200 - resposta original<br/>sem revalidar saldo<br/>nem cobrar novamente"])
    end
    subgraph API["API"]
        I2["1. Validar token e formato<br/>do pedido"]
        I4{"Chave<br/>concluída?"}
        I5{"Mesmo tipo,<br/>contas e valor?"}
        I9(["409 - dados diferentes<br/>nenhuma alteração"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        I3["2. Consultar operation_key<br/>sem movimentar dinheiro"]
    end
    I1 -.-> I2
    I2 -->|"Inválido"| I6
    I2 -->|"Válido"| I3
    I3 -->|"Resultado"| I4
    I4 -->|"Não"| I7
    I4 -->|"Sim"| I5
    I5 -->|"Sim"| I8
    I5 -->|"Não"| I9
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class I2,I3 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class I1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class I4,I5 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class I7,I8 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class I6,I9 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
```

**Leitura:** M = chave nova; C = disputa da chave. Passos numerados e decisões Sim/Não. Azul: processo; lilás: entrada; amarelo: decisão/trava; verde: registro/sucesso; vermelho: recusa.

**Cadastro - caminho feliz e falhas de validação/unicidade**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Solicitante["Solicitante"]
        R1[/"Razão social + CNPJ"/]
        R10(["201 - cadastro e conta<br/>confirmados juntos"])
    end
    subgraph API["API"]
        R2["API: 1. Validar nome e CNPJ<br/>formato e dígitos, localmente"]
        R3{"Dados<br/>válidos?"}
        R4(["400 formato<br/>422 dígitos<br/>sem gravação"])
        R7(["ROLLBACK<br/>409 - repetido<br/>sem segunda conta"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        R5["Banco: 2. Criar empresa<br/>e conta zero juntas<br/>UNIQUE(CNPJ)"]
        R6{"CNPJ<br/>único?"}
        R8[/"Banco: empresa + conta BRL<br/>saldo zero, chaves públicas"/]
        R9["Banco: 3. COMMIT único<br/>encerrar sessão"]
    end
    R1 -.-> R2
    R2 --> R3
    R3 -->|"Não"| R4
    R3 -->|"Sim"| R5
    R5 --> R6
    R6 -->|"Não"| R7
    R6 -->|"Sim"| R8
    R8 --> R9
    R9 --> R10
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class R2,R5,R9 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class R1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class R3,R6 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class R8 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class R10 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class R4,R7 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
```

**Depósito - caminho feliz e falhas de conta/valor/limite**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Solicitante["Solicitante"]
        D1[/"M: chave nova (fluxo acima)"/]
    end
    subgraph API["API"]
        D2["API: 1. Verificar conta<br/>e amount positivo no limite"]
        D3{"Regras<br/>válidas?"}
        D4(["404 conta<br/>422 valor/limite<br/>sem reservar chave"])
        D7{"Saldo + amount<br/>cabe no limite?"}
        D8(["ROLLBACK<br/>422 - sem crédito<br/>liberar chave local"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        D5["Banco: 2. INSERT UNIQUE<br/>chave ainda sem COMMIT<br/>se houver disputa: fluxo C"]
        D6["Banco: 3. Travar a conta<br/>reler saldo protegido"]
        D9[/"Banco: 4. Creditar amount<br/>operação + entry deposit<br/>fee=0, completed_at"/]
        D10(["Banco: 5. COMMIT único<br/>201 - depósito confirmado<br/>encerrar sessão"])
    end
    D1 --> D2
    D2 --> D3
    D5 --> D6
    D6 --> D7
    D9 --> D10
    D3 -->|"Não"| D4
    D3 -->|"Sim"| D5
    D7 -->|"Não"| D8
    D7 -->|"Sim"| D9
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class D2 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class D1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class D3,D7 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class D9 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class D10 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class D4,D8 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class D5,D6 coord;
```

<!-- pagebreak -->

**Transferência - caminho feliz e falhas de saldo/limite**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Solicitante["Solicitante"]
        T1[/"M: chave nova (fluxo anterior)"/]
        T14(["201 - transferência e tarifa<br/>confirmadas, encerrar sessão"])
    end
    subgraph API["API"]
        T2["API: 1. Verificar contas<br/>existentes e distintas<br/>amount positivo no limite"]
        T3{"Regras<br/>válidas?"}
        T4(["404 conta<br/>422 valor/contas<br/>sem reservar chave"])
        T7{"Saldo origem &gt;=<br/>amount + 100?"}
        T8(["ROLLBACK<br/>422 - saldo<br/>sem débito/tarifa"])
        T9{"Destino + amount<br/>cabe no limite?"}
        T10(["ROLLBACK<br/>422 - limite<br/>sem crédito/tarifa"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        T5["Banco: 2. INSERT UNIQUE<br/>sem COMMIT<br/>se houver disputa: fluxo C"]
        T6["Banco: 3. Travar as contas<br/>em ordem crescente de chave<br/>reler ambos os saldos"]
        T11[/"Banco: 4. Origem -(amount+100)<br/>destino +amount<br/>registrar completed_at"/]
        T12[/"Lançamentos:<br/>transfer_out=amount<br/>transfer_in=amount<br/>fee=100"/]
        T13(["Banco: 5. COMMIT único<br/>operação + saldos<br/>+ 3 lançamentos"])
    end
    T1 --> T2
    T2 --> T3
    T5 --> T6
    T6 --> T7
    T13 --> T14
    T3 -->|"Não"| T4
    T3 -->|"Sim"| T5
    T7 -->|"Não"| T8
    T7 -->|"Sim"| T9
    T9 -->|"Não"| T10
    T9 -->|"Sim"| T11
    T11 -.-> T12
    T12 --> T13
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class T2 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class T1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class T3,T7,T9 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class T11,T12 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class T13,T14 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class T4,T8,T10 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class T5,T6 coord;
```

**Consultas - caminhos felizes e falhas de parâmetros/recurso**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Solicitante["Solicitante"]
        Q1[/"Chave/página ou período/página"/]
        Q8(["200 - cadastro<br/>saldo ou extrato"])
        Q9(["200 - total + lista<br/>sem tarifas:<br/>vazio e zero"])
        Q10[/"Extrato: entradas - saídas - tarifas = saldo<br/>Período UTC inclusivo, total independe da página<br/>Além do fim: lista vazia e última, preserva total"/]
    end
    subgraph API["API"]
        Q2["API: 1. Validar token, chave<br/>página e período quando usados"]
        Q3{"Parâmetros<br/>válidos?"}
        Q4(["400 parâmetros<br/>403 token<br/>sem consulta"])
        Q7(["404 - recurso<br/>inexistente<br/>não é lista vazia"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        Q5["Banco: 2. Buscar recurso<br/>Extrato: completed_at DESC<br/>+ ENTRY.id DESC"]
        Q6["Banco: 2. Tarifas<br/>REPEATABLE READ<br/>somar período e paginar<br/>na mesma fotografia"]
    end
    Q1 -.-> Q2
    Q2 --> Q3
    Q3 -->|"Não"| Q4
    Q3 -->|"Sim"| Q5
    Q3 -->|"Sim: tarifas"| Q6
    Q5 -->|"Ausente"| Q7
    Q5 -->|"Existe"| Q8
    Q6 --> Q9
    Q8 -.-> Q10
    Q9 -.-> Q10
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class Q2,Q5,Q6 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class Q1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class Q3 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class Q10 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class Q8,Q9 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class Q4,Q7 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
```

**C: concorrência - confirmação, rollback e recuperação**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph PostgreSQL["PostgreSQL"]
        C1["Banco: INSERT UNIQUE<br/>arbitra a disputa da chave"]
        C2{"Concorrente<br/>confirma?"}
        C5(["Concorrente desfaz:<br/>INSERT prossegue<br/>seguir depósito ou<br/>transferência"])
    end
    subgraph API["API"]
        C3["API: ROLLBACK local<br/>nova sessão e consulta"]
        C4(["Voltar à comparação da chave<br/>200 original ou 409"])
        C6(["INSERT/trava espera &gt; 5s:<br/>ROLLBACK só local<br/>503, Retry-After: 1<br/>original continua"])
    end
    C1 --> C2
    C2 -->|"Sim"| C3
    C2 -->|"Não"| C5
    C3 --> C4
    C1 -->|"Espera"| C6
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class C3 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class C2 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class C4,C5 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class C6 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class C1 coord;
```

**Falha de gravação - cadastro, depósito e transferência:**

1. Antes do COMMIT: ROLLBACK de cadastro/conta ou operação/saldos/lançamentos; nas movimentações, liberar só a chave inserida pela tentativa. Encerrar sessão e responder `500` se possível.
2. COMMIT incerto/resposta perdida: reenviar mesma chave/dados, sem presumir rollback nem gravar estado pendente. `lock_timeout=5s` vale por espera de INSERT/trava, não pela chamada inteira.

> **Principal desafio**
>
> **Qual é:** impedir movimentação parcial, duplicada ou sem saldo.
>
> **Por que é difícil:** falhas, repetição e chamadas disputando o mesmo dinheiro.
>
> **Como resolve:** chave única comparada, contas travadas em ordem e COMMIT único de operação, saldos e lançamentos.
