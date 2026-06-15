from decimal import Decimal
from inventario.config import Settings


def test_defaults_quando_so_database_url_e_serial_port_definidos(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/inv")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyUSB0")
    s = Settings()
    assert s.serial_baud == 115200
    assert s.weight_stability_samples == 3
    assert s.weight_stability_tolerance_g == Decimal("2.0")
    assert s.rounding_tolerance_units == Decimal("0.4")
    assert s.empty_scale_tolerance_g == Decimal("5.0")
    assert s.device_timeout_s == 5


def test_le_overrides_do_ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db:5432/inv")
    monkeypatch.setenv("SERIAL_PORT", "/dev/ttyACM0")
    monkeypatch.setenv("SERIAL_BAUD", "9600")
    monkeypatch.setenv("WEIGHT_STABILITY_SAMPLES", "5")
    s = Settings()
    assert s.serial_port == "/dev/ttyACM0"
    assert s.serial_baud == 9600
    assert s.weight_stability_samples == 5
