"""All the profiles and their configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from uuid import uuid4
from copy import deepcopy

import toml

from .profile import Profile

MAIN_PROFILE_NAME = "default"
@dataclass
class Config:
    profiles: list[Profile] = field(default_factory=lambda: [Profile()])
    default_profile: str = MAIN_PROFILE_NAME
    
    # The configuration is always stored to disk beginning with version
    # 2023.1000, which means we assume that if no configuration is stored
    # we cannot make any assumptions about the latest applicable version.
    version: str | None = None
    
    @classmethod
    def load(cls, path: Path) -> Config:
        return cls.loads(path.read_text())
    
    def dumps(self) -> str:
        config = asdict(self)
        config["profiles"] = {
            profile.pop("name"): profile for profile in config.pop("profiles", [])
        }
        return toml.dumps(config)
    
    @classmethod
    def loads(cls, blob: str) -> Config:
        loaded_config = toml.loads(blob)
        config = deepcopy(loaded_config)
        config["profiles"] = []
        for name, profile in loaded_config.pop("profiles", dict()).items():
            config["profiles"].append(
                Profile(name=name, **profile)
            )
        return cls(**config)
    
    def save(self, path: Path, safe: bool = True) -> None:
        path.parent.mkdir(exist_ok=True, parents=True)
        if safe:
            path_tmp = path.with_suffix(f".{uuid4()!s}")
            path_tmp.write_text(self.dumps())
            path_tmp.replace(path)
        else:
            path.write_text(self.dumps())

    def get_profile(self, name: str) -> Profile:
        for profile in self.profiles:
            if profile.name == name:
                return profile
        raise ValueError(f"Did not find profile with name '{name}'.")