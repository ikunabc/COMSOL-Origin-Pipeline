"""Small CLI; adapters contain application-specific operations."""

import argparse
import sys
from pathlib import Path

from src.config import load_config
from src.exceptions import PipelineError
from src.logger import setup_logging


def main(argv=None):
    parser = argparse.ArgumentParser(description="COMSOL → Python → Origin automated plotting")
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.toml")))
    modes = parser.add_mutually_exclusive_group()
    for flag in ("check", "dry-run", "list-results"):
        modes.add_argument("--" + flag, action="store_true")
    args = parser.parse_args(argv)
    log = setup_logging(Path(__file__).parent)
    try:
        if sys.version_info < (3, 11):
            raise PipelineError("Python 3.11 or later is required.")
        log.info("Loading configuration...")
        config = load_config(
            args.config,
            check_input=not (args.dry_run or args.check),
            create_outputs=not (args.dry_run or args.check or args.list_results),
        )
        if args.check:
            from src.diagnostics import check

            check(config)
        elif args.dry_run:
            from src.pipeline import dry_run

            dry_run(config)
        elif args.list_results:
            from src.pipeline import list_results

            list_results(config)
        else:
            from src.pipeline import run

            run(config)
        return 0
    except PipelineError as exc:
        log.error("%s", exc, exc_info=True)
    except Exception as exc:
        log.error("Unexpected error: %s. See logs/pipeline.log for details.", exc, exc_info=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
