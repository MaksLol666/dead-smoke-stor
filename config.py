import os
from dotenv import load_dotenv

# Читаем .env, если он есть рядом. Если нет — не сломается
load_dotenv()

# === ОТЛАДКА (можно убрать потом) ===
print("=== CONFIG DEBUG ===")
print("cwd:", os.getcwd())
print("files here:", os.listdir("."))
print(".env exists:", os.path.exists(".env"))
print("BOT_TOKEN:", "OK" if os.getenv("BOT_TOKEN") else "MISSING")
print("ADMIN_ID:", repr(os.getenv("ADMIN_ID")))
print("====================")

# === ОСНОВНЫЕ ПЕРЕМЕННЫЕ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_URL = "sqlite+aiosqlite:///data/shop.db"

# === ПРОВЕРКИ ===
if not BOT_TOKEN:
    raise RuntimeError(
        "❌ BOT_TOKEN не задан!\n"
        "Проверь:\n"
        "1) Файл .env в корне проекта\n"
        "2) Строку BOT_TOKEN=... без кавычек\n"
        "3) Или переменные в панели хостинга"
    )
if not ADMIN_ID:
    raise RuntimeError(
        "❌ ADMIN_ID не задан!\n"
        "Проверь:\n"
        "1) Файл .env в корне проекта\n"
        "2) Строку ADMIN_ID=1691654877 без кавычек\n"
        "3) Или переменные в панели хостинга"
    )

# === КАТЕГОРИИ КАТАЛОГА ===
CATEGORIES = [
    "Жижа",
    "Устройства",
    "Одноразки",
    "Снюс",
    "Пластинки",
    "Расходники",
    "Наборы",
]

# === РЕФЕРАЛЬНАЯ СИСТЕМА ===
REFERRAL_BONUS_PERCENT = 15       # 15% от первой покупки реферала
REFERRAL_MILESTONE = 10           # каждые N купивших рефералов
REFERRAL_MILESTONE_DISCOUNT = 10  # даём промокод на −10%

# === ПРОМОКОДЫ ===
MAX_PROMOS_PER_ORDER = 2          # максимум промокодов на 1 заказ
