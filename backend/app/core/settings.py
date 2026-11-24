from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    # Sign-in to Azure. from browser for local test
    azure_interactive_login: bool = Field(default=False, validation_alias="AZURE_INTERACTIVE_LOGIN")
    azure_tenant_id: str | None = Field(default=None, validation_alias="AZURE_TENANT_ID")

    # storage setting endpoint
    azure_storage_account_url: str | None = Field(
        default=None, validation_alias="AZURE_STORAGE_ACCOUNT_URL"
    )

    # The private container for each kind of document (created in the Portal):
    # applicants' documents, and the underwriting guidelines (requirements)
    applicant_container: str = "underwriting-documents"
    requirements_container: str = "requirements"

    # AI Search: Search service → Overview → Url. Optional: without it, nothing is re-indexed
    # on upload/delete and the indexers only run on their schedule.
    azure_search_endpoint: str | None = Field(
        default=None, validation_alias="AZURE_SEARCH_ENDPOINT"
    )
    # The indexer that reads each container (AI Search → Indexers). Unset = not re-indexed.
    applicant_indexer: str | None = Field(default=None, validation_alias="APPLICANT_INDEXER")
    requirements_indexer: str | None = Field(default=None, validation_alias="REQUIREMENTS_INDEXER")

    # MySQL (Azure Database for MySQL – Flexible Server). Optional: without it, the rulebook
    # can't be saved. No password: the app signs in with an Entra token (see database.py)
    mysql_host: str | None = Field(default=None, validation_alias="MYSQL_HOST")
    mysql_database: str = Field(default="underwriting", validation_alias="MYSQL_DATABASE")
    # The Entra user to sign in as: locally your user's principal name (Entra ID → Users →
    # User principal name); on Azure, the Managed Identity's MySQL user
    mysql_user: str | None = Field(default=None, validation_alias="MYSQL_USER")

    # The largest document accepted, per file
    max_upload_mb: int = Field(default=20, gt=0)

    @model_validator(mode="after")
    def storage_configured(self) -> "Settings":
        if not self.azure_storage_account_url:
            raise ValueError("Set AZURE_STORAGE_ACCOUNT_URL (Azure)")
        return self


settings = Settings()
