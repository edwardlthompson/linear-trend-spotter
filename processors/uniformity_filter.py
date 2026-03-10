"""Uniformity Score Calculator"""
import math
import statistics
from typing import List, Tuple, Dict, Any

class UniformityFilter:
    """Calculate uniformity score (0-100) for price action"""

    @staticmethod
    def calculate(prices: List[float], period: int = 30) -> Tuple[float, float]:
        """Calculate uniformity score"""
        if len(prices) < period:
            return 0, 0

        prices_period = prices[-period:]
        base_price = prices_period[0]

        if base_price <= 0:
            return 0, 0

        cumulative_pcts = []
        for price in prices_period:
            pct_change = ((price - base_price) / base_price) * 100
            cumulative_pcts.append(pct_change)

        total_gain = cumulative_pcts[-1]

        if total_gain <= 0:
            return 0, round(total_gain, 1)

        daily_uniform_gain = total_gain / (period - 1)
        ideal_line = [i * daily_uniform_gain for i in range(period)]

        total_deviation = 0
        max_possible_deviation = 0

        for i in range(period):
            deviation = abs(cumulative_pcts[i] - ideal_line[i])
            total_deviation += deviation
            max_possible_deviation += total_gain if i < period - 1 else 0

        if max_possible_deviation > 0:
            normalized_deviation = total_deviation / max_possible_deviation
        else:
            normalized_deviation = 0

        raw_score = 100 * (1 - math.sqrt(min(normalized_deviation, 1)))
        uniformity_score = min(100, max(0, round(raw_score, 1)))

        return uniformity_score, round(total_gain, 1)

    @staticmethod
    def get_score_category(score: float, gain: float) -> str:
        """Get descriptive category"""
        if gain <= 0:
            return "Negative Return 📉"
        elif score >= 90:
            return "Perfect 🏆"
        elif score >= 75:
            return "Excellent 📈"
        elif score >= 60:
            return "Good 📊"
        elif score >= 45:  # Changed from 40 to 45
            return "Fair 📉"
        elif score >= 20:
            return "Poor ⚠️"
        else:
            return "Bad ❌"

    @staticmethod
    def calculate_from_ohlcv(daily_bars: List[Dict[str, Any]], period: int = 30) -> Tuple[float, float]:
        """Calculate OHLCV-aware uniformity score from daily aggregated bars."""
        if len(daily_bars) < period:
            return 0, 0

        sliced = daily_bars[-period:]
        closes = [float(bar.get('close', 0.0)) for bar in sliced]
        trend_score, gain = UniformityFilter.calculate(closes, period)

        body_ratios = []
        bullish_flags = []
        range_values = []

        for bar in sliced:
            open_price = float(bar.get('open', 0.0))
            high_price = float(bar.get('high', 0.0))
            low_price = float(bar.get('low', 0.0))
            close_price = float(bar.get('close', 0.0))

            candle_range = max(1e-9, high_price - low_price)
            body = abs(close_price - open_price)
            body_ratios.append(body / candle_range)
            bullish_flags.append(1.0 if close_price >= open_price else 0.0)

            if open_price > 0:
                range_values.append((candle_range / open_price) * 100)

        body_score = statistics.mean(body_ratios) * 100 if body_ratios else 0.0
        bullish_score = statistics.mean(bullish_flags) * 100 if bullish_flags else 0.0

        if range_values:
            mean_range = statistics.mean(range_values)
            std_range = statistics.pstdev(range_values) if len(range_values) > 1 else 0.0
            range_stability_score = max(0.0, 100.0 - min(100.0, (std_range / max(0.1, mean_range)) * 100))
        else:
            range_stability_score = 0.0

        composite = (0.55 * trend_score) + (0.20 * body_score) + (0.15 * bullish_score) + (0.10 * range_stability_score)
        final_score = round(max(0.0, min(100.0, composite)), 1)
        return final_score, gain