from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> None:
        return None


load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_title: str = os.getenv("PRAJATANTRA_API_TITLE", "Prajatantra Simulation API")
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    neo4j_uri: str | None = os.getenv("NEO4J_URI")
    neo4j_username: str | None = os.getenv("NEO4J_USERNAME")
    neo4j_password: str | None = os.getenv("NEO4J_PASSWORD")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    database_url: str | None = os.getenv("DATABASE_URL")

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_username and self.neo4j_password)

    @property
    def database_enabled(self) -> bool:
        return bool(self.database_url)


    # app/config.py — new frontend_origins property
    @property
    def frontend_origins(self) -> list[str]:
        explicit = [o.strip() for o in self.frontend_origins_raw.split(",") if o.strip()]
        defaults = [self.frontend_origin, "http://localhost:3000", "http://127.0.0.1:3000"]
        seen: set[str] = set()
        origins: list[str] = []
        for origin in [*explicit, *defaults]:
            if origin and origin not in seen:
                seen.add(origin)
                origins.append(origin)
        return origins


settings = Settings()
