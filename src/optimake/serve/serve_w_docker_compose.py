import json
from pathlib import Path

import yaml


class OptimakeServer:
    def __init__(self, port: int, path: Path):
        self.port = port
        self.label = "qwerty"
        self.path = path

        self.base_url = "http://localhost:5000"
        self.index_base_url = "http://localhost:5001"

    def _provider_info(self):
        return {
            "prefix": "optimake",
            "name": "Optimake",
            "description": "Provider created with optimake",
            "homepage": "https://github.com/materialscloud-org/optimade-maker",
            "index_base_url": self.index_base_url,
        }

    def write_optimade_config_file(self):
        provider_fields = []

        config_dict = {
            "debug": False,
            "insert_test_data": False,
            "base_url": self.base_url,
            "provider": self._provider_info(),
            "index_base_url": self.index_base_url,
            "provider_fields": {"structures": provider_fields},
        }

        with open(self.path / "optimade-config.json", "w") as file:
            json.dump(config_dict, file, indent=2)

    def write_docker_compose_yml(self):
        docker_compose_dict = {
            "services": {
                f"optimade_{self.label}": {
                    "container_name": f"optimade_{self.label}",
                    "restart": "always",
                    "image": "ghcr.io/materials-consortia/optimade:0.25.3",
                    "ports": [f"{self.port}:5000"],
                    "volumes": ["./optimade-config.json:/ext/optimade-config.json"],
                    "environment": ["OPTIMADE_CONFIG_FILE=/ext/optimade-config.json"],
                }
            },
        }

        yaml_content = yaml.dump(
            docker_compose_dict, default_flow_style=False, sort_keys=False
        )

        with open(self.path / "docker-compose.yml", "w") as file:
            file.write(yaml_content)


def serve_archive(path):
    print(path)
    optimake_server = OptimakeServer(5000, Path(path))

    optimake_server.write_optimade_config_file()
    optimake_server.write_docker_compose_yml()
