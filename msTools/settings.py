"""Typed application settings and runtime configuration helpers.

This module centralizes configuration loading for the repository. It supports a
hybrid model:

- ``config.yaml`` stores the structural project configuration and algorithm
  defaults.
- ``.env`` can override sensitive connection values and selected runtime
  options.

Environment variables always take precedence over ``.env`` values, which in
turn take precedence over the YAML file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict

DEFAULT_CONFIG_PATH = Path("config.yaml")
DEFAULT_ENV_PATH = Path(".env")
CONFIG_ENV_VAR = "MS_MONITORING_CONFIG"


class InfluxDBSettings(BaseModel):
    """Typed settings for the InfluxDB connection."""

    model_config = ConfigDict(extra="forbid")

    url: str
    token: str
    org: str
    bucket: str
    measurement: str
    verify: bool = False
    timeout: int = 900_000


class PostgreSQLSettings(BaseModel):
    """Typed settings for the PostgreSQL connection."""

    model_config = ConfigDict(extra="forbid")

    host: str
    user: str
    password: str
    database: str
    port: int = 5432


class MovementSettings(BaseModel):
    """Typed movement and gait configuration."""

    model_config = ConfigDict(extra="forbid")

    accel_threshold: float = 0.2
    gyro_threshold: float = 60.0
    accel_power_threshold: float = 0.125
    gyro_power_threshold: float = 1_000.0
    freq_band_min: float = 0.4
    freq_band_max: float = 1.6
    min_continuous_hits: int = 3
    sampling_rate: float = 47.0
    resample_hz: float = 100.0
    window_size_samples: int = 256
    min_window_fraction: float = 0.5
    min_effective_duration_sec: float = 6.0
    min_gait_duration_sec: float = 6.0
    gps_resample_seconds: int = 10
    gps_padding_seconds: int = 15
    gps_min_points: int = 2
    gps_min_distance_m: float = 3.0
    gps_min_speed_m_s: float = 0.2
    gps_max_speed_m_s: float = 3.0


class AppConfig(BaseModel):
    """Aggregate validated application settings."""

    model_config = ConfigDict(extra="forbid")

    influxdb: InfluxDBSettings
    postgresql: PostgreSQLSettings
    movement: MovementSettings


def get_runtime_config_path(explicit_path: str | Path | None = None) -> str:
    """Resolve the configuration path for the current process.

    Args:
        explicit_path: Optional path supplied by the caller.

    Returns:
        The configuration path to use, as a string.
    """
    if explicit_path is not None:
        return str(explicit_path)

    env_path = os.getenv(CONFIG_ENV_VAR)
    if env_path:
        return env_path

    return str(DEFAULT_CONFIG_PATH)


def _read_yaml_config(config_path: str | Path) -> dict[str, Any]:
    """Read a YAML configuration file into a plain dictionary."""
    path = Path(config_path)
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Configuration file must contain a mapping: {path}")
    return data


def _resolve_value(
    yaml_section: dict[str, Any],
    yaml_key: str,
    env_key: str,
    env_values: dict[str, str],
) -> Any:
    """Resolve one configuration value with env-over-yaml precedence."""
    if env_key in os.environ:
        return os.environ[env_key]
    if env_key in env_values and env_values[env_key] not in (None, ""):
        return env_values[env_key]
    return yaml_section.get(yaml_key)


def load_app_config(
    config_path: str | Path,
    *,
    env_path: str | Path = DEFAULT_ENV_PATH,
) -> AppConfig:
    """Load and validate runtime configuration.

    Args:
        config_path: Path to the YAML configuration file.
        env_path: Path to the optional ``.env`` file.

    Returns:
        A validated :class:`AppConfig` instance.
    """
    yaml_data = _read_yaml_config(config_path)
    env_values = {
        key: str(value)
        for key, value in dotenv_values(env_path).items()
        if value is not None
    }

    influx_yaml = yaml_data.get("influxdb", {}) or {}
    postgres_yaml = yaml_data.get("postgresql", {}) or {}
    movement_yaml = yaml_data.get("movement", {}) or {}

    return AppConfig(
        influxdb=InfluxDBSettings(
            url=_resolve_value(influx_yaml, "url", "INFLUXDB_URL", env_values),
            token=_resolve_value(influx_yaml, "token", "INFLUXDB_TOKEN", env_values),
            org=_resolve_value(influx_yaml, "org", "INFLUXDB_ORG", env_values),
            bucket=_resolve_value(influx_yaml, "bucket", "INFLUXDB_BUCKET", env_values),
            measurement=_resolve_value(
                influx_yaml,
                "measurement",
                "INFLUXDB_MEASUREMENT",
                env_values,
            ),
            verify=_resolve_value(influx_yaml, "verify", "INFLUXDB_VERIFY", env_values),
            timeout=_resolve_value(influx_yaml, "timeout", "INFLUXDB_TIMEOUT", env_values),
        ),
        postgresql=PostgreSQLSettings(
            host=_resolve_value(postgres_yaml, "host", "POSTGRESQL_HOST", env_values),
            user=_resolve_value(postgres_yaml, "user", "POSTGRESQL_USER", env_values),
            password=_resolve_value(
                postgres_yaml,
                "password",
                "POSTGRESQL_PASSWORD",
                env_values,
            ),
            database=_resolve_value(
                postgres_yaml,
                "database",
                "POSTGRESQL_DATABASE",
                env_values,
            ),
            port=_resolve_value(postgres_yaml, "port", "POSTGRESQL_PORT", env_values),
        ),
        movement=MovementSettings(**movement_yaml),
    )
