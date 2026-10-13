import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-smartshelf-insecure-secret-key-change-in-prod")
    INSTANCE_DIR = BASE_DIR / "instance"
    DATABASE_PATH = os.getenv("DATABASE_PATH", str(INSTANCE_DIR / "library.db"))

    # Library Policy Settings
    LOAN_DURATION_DAYS = int(os.getenv("LOAN_DURATION_DAYS", 14))
    MAX_LOANS_PER_MEMBER = int(os.getenv("MAX_LOANS_PER_MEMBER", 3))
    FINE_RATE_PER_DAY = float(os.getenv("FINE_RATE_PER_DAY", 1.00))
    MAX_FINE_PER_LOAN = float(os.getenv("MAX_FINE_PER_LOAN", 50.00))
    MAX_UNPAID_FINE_LIMIT = float(os.getenv("MAX_UNPAID_FINE_LIMIT", 20.00))
    RESERVATION_HOLD_DAYS = int(os.getenv("RESERVATION_HOLD_DAYS", 3))
    CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")

    # Security & Session Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    DATABASE_PATH = ":memory:"  # or temporary file in tests


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
