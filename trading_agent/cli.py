from __future__ import annotations

import argparse
import json
from typing import Optional

from .backtest import run_from_config, trade_rows
from .config import load_config, sample_config
from .data import align_benchmark, load_bars, write_trades_csv
from .models import Market
from .runtime import PaperAgentRuntime, step_result_to_dict
from .state import JsonStateStore
from .strategy import ThreeMarketLongOnlyStrategy


def main() -> None:
    parser = argparse.ArgumentParser(description="Three-market long-only trading agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser("backtest", help="Run a CSV backtest")
    backtest_parser.add_argument("--config", required=True)
    backtest_parser.add_argument("--trades-out")

    signal_parser = subparsers.add_parser("signal", help="Print the latest bar signal")
    signal_parser.add_argument("--config", required=True)

    run_parser = subparsers.add_parser("run-once", help="Run one persistent paper-agent step")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--state", required=True)
    run_parser.add_argument("--allow-reprocess", action="store_true")

    reset_parser = subparsers.add_parser("reset-state", help="Delete a paper-agent state file")
    reset_parser.add_argument("--config", required=True)
    reset_parser.add_argument("--state", required=True)

    sample_parser = subparsers.add_parser("sample-config", help="Print a sample JSON config")
    sample_parser.add_argument("--market", choices=[m.value for m in Market], default=Market.US.value)

    args = parser.parse_args()
    if args.command == "backtest":
        _cmd_backtest(args.config, args.trades_out)
    elif args.command == "signal":
        _cmd_signal(args.config)
    elif args.command == "run-once":
        _cmd_run_once(args.config, args.state, args.allow_reprocess)
    elif args.command == "reset-state":
        _cmd_reset_state(args.config, args.state)
    elif args.command == "sample-config":
        print(json.dumps(sample_config(Market(args.market)), indent=2, ensure_ascii=False))


def _cmd_backtest(config_path: str, trades_out: Optional[str]) -> None:
    config = load_config(config_path)
    result = run_from_config(config)
    summary = {
        "initial_equity_usd": round(result.initial_equity_usd, 2),
        "final_equity_usd": round(result.final_equity_usd, 2),
        "total_return_pct": round(result.total_return_pct, 2),
        "max_drawdown_usd": round(result.max_drawdown_usd, 2),
        "trades": len(result.trades),
        "win_rate_pct": round(result.win_rate_pct, 2),
        "profit_factor": result.profit_factor if result.profit_factor != float("inf") else "inf",
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if trades_out:
        write_trades_csv(trades_out, trade_rows(result))


def _cmd_signal(config_path: str) -> None:
    config = load_config(config_path)
    bars = load_bars(config.data.bars_csv)
    benchmark = load_bars(config.data.benchmark_csv) if config.data.benchmark_csv else None
    aligned_benchmark = align_benchmark(bars, benchmark)
    strategy = ThreeMarketLongOnlyStrategy(config)
    features = strategy.prepare(bars, aligned_benchmark)
    latest_index = len(bars) - 1
    signal = strategy.entry_signal(
        latest_index,
        bars,
        features,
        equity_usd=config.risk.initial_capital_usd,
        day_start_equity_usd=config.risk.initial_capital_usd,
    )
    payload = {
        "timestamp": bars[-1].timestamp.isoformat(),
        "symbol": config.market.symbol,
        "action": signal.action.value,
        "reason": signal.reason,
        "quantity": signal.quantity,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "confidence": signal.confidence,
        "details": signal.details,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _cmd_run_once(config_path: str, state_path: str, allow_reprocess: bool) -> None:
    runtime = PaperAgentRuntime.from_files(config_path, state_path)
    result = runtime.run_once(allow_reprocess=allow_reprocess)
    print(json.dumps(step_result_to_dict(result), indent=2, ensure_ascii=False))


def _cmd_reset_state(config_path: str, state_path: str) -> None:
    config = load_config(config_path)
    JsonStateStore(state_path, config).reset()
    print(json.dumps({"state": state_path, "status": "reset"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
