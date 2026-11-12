from pathlib import Path

import pytest
from src.config import load_config


@pytest.fixture
def config():
    # Isolate tests from the user's active model/plot configuration.
    c = load_config(
        Path(__file__).parents[1] / "config.example-csv.toml",
        check_input=False,
        create_outputs=False,
    )
    c["comsol"]["mode"] = "mph"
    return c
