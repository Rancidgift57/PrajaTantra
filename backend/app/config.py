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
    # API
    api_title: str = os.getenv(
        "PRAJATANTRA_API_TITLE",
        "Prajatantra Simulation API"
    )

    # Frontend
    frontend_origin: str = os.getenv(
        "FRONTEND_ORIGIN",
        "http://localhost:3000"
    )

    # Optional: comma-separated list of frontend URLs
    frontend_origins_raw: str = os.getenv(
        "FRONTEND_ORIGINS",
        ""
    )

    # PostgreSQL
    database_url: str | None = os.getenv("DATABASE_URL")

    # Neo4j
    neo4j_uri: str | None = os.getenv("NEO4J_URI")
    neo4j_username: str | None = os.getenv("NEO4J_USERNAME")
    neo4j_password: str | None = os.getenv("NEO4J_PASSWORD")
    neo4j_database: str = os.getenv(
        "NEO4J_DATABASE",
        "neo4j"
    )

    @property
    def database_enabled(self) -> bool:
        return bool(self.database_url)

    @property
    def neo4j_enabled(self) -> bool:
        return bool(
            self.neo4j_uri
            and self.neo4j_username
            and self.neo4j_password
        )

    @property
    def frontend_origins(self) -> list[str]:
        origins = []

        # Add comma-separated origins from FRONTEND_ORIGINS
        if self.frontend_origins_raw:
            origins.extend(
                origin.strip()
                for origin in self.frontend_origins_raw.split(",")
                if origin.strip()
            )

        # Add FRONTEND_ORIGIN
        if self.frontend_origin:
            origins.append(self.frontend_origin)

        # Local development URLs
        origins.extend([
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ])

        # Remove duplicates while preserving order
        seen = set()
        unique_origins = []

        for origin in origins:
            if origin not in seen:
                seen.add(origin)
                unique_origins.append(origin)

        return unique_origins


settings = Settings()
