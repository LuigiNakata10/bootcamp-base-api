import re

# 12 primeiros caracteres A-Z ou 0-9, mais 2 verificadores numéricos.
CNPJ_FORMAT = re.compile(r"^[A-Z0-9]{12}[0-9]{2}$")

FIRST_WEIGHTS = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
SECOND_WEIGHTS = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]


def normalize_cnpj(cnpj: str) -> str:
    """Minúsculas viram maiúsculas antes de validar, gravar e comparar."""
    return cnpj.upper()


def check_digit(characters: str, weights: list) -> int:
    # O valor de cada caractere é o código ASCII menos 48: '0'..'9' valem 0..9
    # e 'A' vale 17. Num CNPJ só numérico isso dá o cálculo clássico.
    total = sum((ord(char) - 48) * weight for char, weight in zip(characters, weights))
    remainder = total % 11

    if remainder < 2:
        return 0

    return 11 - remainder


def is_valid_cnpj(cnpj: str) -> bool:
    """Confere formato e os dois verificadores (módulo 11). Espera o CNPJ já normalizado."""
    if not CNPJ_FORMAT.match(cnpj):
        return False

    first = check_digit(cnpj[:12], FIRST_WEIGHTS)
    second = check_digit(cnpj[:12] + str(first), SECOND_WEIGHTS)

    return cnpj[12:] == f"{first}{second}"
