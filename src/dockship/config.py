from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    dockship_api_key: str
    github_webhook_secret: str
    db_path: str = "./dockship.db"
    nginx_conf_dir: str = "/etc/nginx/conf.d/dockship"
    port_min: int = 9000
    port_max: int = 9099
    health_tries: int = 10
    health_interval_s: int = 3
    drain_s: int = 5

    @field_validator("dockship_api_key", "github_webhook_secret")
    @classmethod
    def reject_placeholders(cls, value: str) -> str:
        if not value or value == "change-me" or len(value) < 8:
            raise ValueError("secret must be at least 8 characters and not 'change-me'")
        return value


settings = Settings()
