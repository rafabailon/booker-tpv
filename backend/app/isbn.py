"""ISBN normalization and checksum validation."""

import re


def normalize_isbn(value: str | None) -> str | None:
    """Normalize and validate an optional ISBN-10 or ISBN-13."""
    if value is None or not value.strip():
        return None
    normalized = re.sub(r"[\s-]", "", value).upper()
    if not re.fullmatch(r"(?:\d{9}[\dX]|\d{13})", normalized):
        raise ValueError("El ISBN debe tener 10 o 13 caracteres válidos")
    if len(normalized) == 10:
        checksum = sum((10 - index) * (10 if char == "X" else int(char)) for index, char in enumerate(normalized))
        if checksum % 11:
            raise ValueError("El ISBN-10 no supera la validación de control")
        return normalized
    checksum = sum(int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(normalized))
    if checksum % 10:
        raise ValueError("El ISBN-13 no supera la validación de control")
    return normalized