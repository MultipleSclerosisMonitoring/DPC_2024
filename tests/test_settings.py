from __future__ import annotations

from pathlib import Path

from msTools.settings import CONFIG_ENV_VAR, get_runtime_config_path, load_app_config


def test_load_app_config_prefers_env_values(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    env_path = tmp_path / ".env"

    config_path.write_text(
        """
influxdb:
  url: "https://yaml-host:8086"
  token: "yaml-token"
  org: "yaml-org"
  bucket: "yaml-bucket"
  measurement: "yaml-measurement"
  verify: false
  timeout: 900000

postgresql:
  host: "yaml-db"
  user: "yaml-user"
  password: "yaml-pass"
  database: "yaml-name"
  port: 5432

movement:
  resample_hz: 100.0
        """.strip(),
        encoding="utf-8",
    )
    env_path.write_text(
        """
INFLUXDB_URL=https://env-host:8086
POSTGRESQL_HOST=env-db
POSTGRESQL_PASSWORD=env-pass
        """.strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("INFLUXDB_BUCKET", "os-bucket")

    settings = load_app_config(config_path, env_path=env_path)

    assert settings.influxdb.url == "https://env-host:8086"
    assert settings.influxdb.bucket == "os-bucket"
    assert settings.postgresql.host == "env-db"
    assert settings.postgresql.password == "env-pass"
    assert settings.postgresql.user == "yaml-user"
    assert settings.movement.resample_hz == 100.0


def test_get_runtime_config_path_uses_env_override(monkeypatch) -> None:
    monkeypatch.setenv(CONFIG_ENV_VAR, "custom-config.yaml")

    assert get_runtime_config_path() == "custom-config.yaml"
