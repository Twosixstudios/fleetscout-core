import os

class Settings:
    API_KEY: str = os.getenv("API_KEY", "default_key")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./test.db")

    def get_database_url(self) -> str:
        return self.DATABASE_URL

try:
    settings = Settings()
except Exception as e:
    print(f"Error loading configuration: {e}")
    exit(1)
