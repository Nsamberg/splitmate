import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "splitmate.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

APP_ENV = os.environ.get("APP_ENV", "development")
IS_PRODUCTION = APP_ENV == "production"

SESSION_SECRET = os.environ.get("SESSION_SECRET")
if not SESSION_SECRET:
    if IS_PRODUCTION:
        raise RuntimeError("SESSION_SECRET must be set when APP_ENV=production")
    SESSION_SECRET = "dev-only-insecure-secret-do-not-use-in-production"

# Used only to seed the access_code setting on first run. After that, the
# access code lives in the database and can be changed from /admin without
# a redeploy.
INITIAL_ACCESS_CODE = os.environ.get("ACCESS_CODE", "changeme")

# Seeded once, on first run, if the Member table is empty.
SEED_MEMBERS = ["Ade", "Sandro", "Vidhya", "Mohammed", "Atsushi", "Huseyin", "Sam", "Niko"]
ADMIN_MEMBER_NAME = os.environ.get("ADMIN_MEMBER_NAME", "Niko")

# Initial payment-routing preferences: name -> (preferred creditor's name or
# None, a short note explaining why). Only used to fill in a member's
# preference the first time it's unset — after that it's editable from
# /admin and this is never consulted again for that member. See
# balances.suggest_settlements_with_preferences.
PAYMENT_PREFERENCES: dict[str, tuple[str | None, str]] = {
    "Atsushi": ("Niko", "has a Wise account"),
    "Ade": ("Niko", "has a UK account"),
    "Mohammed": ("Ade", "has a US account"),
    "Sandro": ("Ade", "has a US account"),
    "Huseyin": ("Ade", "has a US account"),
    "Sam": (None, "prefers to limit the number of transfers"),
}
