
class Emoji:
    """Enum of emojis used in the bot."""
    _db = {
        "PASS": "✅",
        "SKIP": "❎",
        "FAIL": "❌",
        "PLAY": "▶️",
    }

    def __init__(self):
        for name, emoji in self._db.items():
            setattr(self, name, emoji)
        return

    def __getitem__(self, item: str):
        return self._db[item.upper()]


emoji = Emoji()
