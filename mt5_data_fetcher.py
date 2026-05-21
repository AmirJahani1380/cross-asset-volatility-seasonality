"""
MT5 Data Fetcher

Fetches historical candles from MetaTrader 5 and saves them as CSV files.

Requirements:
    pip install MetaTrader5 pandas numpy

Important:
    - Run this on the same machine where MetaTrader 5 is installed.
    - Open MT5 and log in to your broker account before running.
    - Make sure the symbol is visible in Market Watch.

Example:
    python mt5_data_fetcher.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import MetaTrader5 as mt5


TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}


def initialize_mt5(path: str | None = None) -> None:
    """Initialize MT5 connection."""
    if path:
        ok = mt5.initialize(path=path)
    else:
        ok = mt5.initialize()

    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")


def shutdown_mt5() -> None:
    """Close MT5 connection."""
    mt5.shutdown()


def ensure_symbol(symbol: str) -> None:
    """Make sure symbol is available and selected in Market Watch."""
    info = mt5.symbol_info(symbol)
    if info is None:
        raise ValueError(f"Symbol not found in MT5: {symbol}")

    if not info.visible:
        selected = mt5.symbol_select(symbol, True)
        if not selected:
            raise RuntimeError(f"Could not select symbol in Market Watch: {symbol}")


def compute_ema(series: pd.Series, period: int = 20) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)

    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def fetch_rates(symbol: str, timeframe: str, max_bars: int = 100_000) -> pd.DataFrame:
    """
    Fetch latest historical candles from MT5.

    Parameters
    ----------
    symbol:
        Broker symbol, e.g. "XAUUSDzero", "EURUSD", "GBPUSD".
    timeframe:
        One of: M1, M5, M15, M30, H1, H4, D1.
    max_bars:
        Number of bars to request from MT5.
    """
    timeframe = timeframe.upper()
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Use one of {list(TIMEFRAMES)}")

    ensure_symbol(symbol)

    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAMES[timeframe], 0, max_bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No data returned for {symbol} {timeframe}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    # Keep standard MT5 OHLCV columns first.
    base_cols = ["time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
    df = df[base_cols].copy()

    # Extra analysis-friendly columns matching your existing datasets.
    df["range"] = df["high"] - df["low"]
    df["body"] = (df["close"] - df["open"]).abs()
    df["weekday"] = df["time"].dt.day_name()
    df["ema20"] = compute_ema(df["close"], 20)
    df["atr14"] = compute_atr(df, 14)

    return df


def save_rates_csv(
    symbol: str,
    timeframe: str,
    max_bars: int = 100_000,
    output_dir: str | os.PathLike[str] = "mt5_data",
) -> Path:
    """Fetch one symbol/timeframe and save it to CSV."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df = fetch_rates(symbol=symbol, timeframe=timeframe, max_bars=max_bars)

    file_path = output_path / f"{symbol}_{timeframe}_max_bars.csv"
    df.to_csv(file_path, index=False)

    print(f"Saved {len(df):,} rows -> {file_path}")
    print(f"First candle: {df['time'].min()}")
    print(f"Last candle:  {df['time'].max()}")

    return file_path


def fetch_multiple_timeframes(
    symbol: str,
    timeframes: Iterable[str] = ("M1", "M5", "D1"),
    max_bars: int = 100_000,
    output_dir: str | os.PathLike[str] = "mt5_data",
) -> list[Path]:
    """Fetch several timeframes for one asset."""
    saved_files = []
    for tf in timeframes:
        saved_files.append(
            save_rates_csv(
                symbol=symbol,
                timeframe=tf,
                max_bars=max_bars,
                output_dir=output_dir,
            )
        )
    return saved_files


if __name__ == "__main__":
    # Edit these values for another asset.
    SYMBOL = "AUDUSDzero"
    TIMEFRAMES_TO_FETCH = ["D1"]
    MAX_BARS = 90_000
    OUTPUT_DIR = "mt5_data"

    # Optional: set your terminal path if mt5.initialize() cannot find it automatically.
    # Example:
    # MT5_PATH = r"C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    MT5_PATH = None

    try:
        initialize_mt5(path=MT5_PATH)
        fetch_multiple_timeframes(
            symbol=SYMBOL,
            timeframes=TIMEFRAMES_TO_FETCH,
            max_bars=MAX_BARS,
            output_dir=OUTPUT_DIR,
        )
    finally:
        shutdown_mt5()
