from dataclasses import dataclass, field

import pandas as pd


@dataclass
class Dataset:
    data: pd.DataFrame
    name: str
    source: str
    variables: list[str] = field(default_factory=list)
    units: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
