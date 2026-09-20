import random

DICE_EMOJIS = ["🎲", "🎯", "🎰", "🎳", "⚽", "🏀"]


def random_dice() -> str:
    return random.choice(DICE_EMOJIS)
