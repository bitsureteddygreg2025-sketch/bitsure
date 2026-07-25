"""CLI entrypoint for the Bitsure Teddy backtest simulator.

Usage:
    python -m backtest.simulator --config backtest/config_backtest.json
    python backtest/simulator.py --config backtest/configs/scalping.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .engine import BacktestConfig, BacktestEngine
else:
    from engine import BacktestConfig, BacktestEngine


def load_config(path: str) -> BacktestConfig:
    with Path(path).open("r", encoding="utf-8") as fh:
        return BacktestConfig.from_dict(json.load(fh))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an independent backtest of the current bot strategy.")
    parser.add_argument("--config", default="backtest/config_backtest.json", help="Path to a JSON backtest config file.")
    args = parser.parse_args()

    config = load_config(args.config)
    result = BacktestEngine(config).run()
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    print(f"Results written to: {result['results_dir']}")


if __name__ == "__main__":
    main()
