import re

from errors import InvalidParameter

UUID_FORMAT = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def parse_key(value: str, name: str = "key") -> str:
    """Valida o UUID canônico e o devolve em minúsculas, que é como ele é gravado e comparado.

    Fora do formato é 400 sem consultar o banco: uma chave que nem parece
    UUID não pode existir, e a resposta certa para isso não é "não achei".
    """
    if not isinstance(value, str) or not UUID_FORMAT.fullmatch(value):
        raise InvalidParameter(f"{name} must be a canonical UUID")

    return value.lower()
