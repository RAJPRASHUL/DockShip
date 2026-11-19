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


settings = Settings()
