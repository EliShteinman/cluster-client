def to_upper(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


def to_lower(value: object) -> object:
    return value.lower() if isinstance(value, str) else value
