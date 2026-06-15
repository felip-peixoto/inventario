from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=False)

    # Banco / serial
    database_url: str
    serial_port: str
    serial_baud: int = 115200

    # Lógica de inventário
    weight_stability_samples: int = 3
    weight_stability_tolerance_g: Decimal = Decimal("2.0")
    rounding_tolerance_units: Decimal = Decimal("0.4")
    empty_scale_tolerance_g: Decimal = Decimal("5.0")
    device_timeout_s: int = 5
