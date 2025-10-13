# logging.py
from __future__ import annotations
import logging
import logging.config
from pathlib import Path

import yaml


def setup_logging(yaml_path: str | None = None) -> None:
    """Centralized logging config (YAML). Falls back to basicConfig."""
    if yaml_path and Path(yaml_path).exists():
        cfg = yaml.safe_load(Path(yaml_path).read_text())
        logging.config.dictConfig(cfg)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s :: %(message)s"
        )
