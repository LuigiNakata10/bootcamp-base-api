import random
import string
from uuid import uuid4

CNPJ_ALPHABET = string.ascii_uppercase + string.digits


def cnpj_check_digits(base: str) -> str:
    """Os 2 verificadores do CNPJ (módulo 11, valor = ASCII - 48), a partir dos 12 primeiros."""
    digits = []
    for weights in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        sequence = base + "".join(str(d) for d in digits)
        total = sum((ord(char) - 48) * weight for char, weight in zip(sequence, weights))
        remainder = total % 11
        digits.append(0 if remainder < 2 else 11 - remainder)
    return "".join(str(d) for d in digits)


class RandomGenerator:
    @staticmethod
    def generate_cnpj(alphanumeric: bool = False) -> str:
        """Um CNPJ válido de 14 caracteres, sem máscara. Com `alphanumeric`, os 12 primeiros misturam letras."""
        alphabet = CNPJ_ALPHABET if alphanumeric else string.digits
        base = "".join(random.choice(alphabet) for _ in range(12))
        if alphanumeric and base.isdigit():
            base = "A" + base[1:]
        return base + cnpj_check_digits(base)

    @staticmethod
    def generate_legal_name() -> str:
        return f"Empresa {uuid4().hex[:8]} Ltda"

    @staticmethod
    def generate_uuid() -> str:
        return str(uuid4())
