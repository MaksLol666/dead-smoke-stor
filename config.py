import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_URL = "sqlite+aiosqlite:///data/shop.db"

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN не задан! Укажи его в переменных окружения.")
if not ADMIN_ID:
    raise RuntimeError("❌ ADMIN_ID не задан! Укажи свой Telegram ID.")

CATEGORIES = [
    "Жижа",
    "Устройства",
    "Одноразки",
    "Снюс",
    "Пластинки",
    "Расходники",
    "Наборы",
]

REFERRAL_BONUS_PERCENT = 15
REFERRAL_MILESTONE = 10
REFERRAL_MILESTONE_DISCOUNT = 10
MAX_PROMOS_PER_ORDER = 2

# === ОТЗЫВЫ ===
REVIEWS_CHANNEL_ID = -1004357829679
REVIEWS_CHANNEL_USERNAME = "@OTZOV_DSS"

# === ДОСТАВКА ===
DELIVERY_PRICE = 500
