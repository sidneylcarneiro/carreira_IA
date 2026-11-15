from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    DEEPSEEK_API_KEY: str
    SESSION_SECRET: str = "dev-secret-key-change-me"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    BASE_URL: str = "http://localhost:8000"

    class Config:
        env_file = '.env'

settings = Settings()