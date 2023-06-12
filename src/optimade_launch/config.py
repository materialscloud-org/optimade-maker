"""All the profiles and their configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from uuid import uuid4

import toml

from .profile import Profile

@dataclass
class Config:
    profiles: list[Profile] = field(default_factory=lambda: [Profile()])
    
    @classmethod
    def load(cls, path: Path) -> Config:
        return cls.loads(path.read_text())
    
    def dumps(self) -> str:
        config = asdict(self)
        config["profiles"] = {
            profile.pop("name"): profile for profile in config.pop("profiles", [])
        }
        return toml.dumps(config)
    
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