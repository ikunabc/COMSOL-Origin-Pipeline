import logging
from pathlib import Path


class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        # The file handler retains the traceback; terminal shows the message only.
        return f"[{record.levelname}] {record.getMessage()}"


def setup_logging(root: Path):
    folder = root / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("pipeline")
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    disk = logging.FileHandler(folder / "pipeline.log", encoding="utf-8")
    disk.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(ConsoleFormatter())
    log.addHandler(disk)
    log.addHandler(console)
    return log
