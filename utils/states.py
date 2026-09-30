from aiogram.fsm.state import State, StatesGroup


class AddProduct(StatesGroup):
    category = State()
    brand = State()
    flavor = State()
    price = State()


class EditProduct(StatesGroup):
    category = State()
    number = State()
    field = State()
    value = State()


class DelProduct(StatesGroup):
    category = State()
    number = State()


class PromoEnter(StatesGroup):
    code = State()


class PromoCreate(StatesGroup):
    kind = State()
    amount = State()
    uses = State()
    custom_code = State()


class Broadcast(StatesGroup):
    content = State()
    confirm = State()


class ReviewFlow(StatesGroup):
    rating = State()
    text = State()


class Checkout(StatesGroup):
    delivery = State()
    name = State()
    phone = State()
    city = State()
    address = State()
