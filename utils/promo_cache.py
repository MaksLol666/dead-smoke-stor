_applied: dict[int, list[str]] = {}


def get_applied(user_id: int) -> list[str]:
    return _applied.get(user_id, [])


def add_applied(user_id: int, code: str) -> bool:
    lst = _applied.setdefault(user_id, [])
    if code in lst or len(lst) >= 2:
        return False
    lst.append(code)
    return True


def clear_applied(user_id: int):
    _applied.pop(user_id, None)
