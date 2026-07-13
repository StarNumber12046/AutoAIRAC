"""Application configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

SimulatorId = Literal["xplane12", "msfs2020", "msfs2024", "p3d5", "fsx"]


class PathsConfig(BaseModel):
    xplane12: str = ""
    msfs2020_community: str = ""
    msfs2024_community: str = ""
    p3d5: str = ""
    fsx: str = ""


class RuTrackerConfig(BaseModel):
    base_url: str = "https://rutracker.org"
    username: str = ""
    password: str = ""
    search_query: str = "Navigraph AIRAC {cycle}"
    topic_id: int | None = None


class QBittorrentConfig(BaseModel):
    host: str = "http://127.0.0.1:8080"
    username: str = "admin"
    password: str = "adminadmin"
    download_category: str = "AutoAIRAC"
    save_path: str = ""


class NotificationsConfig(BaseModel):
    app_id: str = "AutoAIRAC"
    enabled: bool = True


class SimulatorsConfig(BaseModel):
    enabled: list[SimulatorId] = Field(default_factory=lambda: ["xplane12"])


class AppConfig(BaseModel):
    simulators: SimulatorsConfig = Field(default_factory=SimulatorsConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    rutracker: RuTrackerConfig = Field(default_factory=RuTrackerConfig)
    qbittorrent: QBittorrentConfig = Field(default_factory=QBittorrentConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    staging_dir: str = "%LOCALAPPDATA%/AutoAIRAC/staging"
    watch_interval_minutes: int = 1440

    def resolved_staging_dir(self) -> Path:
        return Path(os.path.expandvars(self.staging_dir)).expanduser()


def _expand_path(value: str) -> Path | None:
    if not value:
        return None
    return Path(os.path.expandvars(value)).expanduser()


def load_config(path: Path | None = None) -> AppConfig:
    """Load YAML config from disk, falling back to defaults."""
    if path is None:
        path = Path("config.yaml")
    if not path.exists():
        return AppConfig()
    with path.open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)


class Settings(BaseSettings):
    """Optional environment-variable overrides."""

    config_path: Path = Path("config.yaml")