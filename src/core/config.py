import os

class Settings:
    API_KEY = os.getenv("API_KEY", "default_key")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

try:
    settings = Settings()
except Exception as e:
    print(f"Error loading configuration: {e}")
    exit(1)