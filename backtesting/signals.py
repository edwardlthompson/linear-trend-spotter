"""Signal generation for backtesting indicators."""

from __future__ import annotations

from typing import Tuple

import pandas as pd

try:
    import talib
except Exception:  # pragma: no cover - optional fallback path
    talib = None


def _cross_above(left: pd.Series, right: pd.Series) -> pd.Series:
    return (left > right) & (left.shift(1) <= right.shift(1))


def _cross_below(left: pd.Series, right: pd.Series) -> pd.Series:
    return (left < right) & (left.shift(1) >= right.shift(1))


def _edge_true(condition: pd.Series) -> pd.Series:
    condition = condition.fillna(False).astype(bool)
    return condition & (~condition.shift(1, fill_value=False))


def _require_ohlcv(frame: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "volume"}
    if set(frame.columns) != required:
        raise ValueError("frame must contain open/high/low/close/volume")


def _safe_bool_signals(buy: pd.Series, sell: pd.Series, index: pd.Index) -> Tuple[pd.Series, pd.Series]:
    buy = buy.reindex(index).fillna(False).astype(bool)
    sell = sell.reindex(index).fillna(False).astype(bool)
    return buy, sell


def _rsi(close: pd.Series, period: int) -> pd.Series:
    if talib is not None:
        return pd.Series(talib.RSI(close.values, timeperiod=period), index=close.index)

    delta = close.diff()
    gains = delta.clip(lower=0.0)
    losses = -delta.clip(upper=0.0)
    avg_gain = gains.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.astype(float)


def rsi_signals(frame: pd.DataFrame, period: int = 14, lower: float = 30, upper: float = 70) -> Tuple[pd.Series, pd.Series]:
    close = frame["close"].astype(float)
    rsi = _rsi(close, period)

    lower_series = pd.Series(lower, index=frame.index)
    upper_series = pd.Series(upper, index=frame.index)

    buy = _cross_below(rsi, lower_series)
    sell = _cross_above(rsi, upper_series)
    return buy.fillna(False), sell.fillna(False)


def ema_crossover_signals(frame: pd.DataFrame, short_period: int = 12, long_period: int = 26) -> Tuple[pd.Series, pd.Series]:
    close = frame["close"].astype(float)
    short_ema = close.ewm(span=short_period, adjust=False, min_periods=short_period).mean()
    long_ema = close.ewm(span=long_period, adjust=False, min_periods=long_period).mean()

    buy = _cross_above(short_ema, long_ema)
    sell = _cross_below(short_ema, long_ema)
    return buy.fillna(False), sell.fillna(False)


def sma_crossover_signals(frame: pd.DataFrame, short_period: int = 20, long_period: int = 50) -> Tuple[pd.Series, pd.Series]:
    close = frame["close"].astype(float)
    short_sma = close.rolling(window=short_period, min_periods=short_period).mean()
    long_sma = close.rolling(window=long_period, min_periods=long_period).mean()

    buy = _cross_above(short_sma, long_sma)
    sell = _cross_below(short_sma, long_sma)
    return buy.fillna(False), sell.fillna(False)


def stochastic_signals(
    frame: pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
    smooth: int = 3,
    oversold: float = 20,
    overbought: float = 80,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    if talib is None:
        raise ValueError("TA-Lib required for stochastic_signals")

    k_line, d_line = talib.STOCH(
        frame["high"].values,
        frame["low"].values,
        frame["close"].values,
        fastk_period=k_period,
        slowk_period=smooth,
        slowk_matype=0,
        slowd_period=d_period,
        slowd_matype=0,
    )
    k = pd.Series(k_line, index=frame.index)
    d = pd.Series(d_line, index=frame.index)

    buy = _cross_above(k, d) & (k < oversold)
    sell = _cross_below(k, d) & (k > overbought)
    return _safe_bool_signals(buy, sell, frame.index)


def macd_signals(
    frame: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    close = frame["close"].astype(float)

    if talib is not None:
        macd_line, signal_line, _ = talib.MACD(
            close.values,
            fastperiod=fast_period,
            slowperiod=slow_period,
            signalperiod=signal_period,
        )
        macd_series = pd.Series(macd_line, index=frame.index)
        signal_series = pd.Series(signal_line, index=frame.index)
    else:
        fast_ema = close.ewm(span=fast_period, adjust=False).mean()
        slow_ema = close.ewm(span=slow_period, adjust=False).mean()
        macd_series = fast_ema - slow_ema
        signal_series = macd_series.ewm(span=signal_period, adjust=False).mean()

    buy = _cross_above(macd_series, signal_series)
    sell = _cross_below(macd_series, signal_series)
    return _safe_bool_signals(buy, sell, frame.index)


def bollinger_percent_b_signals(
    frame: pd.DataFrame,
    period: int = 20,
    std_dev: float = 2.0,
    buy_threshold: float = 0.2,
    sell_threshold: float = 0.8,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    close = frame["close"].astype(float)

    if talib is not None:
        upper, middle, lower = talib.BBANDS(
            close.values,
            timeperiod=period,
            nbdevup=std_dev,
            nbdevdn=std_dev,
            matype=0,
        )
        upper_s = pd.Series(upper, index=frame.index)
        lower_s = pd.Series(lower, index=frame.index)
    else:
        middle = close.rolling(window=period, min_periods=period).mean()
        sigma = close.rolling(window=period, min_periods=period).std()
        upper_s = middle + std_dev * sigma
        lower_s = middle - std_dev * sigma

    band_width = (upper_s - lower_s).replace(0, pd.NA)
    percent_b = (close - lower_s) / band_width

    buy = _cross_above(percent_b, pd.Series(buy_threshold, index=frame.index))
    sell = _cross_below(percent_b, pd.Series(sell_threshold, index=frame.index))
    return _safe_bool_signals(buy, sell, frame.index)


def cci_signals(
    frame: pd.DataFrame,
    period: int = 20,
    oversold: float = -100,
    overbought: float = 100,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    if talib is None:
        raise ValueError("TA-Lib required for cci_signals")

    cci = talib.CCI(
        frame["high"].values,
        frame["low"].values,
        frame["close"].values,
        timeperiod=period,
    )
    cci_s = pd.Series(cci, index=frame.index)

    buy = _cross_above(cci_s, pd.Series(oversold, index=frame.index))
    sell = _cross_below(cci_s, pd.Series(overbought, index=frame.index))
    return _safe_bool_signals(buy, sell, frame.index)


def ultimate_oscillator_signals(
    frame: pd.DataFrame,
    short_period: int = 7,
    medium_period: int = 14,
    long_period: int = 28,
    oversold: float = 30,
    overbought: float = 70,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    if talib is None:
        raise ValueError("TA-Lib required for ultimate_oscillator_signals")

    ult = talib.ULTOSC(
        frame["high"].values,
        frame["low"].values,
        frame["close"].values,
        timeperiod1=short_period,
        timeperiod2=medium_period,
        timeperiod3=long_period,
    )
    ult_s = pd.Series(ult, index=frame.index)

    buy = _cross_above(ult_s, pd.Series(oversold, index=frame.index))
    sell = _cross_below(ult_s, pd.Series(overbought, index=frame.index))
    return _safe_bool_signals(buy, sell, frame.index)


def mfi_signals(
    frame: pd.DataFrame,
    period: int = 14,
    lower: float = 20,
    upper: float = 80,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    if talib is None:
        raise ValueError("TA-Lib required for mfi_signals")

    volume = frame["volume"].astype(float)
    if (volume <= 0).all():
        reason = pd.Series(False, index=frame.index)
        return reason, reason

    mfi = talib.MFI(
        frame["high"].values,
        frame["low"].values,
        frame["close"].values,
        volume.values,
        timeperiod=period,
    )
    mfi_s = pd.Series(mfi, index=frame.index)

    buy = _cross_above(mfi_s, pd.Series(lower, index=frame.index))
    sell = _cross_below(mfi_s, pd.Series(upper, index=frame.index))
    return _safe_bool_signals(buy, sell, frame.index)


def adx_signals(
    frame: pd.DataFrame,
    period: int = 14,
    adx_threshold: float = 20,
    di_diff_min: float = 3,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    if talib is None:
        raise ValueError("TA-Lib required for adx_signals")

    high = frame["high"].values
    low = frame["low"].values
    close = frame["close"].values

    adx = pd.Series(talib.ADX(high, low, close, timeperiod=period), index=frame.index)
    plus_di = pd.Series(talib.PLUS_DI(high, low, close, timeperiod=period), index=frame.index)
    minus_di = pd.Series(talib.MINUS_DI(high, low, close, timeperiod=period), index=frame.index)

    up_condition = (adx >= adx_threshold) & ((plus_di - minus_di) >= di_diff_min)
    down_condition = (adx >= adx_threshold) & ((minus_di - plus_di) >= di_diff_min)

    buy = _edge_true(up_condition)
    sell = _edge_true(down_condition)
    return _safe_bool_signals(buy, sell, frame.index)


def parabolic_sar_signals(
    frame: pd.DataFrame,
    accel_step: float = 0.02,
    max_step: float = 0.2,
) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)
    if talib is None:
        raise ValueError("TA-Lib required for parabolic_sar_signals")

    sar = pd.Series(
        talib.SAR(frame["high"].values, frame["low"].values, acceleration=accel_step, maximum=max_step),
        index=frame.index,
    )
    close = frame["close"].astype(float)

    buy = _cross_above(close, sar)
    sell = _cross_below(close, sar)
    return _safe_bool_signals(buy, sell, frame.index)


def heikin_ashi_signals(frame: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    _require_ohlcv(frame)

    ha_close = (frame["open"] + frame["high"] + frame["low"] + frame["close"]) / 4.0
    ha_open = ha_close.copy()

    if len(frame.index) > 0:
        ha_open.iloc[0] = (frame["open"].iloc[0] + frame["close"].iloc[0]) / 2.0
        for i in range(1, len(frame.index)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2.0

    bullish = ha_close > ha_open
    bearish = ha_close < ha_open

    buy = _edge_true(bullish)
    sell = _edge_true(bearish)
    return _safe_bool_signals(buy, sell, frame.index)


SIGNAL_REGISTRY = {
    "RSI": rsi_signals,
    "Stochastic": stochastic_signals,
    "MACD": macd_signals,
    "EMA Crossover": ema_crossover_signals,
    "SMA Crossover": sma_crossover_signals,
    "Bollinger %B": bollinger_percent_b_signals,
    "CCI": cci_signals,
    "Ultimate Oscillator": ultimate_oscillator_signals,
    "MFI": mfi_signals,
    "ADX": adx_signals,
    "Parabolic SAR": parabolic_sar_signals,
    "Heikin Ashi": heikin_ashi_signals,
}


def generate_indicator_signals(
    indicator: str,
    frame: pd.DataFrame,
    params: dict | None = None,
) -> Tuple[pd.Series, pd.Series]:
    if indicator not in SIGNAL_REGISTRY:
        raise ValueError(f"Unknown indicator: {indicator}")

    fn = SIGNAL_REGISTRY[indicator]
    kwargs = params or {}
    return fn(frame, **kwargs)
