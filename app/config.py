from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    DEEPSEEK_API_KEY: str
    SESSION_SECRET: str = "dev-secret-key-change-me"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    BASE_URL: str = "http://localhost:8000"
    # Se vazio, o redirect do Google é derivado da própria requisição (mesmo host do navegador),
    # garantindo que o cookie de sessão (onde o "state" é gravado) chegue no callback.
    # Preencha apenas quando o app estiver atrás de proxy reverse com URL pública diferente.
    OAUTH_REDIRECT_BASE_URL: str = ""
    # Em modo debug, o callback do Google expõe o erro real em JSON em vez de redirecionar.
    OAUTH_DEBUG: bool = False

    class Config:
        env_file = '.env'

settings = Settings()
