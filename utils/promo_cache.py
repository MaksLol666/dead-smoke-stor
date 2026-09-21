_applied: dict[int, list[str]] = {}
_cart_msg: dict[int, tuple[int, int]] = {}
_promo_prompt: dict[int, int] = {}


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
    _cart_msg.pop(user_id, None)
    _promo_prompt.pop(user_id, None)


def set_cart_message(user_id: int, chat_id: int, message_id: int):
    _cart_msg[user_id] = (chat_id, message_id)


def get_cart_message(user_id: int) -> tuple[int, int] | None:
    return _cart_msg.get(user_id)


def set_promo_prompt_id(user_id: int, message_id: int):
    _promo_prompt[user_id] = message_id


def get_promo_prompt_id(user_id: int) -> int | None:
    return _promo_prompt.pop(user_id, None)
