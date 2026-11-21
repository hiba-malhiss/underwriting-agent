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

    # The private container application documents go in (created in the Portal)
    storage_container: str = "underwriting-documents"

    # The largest document accepted, per file
    max_upload_mb: int = Field(default=20, gt=0)

    @model_validator(mode="after")
    def storage_configured(self) -> "Settings":
        if not self.azure_storage_account_url:
            raise ValueError("Set AZURE_STORAGE_ACCOUNT_URL (Azure)")
        return self


settings = Settings()
