"""Uniformity Score Calculator"""
import math
from typing import List, Tuple

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