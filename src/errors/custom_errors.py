from errors import QIException


class InvalidCnpj(QIException):
    """O CNPJ tem o formato certo, mas os dígitos verificadores não batem.

    422, e não 400: a API leu e entendeu o pedido; é o valor que não pode existir.
    """

    code = "QIT002001"

    def __init__(self, cnpj) -> None:
        title = "Invalid CNPJ"
        http_status = 422
        description = f"The CNPJ {cnpj} has invalid check digits."
        translation = "O CNPJ informado não é válido."
        super().__init__(title, self.code, http_status, description, translation)


class CnpjLegalNameMismatch(QIException):
    """O CNPJ já está cadastrado, mas com outra razão social."""

    code = "QIT002002"

    def __init__(self, cnpj) -> None:
        title = "CNPJ registered with another legal name"
        http_status = 409
        description = f"There is already a company with the CNPJ {cnpj} and a different legal name."
        translation = "Já existe uma empresa com este CNPJ e outra razão social."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundCompany(QIException):
    code = "QIT002003"

    def __init__(self, company_key) -> None:
        title = "Company not Found"
        http_status = 404
        description = f"Company with key {company_key} was not found."
        translation = f"A empresa com chave {company_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundAccount(QIException):
    code = "QIT002004"

    def __init__(self, account_key) -> None:
        title = "Account not Found"
        http_status = 404
        description = f"Account with key {account_key} was not found."
        translation = f"A conta com chave {account_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)


class InvalidAmount(QIException):
    code = "QIT002005"

    def __init__(self, amount) -> None:
        title = "Invalid Amount"
        http_status = 422
        description = f"The amount {amount} must be a positive number of cents."
        translation = "O valor precisa ser positivo, em centavos."
        super().__init__(title, self.code, http_status, description, translation)


class SameAccountTransfer(QIException):
    code = "QIT002006"

    def __init__(self, account_key) -> None:
        title = "Same Account Transfer"
        http_status = 422
        description = f"The source and destination accounts are the same: {account_key}."
        translation = "A conta de origem e a de destino precisam ser diferentes."
        super().__init__(title, self.code, http_status, description, translation)


class InsufficientBalance(QIException):
    code = "QIT002007"

    def __init__(self, account_key, balance, required) -> None:
        title = "Insufficient Balance"
        http_status = 422
        description = f"Account {account_key} has {balance} cents and the operation requires {required}."
        translation = f"A conta {account_key} não tem saldo suficiente para a operação."
        super().__init__(title, self.code, http_status, description, translation)


class OperationKeyConflict(QIException):
    """A operation_key já foi usada, com outros dados."""

    code = "QIT002008"

    def __init__(self, operation_key) -> None:
        title = "Operation Key already used"
        http_status = 409
        description = f"The operation key {operation_key} was already used with different data."
        translation = "Esta chave de operação já foi usada com outros dados."
        super().__init__(title, self.code, http_status, description, translation)


class AmountLimitExceeded(QIException):
    code = "QIT002009"

    def __init__(self, amount) -> None:
        title = "Amount Limit Exceeded"
        http_status = 422
        description = f"The amount {amount} exceeds the limit supported by the account balance."
        translation = "O valor ultrapassa o limite suportado."
        super().__init__(title, self.code, http_status, description, translation)


class LockTimeout(QIException):
    """Esperou mais de 5 s pela trava de uma conta: nada foi gravado, pode reenviar."""

    code = "QIT002010"
    headers = {"Retry-After": "1"}

    def __init__(self) -> None:
        title = "Service Unavailable"
        http_status = 503
        description = "The account is busy with another operation. Retry with the same operation key."
        translation = "A conta está ocupada com outra operação. Tente novamente com a mesma chave."
        super().__init__(title, self.code, http_status, description, translation)


class NotFoundOperation(QIException):
    code = "QIT002011"

    def __init__(self, operation_key) -> None:
        title = "Operation not Found"
        http_status = 404
        description = f"Operation with key {operation_key} was not found."
        translation = f"A operação com chave {operation_key} não foi encontrada."
        super().__init__(title, self.code, http_status, description, translation)
