# RFC - Protótipo bancário empresarial

| | |
|---|---|
| **Time** | Bootcamp QI Tech |
| **Data** | 06/10/2026 |
| **Versão** | 5.0 |

## Contextualização

### Entendendo o problema

O banco ou fintech operador atende empresas com cadastro, conta, movimentações, tarifa e extrato paginado. Seu sistema consome a API; as empresas são titulares e pagadoras, sem acesso direto. O operador solicita depósitos simulados e transferências e consulta a arrecadação para conferir quanto cobrou e explicar cada tarifa. Deve impedir saldo divergente, duplicidade e execução parcial. Fora do escopo: interface, escalabilidade, pagamentos reais, integrações externas, múltiplas contas, crédito, estornos e agendamentos.

### Explicando a solução de forma macro

A API do projeto-base e o PostgreSQL registram empresas, contas, operações e lançamentos. Uma conta por empresa, centavos inteiros e tarifa fixa reduzem regras. Chave única, trava e confirmação conjunta preservam o dinheiro. A arrecadação soma os lançamentos de tarifa, sem conta movimentável do operador nem receita direta presumida da QI.

- Tarifa percentual: exige arredondamento; ganharia com preços comerciais diferenciados.
- Saldo pelo extrato: exige somas por operação; ganharia com baixo volume e sem saldo duplicado.
- Conta de arrecadação: duplica estado; ganharia se o operador movimentasse os recursos.
- Só cumprir o mínimo: registrar tarifas não oferece conferência por período; ganharia se o operador já a fizesse fora do serviço.

## Implementação

### Rotas

Recursos em inglês e no plural; `entries` representa os lançamentos do extrato. JSON sem campos desconhecidos; UUIDs públicos. Valores monetários inteiros, sem strings, booleanos ou frações. CNPJ é string de 14 dígitos sem máscara, validada localmente; razão social: 1 a 255 caracteres após trim. Negócio exige `INTERNAL-TOKEN` (`403` inválido). Erros: `title`, `description`, `translation`, `code`.

| Método | Caminho | O que faz | Entrada (campos que importam) | Saídas (status e quando) |
|---|---|---|---|---|
| `GET` | `/` | Identifica o serviço; pública | - | `200` |
| `GET` | `/health_check` | Verifica a API; pública | - | `204`; não verifica o banco |
| `POST` | `/companies` | Cria empresa e conta zero | `legal_name`, `cnpj` | `201` chaves da empresa/conta; `400` formato; `409` CNPJ repetido; `422` dígitos inválidos |
| `GET` | `/companies/{company_key}` | Consulta cadastro e conta | `company_key` | `200` cadastro e conta; `400` chave inválida; `404` inexistente |
| `GET` | `/accounts/{account_key}` | Consulta titular e saldo | `account_key` | `200` conta, empresa, `balance`, BRL; `400` chave inválida; `404` inexistente |
| `POST` | `/deposits` | Depósito gratuito; idempotente | `operation_key`, `account_key`, `amount` | `201` novo; `200` repetido; `400` formato; `404` conta; `409` chave conflitante; `422` valor/limite; `503` trava; `500` falha interna |
| `POST` | `/transfers` | Transferência + tarifa; idempotente | `operation_key`, `source_account_key`, `destination_account_key`, `amount` | `201` nova; `200` repetida; `400` formato; `404` conta; `409` chave conflitante; `422` valor, contas iguais, saldo/limite; `503` trava; `500` falha interna |
| `GET` | `/accounts/{account_key}/entries` | Extrato paginado | `account_key`, `page=0` | `200`, inclusive vazio; `400` chave/página; `404` conta |
| `GET` | `/fees` | Tarifas e total do período | `start_date`, `end_date`, `page=0` | `200`, inclusive vazio; `400` datas, página ou intervalo invertido |

**Dinheiro e horário:** BRL em centavos, dentro do limite de BIGINT assinado. Depósito simulado gratuito; transferência debita `amount + 100` na origem e credita `amount` no destino. Crédito excedente é recusado; total de tarifas é inteiro JSON sem o limite individual. Operações em qualquer horário, sem rate limiting/`429`; sem promessa de disponibilidade/capacidade ilimitadas.

<!-- pagebreak -->

**Idempotência:** depósitos/transferências exigem `operation_key`, UUID canônico de 36 caracteres do solicitante, com `UNIQUE` global em `OPERATION`, persistência após reinícios e sem expiração. Após validar formato e normalizar UUIDs, consultar a chave antes das regras de uma operação nova: conta existente, valor positivo no limite e contas distintas na transferência. Mesma chave, tipo, contas e valor: `200` com dados e instante originais; divergência: `409`, mesmo com valor zero/contas iguais. Outra operação exige chave nova. CNPJ repetido: `409`, sem recuperação de resposta.

**Retentativa:** nas movimentações, o operador guarda a chave antes do envio. Timeout, `5xx` ou COMMIT incerto: mesma chave/dados após ao menos 1 segundo, respeitando `Retry-After`. Espera de chave/trava excedida: `503`, `Retry-After: 1`; limite de 5s por espera, não por chamada. Outra chave aguarda a trava e relê o saldo antes de seguir. Resposta perdida não prova rollback. Só operações confirmadas ficam gravadas, sem estado pendente.

**Paginação:** 20 itens; `page` começa em zero; envelope `data`, `page`, `page_size`, `is_last_page`. Ordenar por `OPERATION.completed_at` e `ENTRY.id` decrescentes. Página além do fim: vazia e última; novas operações podem deslocar páginas. Extrato: valores positivos, tipo indica entrada/saída, principal separado da tarifa; entradas menos saídas/tarifas reconstruem saldo. `/fees`: datas obrigatórias `YYYY-MM-DD`, dias UTC inclusivos, total do período independente da página. Sem tarifas: vazio/zero; página além do fim mantém total. Instantes: ISO 8601 UTC.

**Respostas:** cadastro: `company_key`, `account_key`; empresa acrescenta `legal_name`, `cnpj`. Conta: `account_key`, `company_key`, `balance`, `currency=BRL`. Movimentações: `operation_key`, `amount`, `completed_at`; depósito acrescenta `account_key`; transferência, `source_account_key`, `destination_account_key`, `fee_amount`. Lançamentos: `entry_key`, `operation_key`, `amount`, `completed_at`; extrato acrescenta `type`; tarifa, `payer_account_key`. Envelope de tarifas acrescenta `start_date`, `end_date`, `total_amount`. IDs internos não saem.

**Erros (prefixo + sufixo):** base `QIT000`: `001` corpo/`010` parâmetros (`400`), `002` token (`403`), `404` rota (`404`), `405` método (`405`), `500` falha interna (`500`). Protótipo `QIT002`: `001` dígitos CNPJ (`422`), `002` CNPJ repetido (`409`), `003` empresa/`004` conta ausente (`404`), `005` valor não positivo/`006` contas iguais/`007` saldo insuficiente/`009` limite (todos `422`), `008` chave conflitante (`409`), `010` espera de bloqueio (`503`). Os códigos do protótipo não são catálogo comercial da QI.

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

**Leitura:** azul: processo; lilás: entrada; amarelo: decisão/trava; verde: registro/sucesso; vermelho: recusa. Falha pré-COMMIT desfaz os efeitos.

**Movimentações - apoio comum de idempotência e concorrência**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Operador["Operador"]
        I1[/"Operador: pedido<br/>operation_key + dados"/]
        I4(["400 formato / 403 token<br/>nenhuma gravação"])
        I8(["Chave nova: seguir<br/>depósito ou transferência"])
        I10(["200 resposta original<br/>sem novo débito ou tarifa"])
        I11(["409 dados diferentes<br/>nenhuma alteração"])
    end
    subgraph API["API"]
        I2["API: 1. Validar pedido<br/>token e formato"]
        I3{"Pedido<br/>válido?"}
        I5["API: 2. Normalizar UUIDs"]
        I7{"Chave<br/>confirmada?"}
        I9{"Tipo, contas e<br/>valor iguais?"}
    end
    subgraph PostgreSQL["PostgreSQL"]
        I6["Banco: 3. Consultar chave<br/>OPERATION.operation_key"]
    end
    I1 -.-> I2
    I2 --> I3
    I3 -->|"Não"| I4
    I3 -->|"Sim"| I5
    I5 --> I6
    I6 --> I7
    I7 -->|"Não"| I8
    I7 -->|"Sim"| I9
    I9 -->|"Sim"| I10
    I9 -->|"Não"| I11
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class I2,I5,I6 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class I1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class I3,I7,I9 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class I8,I10 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class I4,I11 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
```

Ao reservar a mesma `operation_key` em disputa:

1. Aguardar a transação concorrente pelo `INSERT UNIQUE`.
2. Se confirmar: ROLLBACK só local, nova sessão e consulta da chave; voltar à comparação.
3. Se desfizer: a própria inserção prossegue.
4. Espera acima de 5s: ROLLBACK só local; `503`, `Retry-After: 1`; a concorrente continua.

Com chaves diferentes, aguardar a trava da conta, reler o saldo e seguir a própria operação. Depósito e transferência iniciam com este apoio; disputas no INSERT seguem os passos acima.

**Cadastro - confirmação conjunta e falhas**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Operador["Operador"]
        R1[/"Operador: cadastro<br/>legal_name + cnpj"/]
        R4(["400 formato / 422 dígitos<br/>nenhuma gravação"])
        R8(["201 empresa + conta<br/>chaves públicas"])
        R10(["409 CNPJ repetido<br/>500 falha interna<br/>nenhuma segunda conta"])
    end
    subgraph API["API"]
        R2["API: 1. Validar cadastro<br/>nome e CNPJ localmente"]
        R3{"Dados<br/>válidos?"}
        R9(["Desfazer cadastro<br/>ROLLBACK empresa/conta"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        R5["Banco: 2. Criar empresa<br/>UNIQUE(cnpj)"]
        R6[/"Banco: 3. Criar conta<br/>BRL; saldo=0; company_id"/]
        R7["Banco: 4. Confirmar<br/>COMMIT de empresa/conta"]
    end
    R1 -.-> R2
    R2 --> R3
    R3 -->|"Não"| R4
    R3 -->|"Sim"| R5
    R5 --> R6
    R6 --> R7
    R7 --> R8
    R5 -->|"CNPJ repetido"| R9
    R6 -->|"Falha pré-COMMIT"| R9
    R9 --> R10
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class R2,R5,R7 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class R1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class R3 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class R6 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class R8 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class R4,R9,R10 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
```

**Depósito - crédito gratuito e falhas**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Operador["Operador"]
        D1[/"Operador: depósito simulado<br/>chave + conta + amount"/]
        D4(["404 conta / 422 valor<br/>chave não reservada"])
        D12(["201 depósito confirmado<br/>saldo/entry confirmados"])
    end
    subgraph API["API"]
        D2["API: 1. Verificar regras<br/>conta e amount positivo"]
        D3{"Regras<br/>válidas?"}
        D8{"Crédito cabe<br/>no limite?"}
        D13(["Desfazer tentativa<br/>422 limite / 500 falha interna<br/>ROLLBACK chave/operação/saldo/entry"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        D5["Banco: 2. Reservar chave<br/>UNIQUE; sem COMMIT<br/>disputa/espera: concorrência"]
        D6["Banco: 3. Travar conta<br/>FOR UPDATE"]
        D7["Banco: 4. Consultar saldo<br/>conta protegida pela trava"]
        D9[/"Banco: 5. Creditar conta<br/>balance += amount"/]
        D10[/"Banco: 6. Registrar dados<br/>ENTRY: deposit=amount<br/>OPERATION: fee_amount=0<br/>+ completed_at"/]
        D11["Banco: 7. Confirmar<br/>COMMIT: saldo/operação<br/>+ entry"]
    end
    D1 -.-> D2
    D2 --> D3
    D3 -->|"Não"| D4
    D3 -->|"Sim"| D5
    D5 --> D6
    D6 --> D7
    D7 --> D8
    D8 -->|"Sim"| D9
    D8 -->|"Não"| D13
    D9 --> D10
    D10 --> D11
    D11 --> D12
    D10 -->|"Falha pré-COMMIT"| D13
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class D2,D7,D11 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class D1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class D3,D8 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class D9,D10 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class D12 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class D4,D13 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class D5,D6 coord;
```

<!-- pagebreak -->

**Transferência - saldo, tarifa e falhas**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Operador["Operador"]
        T1[/"Operador: transferência<br/>chave nova + dados"/]
        T4(["404 conta / 422 regras<br/>chave não reservada"])
        T14(["201 confirmada<br/>destino: amount<br/>origem: amount + 100"])
    end
    subgraph API["API"]
        T2["API: 1. Verificar regras<br/>contas existentes e distintas<br/>amount positivo no limite"]
        T3{"Regras<br/>válidas?"}
        T8{"Saldo cobre<br/>amount + 100?"}
        T9{"Crédito cabe<br/>no limite?"}
        T15(["Desfazer tentativa<br/>422 saldo/limite / 500 interno<br/>ROLLBACK chave e efeitos<br/>nenhum dinheiro ou tarifa"])
    end
    subgraph PostgreSQL["PostgreSQL"]
        T5["Banco: 2. Reservar chave<br/>UNIQUE; sem COMMIT<br/>disputa/espera: concorrência"]
        T6["Banco: 3. Travar contas<br/>account_key crescente"]
        T7["Banco: 4. Consultar saldos<br/>ambas as contas protegidas"]
        T10[/"Banco: 5. Debitar origem<br/>balance -= amount + 100"/]
        T11[/"Banco: 6. Creditar destino<br/>balance += amount"/]
        T12[/"Banco: 7. Registrar dados<br/>transfer_out=amount<br/>transfer_in=amount<br/>ENTRY: fee=100<br/>OPERATION: completed_at"/]
        T13["Banco: 8. Confirmar<br/>COMMIT operação/saldos<br/>+ três lançamentos"]
    end
    T1 -.-> T2
    T2 --> T3
    T3 -->|"Não"| T4
    T3 -->|"Sim"| T5
    T5 --> T6
    T6 --> T7
    T7 --> T8
    T8 -->|"Sim"| T9
    T8 -->|"Não"| T15
    T9 -->|"Sim"| T10
    T9 -->|"Não"| T15
    T10 --> T11
    T11 --> T12
    T12 --> T13
    T13 --> T14
    T12 -->|"Falha pré-COMMIT"| T15
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class T2,T7,T13 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class T1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class T3,T8,T9 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    class T10,T11,T12 record;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class T14 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class T4,T15 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class T5,T6 coord;
```

**Extrato - paginação e conta inexistente**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Operador["Operador"]
        E1[/"Operador: consulta<br/>Extrato: account_key + page"/]
        E5(["400 parâmetros / 403 token<br/>nenhuma consulta ao banco"])
        E6(["404 não encontrado<br/>sem resultado"])
        E8(["200 extrato: entries<br/>principal / tarifa separados<br/>saldo reconstruível"])
    end
    subgraph API["API"]
        E2["API: 1. Validar consulta<br/>token, UUID e página"]
        E4{"Recurso<br/>existe?"}
    end
    subgraph PostgreSQL["PostgreSQL"]
        E3["Banco: 2. Buscar conta"]
        E7["Banco: 3. Paginar entries<br/>completed_at DESC<br/>+ ENTRY.id DESC"]
    end
    E7 --> E8
    E1 -.-> E2
    E2 -->|"Válido"| E3
    E2 -->|"Inválido"| E5
    E3 --> E4
    E4 -->|"Sim"| E7
    E4 -->|"Não"| E6
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class E2,E3,E7 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class E1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class E4 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class E8 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class E5,E6 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
```

**Arrecadação - período, total e falhas**

```mermaid
%%{init: {"theme":"base","flowchart":{"htmlLabels":true,"curve":"linear"}}}%%
flowchart TB
    subgraph Operador["Operador"]
        F1[/"Operador: arrecadação<br/>start_date, end_date, page"/]
        F4(["400 parâmetros / 403 token<br/>nenhuma consulta ao banco"])
        F8(["200 lista + total_amount<br/>sem tarifas: vazio e zero<br/>além do fim: preserva total"])
    end
    subgraph API["API"]
        F2["API: 1. Validar consulta<br/>token, datas e página"]
        F3{"Parâmetros<br/>válidos?"}
    end
    subgraph PostgreSQL["PostgreSQL"]
        F5["Banco: 2. Fixar fotografia<br/>REPEATABLE READ"]
        F6["Banco: 3. Somar tarifas<br/>período UTC inclusivo"]
        F7["Banco: 4. Paginar tarifas<br/>mesma fotografia do total"]
    end
    F1 -.-> F2
    F2 --> F3
    F3 -->|"Não"| F4
    F3 -->|"Sim"| F5
    F5 --> F6
    F6 --> F7
    F7 --> F8
    classDef process fill:#d8ebfa,stroke:#5683ab,color:#26344d;
    class F2,F6,F7 process;
    classDef data fill:#e9e1fb,stroke:#947ac0,color:#26344d;
    class F1 data;
    classDef decision fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class F3 decision;
    classDef record fill:#def3ec,stroke:#5caa97,color:#26344d;
    classDef success fill:#def3ec,stroke:#5caa97,color:#26344d;
    class F8 success;
    classDef failure fill:#fbe4e6,stroke:#bf6e78,color:#26344d;
    class F4 failure;
    classDef coord fill:#fff4d1,stroke:#caaa51,color:#26344d;
    class F5 coord;
```

> **Principal desafio**
>
> **Qual é:** impedir movimentação parcial, duplicada ou sem saldo.
>
> **Por que é difícil:** falhas, repetição e chamadas disputando o mesmo dinheiro.
>
> **Como resolve:** chave única comparada, contas travadas em ordem e COMMIT único de operação, saldos e lançamentos.
