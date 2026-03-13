"""
Notification message formatting
"""

from datetime import datetime
from typing import Dict, List
from config.constants import EXCHANGE_EMOJIS

class MessageFormatter:
    """Format notification messages per spec §10.1-10.2"""

    @staticmethod
    def _format_rank_change(status: str, delta: int | None) -> str:
        if status == 'up':
            amount = max(1, abs(int(delta or 0)))
            return f"↑{amount}"
        if status == 'down':
            amount = max(1, abs(int(delta or 0)))
            return f"↓{amount}"
        if status == 'flat':
            return "→"
        return "🆕"

    @staticmethod
    def _format_pct(value: float | None) -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):+.2f}%"
        return "n/a"

    @staticmethod
    def _format_score(value: float | None) -> str:
        if isinstance(value, (int, float)):
            return f"{float(value):.0f}/100"
        return "n/a"

    @staticmethod
    def _format_key_settings(params: Dict) -> str:
        if not params:
            return "none"

        key_aliases = {
            'period': 'p',
            'lower': 'lo',
            'upper': 'hi',
            'overbought': 'ob',
            'oversold': 'os',
            'fast_period': 'fast',
            'slow_period': 'slow',
            'signal_period': 'sig',
            'short_period': 'short',
            'long_period': 'long',
            'std_dev': 'std',
            'buy_threshold': 'buy<',
            'sell_threshold': 'sell>',
            'adx_threshold': 'adx>',
            'di_diff_min': 'diΔ>',
            'k_period': 'k',
            'd_period': 'd',
            'smooth': 'sm',
        }

        def compact_value(value):
            if isinstance(value, float):
                if value.is_integer():
                    return str(int(value))
                return f"{value:.4g}"
            return str(value)

        parts = []
        for key in sorted(params.keys()):
            label = key_aliases.get(key, key)
            parts.append(f"{label}={compact_value(params[key])}")

        compact = "; ".join(parts)
        if len(compact) > 56:
            return compact[:53] + "..."
        return compact

    @staticmethod
    def format_entry(coin: Dict) -> str:
        """
        Format entry notification per spec §10.1
        Returns HTML-formatted caption for Telegram photo
        """
        # Build CMC URL
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        
        # Get data
        symbol = coin['symbol']
        name = coin['name']
        gain_7d = coin['gains'].get('7d', 0)
        gain_30d = coin['gains'].get('30d', 0)
        score = coin.get('uniformity_score', 0)
        
        # Header with HTML link
        caption = f"🟢 <a href='{cmc_url}'>{symbol} ({name})</a>\n\n"
        
        # Gains section
        caption += f"📊 Gains:\n"
        caption += f"   7d: +{gain_7d:.1f}%\n"
        caption += f"   30d: +{gain_30d:.1f}%\n\n"
        
        # Uniformity score
        caption += f"📈 Uniformity Score: {score:.0f}/100\n"

        atr_score = coin.get('atr_score')
        atr_pct = coin.get('atr_pct')
        if isinstance(atr_score, (int, float)):
            if isinstance(atr_pct, (int, float)):
                caption += f"📏 ATR Score: {float(atr_score):.0f}/100 (ATR14: {float(atr_pct):.2f}%)\n"
            else:
                caption += f"📏 ATR Score: {float(atr_score):.0f}/100\n"

        health_score = coin.get('health_score')
        if isinstance(health_score, (int, float)):
            caption += f"🩺 Health Score: {float(health_score):.0f}/100"
            if coin.get('health_label'):
                caption += f" ({coin.get('health_label')})"
            caption += "\n"

        exchange_quality_score = coin.get('exchange_quality_score')
        if isinstance(exchange_quality_score, (int, float)):
            caption += f"🏦 Exchange Quality: {float(exchange_quality_score):.0f}/100"
            if coin.get('exchange_quality_label'):
                caption += f" ({coin.get('exchange_quality_label')})"
            caption += "\n"

        data_reliability_score = coin.get('data_reliability_score')
        if isinstance(data_reliability_score, (int, float)):
            caption += f"🧪 Data Reliability: {float(data_reliability_score):.0f}/100"
            if coin.get('data_reliability_label'):
                caption += f" ({coin.get('data_reliability_label')})"
            caption += "\n"

        caption += "\n"

        current_rank = coin.get('current_rank')
        previous_rank = coin.get('previous_rank')
        rank_status = coin.get('rank_status')
        rank_delta = coin.get('rank_delta')
        if isinstance(current_rank, int):
            if isinstance(previous_rank, int) and rank_status in {'up', 'down', 'flat'}:
                arrow = '↑' if rank_status == 'up' else '↓' if rank_status == 'down' else '→'
                change_text = '' if rank_delta in (None, 0) else f" ({abs(int(rank_delta))})"
                caption += f"🏁 Rank: #{current_rank} {arrow} from #{previous_rank}{change_text}\n"
            else:
                caption += f"🏁 Rank: #{current_rank} (new)\n"

        signal_age_label = coin.get('signal_age_label')
        signal_indicator = coin.get('signal_age_indicator')
        if signal_age_label and signal_indicator:
            caption += f"⏱️ Best Strategy Signal: {signal_indicator} • {signal_age_label}\n"

        top_strategies = coin.get('backtest_top_strategies') or []
        if top_strategies:
            confidence_score = top_strategies[0].get('confidence_score')
            weighted_net_score = top_strategies[0].get('weighted_net_score')
            if isinstance(confidence_score, (int, float)):
                caption += f"🧠 Backtest Confidence: {float(confidence_score):.0f}/100"
                if isinstance(weighted_net_score, (int, float)):
                    caption += f" (weighted net: {float(weighted_net_score):+.2f})"
                caption += "\n"

        reentry_quality_score = coin.get('reentry_quality_score')
        if isinstance(reentry_quality_score, (int, float)):
            caption += f"🔁 Re-entry Quality: {float(reentry_quality_score):.0f}/100"
            if coin.get('reentry_quality_label'):
                caption += f" ({coin.get('reentry_quality_label')})"
            caption += "\n"

        regime = coin.get('market_regime')
        if regime:
            caption += f"🌦️ Regime: {regime}\n"

        volume_acceleration_pct = coin.get('volume_acceleration_pct')
        volume_window_days = coin.get('volume_acceleration_window_days')
        if isinstance(volume_acceleration_pct, (int, float)) and isinstance(volume_window_days, int):
            caption += f"🚀 Volume Acceleration: {float(volume_acceleration_pct):+.0f}% vs prior {volume_window_days}d avg\n"

        if any(
            value is not None
            for value in [current_rank, signal_age_label, volume_acceleration_pct, health_score]
        ):
            caption += "\n"

        # Total CMC 24h volume
        total_volume_24h = coin.get('volume_24h', 0)
        if isinstance(total_volume_24h, (int, float)) and total_volume_24h > 0:
            caption += f"💵 Total 24h Volume (CMC): ${total_volume_24h:,.0f}\n\n"
        else:
            caption += f"💵 Total 24h Volume (CMC): No volume\n\n"
        
        # Exchange volumes
        caption += f"💰 Exchange Volumes:\n"
        
        volumes = coin.get('exchange_volumes', {})
        listed_on = coin.get('listed_on', ['coinbase', 'kraken', 'mexc'])
        
        for exchange in listed_on:
            volume = volumes.get(exchange, "N/A")
            exchange_emoji = EXCHANGE_EMOJIS.get(exchange, "💱")
            
            # Show "No volume" instead of $0 or N/A per spec §10.1
            if volume == "N/A" or volume == 0 or volume == "0":
                caption += f"{exchange_emoji} {exchange.title()}: No volume\n"
            elif isinstance(volume, (int, float)):
                caption += f"{exchange_emoji} {exchange.title()}: ${volume:,.0f}\n"
            else:
                caption += f"{exchange_emoji} {exchange.title()}: {volume}\n"
        
        return caption
    
    @staticmethod
    def format_exit(coin: Dict) -> str:
        """
        Format exit notification per spec §10.2
        Returns plain text message
        """
        symbol = coin['symbol']
        name = coin['name']
        cmc_url = f"https://coinmarketcap.com/currencies/{coin['slug']}/"
        reason = coin.get('exit_reason', 'No longer met qualification criteria')
        
        message = f"🔴 {symbol} ({name})\n"
        message += f"🔗 {cmc_url}\n"
        message += f"has left the qualified list\n"
        message += f"Reason: {reason}"

        lifecycle_pnl_pct = coin.get('lifecycle_pnl_pct')
        max_runup_pct = coin.get('max_runup_pct')
        max_drawdown_pct = coin.get('max_drawdown_pct')
        held_days = coin.get('held_days')

        lifecycle_parts = []
        if isinstance(lifecycle_pnl_pct, (int, float)):
            lifecycle_parts.append(f"P&L {float(lifecycle_pnl_pct):+.2f}%")
        if isinstance(max_runup_pct, (int, float)):
            lifecycle_parts.append(f"Max↑ {float(max_runup_pct):+.2f}%")
        if isinstance(max_drawdown_pct, (int, float)):
            lifecycle_parts.append(f"Max↓ {float(max_drawdown_pct):+.2f}%")
        if isinstance(held_days, int):
            lifecycle_parts.append(f"Held {held_days}d")

        if lifecycle_parts:
            message += "\nLifecycle: " + " | ".join(lifecycle_parts)
        
        return message

    @staticmethod
    def format_active_rankings_summary(
        active_rows: List[Dict],
        entries_count: int,
        exits_count: int,
        blocked_count: int,
        regime: str | None = None,
        drift_status: str | None = None,
        max_chars: int = 3800,
    ) -> List[str]:
        active_count = len(active_rows)
        header = (
            "📋 <b>Active Coins (This Scan)</b>\n"
            f"Entries: {entries_count} | Exits: {exits_count} | Cooldown blocked: {blocked_count} | Active: {active_count}"
        )
        if regime:
            header += f"\nRegime: {regime}"
        if drift_status:
            header += f" | Drift: {drift_status}"

        if not active_rows:
            return [header + "\n\nNo active coins this scan."]

        lines = []
        for row in active_rows:
            active_rank = row.get('active_rank')
            rank_label = f"A#{int(active_rank)}" if isinstance(active_rank, int) else "A#?"
            movement = MessageFormatter._format_rank_change(str(row.get('rank_status', 'new')), row.get('rank_delta'))
            since_entry = MessageFormatter._format_pct(row.get('gain_since_entry_pct'))
            since_last_update = MessageFormatter._format_pct(row.get('gain_since_last_update_pct'))
            health = MessageFormatter._format_score(row.get('health_score'))
            symbol = str(row.get('symbol', '')).upper()
            lines.append(
                f"{rank_label} {movement} <b>{symbol}</b> | H: {health} | Since alert: {since_entry} | 1h: {since_last_update}"
            )

        messages: List[str] = []
        current_message = header + "\n\n"

        for line in lines:
            candidate = current_message + line + "\n"
            if len(candidate) > max_chars and current_message.strip():
                messages.append(current_message.rstrip())
                current_message = "📋 <b>Active Coins (cont.)</b>\n\n" + line + "\n"
            else:
                current_message = candidate

        if current_message.strip():
            messages.append(current_message.rstrip())

        return messages

    @staticmethod
    def format_hourly_combined_report(
        active_rows: List[Dict],
        entries_count: int,
        exits_count: int,
        blocked_count: int,
        watchlist_rows: List[Dict],
        warnings: List[Dict],
        regime: str | None,
        drift_status: str | None,
        drift_notes: List[str] | None = None,
        max_chars: int = 3800,
    ) -> str:
        lines: List[str] = []
        lines.append("📋 <b>Hourly Scanner Report</b>")
        lines.append(
            f"Entries: {entries_count} | Exits: {exits_count} | Cooldown blocked: {blocked_count} | Active: {len(active_rows)}"
        )
        if regime:
            lines.append(f"Regime: {regime}")
        if drift_status:
            lines.append(f"Benchmark drift: {drift_status}")
        if drift_notes:
            for note in drift_notes[:2]:
                lines.append(f"• Drift note: {note}")

        lines.append("")
        lines.append("🏁 <b>Active Rankings</b>")
        if active_rows:
            for row in active_rows[:15]:
                active_rank = row.get('active_rank')
                active_label = f"A#{int(active_rank)}" if isinstance(active_rank, int) else "A#?"
                movement = MessageFormatter._format_rank_change(str(row.get('rank_status', 'new')), row.get('rank_delta'))
                health = MessageFormatter._format_score(row.get('health_score'))
                since_entry = MessageFormatter._format_pct(row.get('gain_since_entry_pct'))
                since_last = MessageFormatter._format_pct(row.get('gain_since_last_update_pct'))
                symbol = str(row.get('symbol', '')).upper()
                lines.append(
                    f"• {active_label} {movement} <b>{symbol}</b> | H {health} | Alert {since_entry} | 1h {since_last}"
                )
        else:
            lines.append("• No active coins this scan.")

        lines.append("")
        lines.append("⚠️ <b>Early Warnings</b>")
        if warnings:
            for row in warnings[:6]:
                reasons = ", ".join((row.get('reasons') or [])[:2])
                lines.append(
                    f"• <b>{row.get('symbol')}</b> | health {float(row.get('health_score', 0.0)):.0f}/100 | {reasons}"
                )
        else:
            lines.append("• None")

        lines.append("")
        lines.append("👀 <b>Watchlist</b>")
        if watchlist_rows:
            for row in watchlist_rows[:6]:
                reasons = ", ".join((row.get('reasons') or [])[:2])
                lines.append(f"• <b>{row.get('symbol')}</b> | score {float(row.get('watchlist_score', 0.0)):.0f} | {reasons}")
        else:
            lines.append("• None")

        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 20].rstrip() + "\n…truncated"

    @staticmethod
    def format_watchlist_summary(watchlist_rows: List[Dict]) -> str:
        if not watchlist_rows:
            return "👀 <b>Watchlist</b>\nNo near-qualifiers this scan."

        lines = ["👀 <b>Watchlist Near-Qualifiers</b>"]
        for row in watchlist_rows[:8]:
            reasons = ", ".join(row.get('reasons', [])[:2])
            lines.append(
                f"• <b>{row.get('symbol')}</b> | score {float(row.get('watchlist_score', 0.0)):.0f} | {reasons}"
            )
        return "\n".join(lines)

    @staticmethod
    def format_early_warnings(warnings: List[Dict]) -> str:
        if not warnings:
            return ""
        lines = ["⚠️ <b>Exit Early-Warning Alerts</b>"]
        for row in warnings[:8]:
            reason_text = ", ".join(row.get('reasons', [])[:3])
            rank_text = f"#{row.get('current_rank')}" if row.get('current_rank') else "#?"
            lines.append(
                f"• <b>{row.get('symbol')}</b> {rank_text} | health {float(row.get('health_score', 0.0)):.0f}/100 | {reason_text}"
            )
        return "\n".join(lines)

    @staticmethod
    def format_drift_summary(drift: Dict) -> str:
        status = str(drift.get('status', 'stable'))
        notes = drift.get('notes', []) or []
        if status == 'stable':
            return "📏 <b>Benchmark Drift</b>\nStatus: stable"
        return "📏 <b>Benchmark Drift</b>\nStatus: drift\n" + "\n".join(f"• {note}" for note in notes)

    @staticmethod
    def format_summary_caption(regime: Dict | None, drift: Dict | None, active_count: int, watchlist_count: int) -> str:
        regime_label = str((regime or {}).get('regime', 'unknown'))
        drift_label = str((drift or {}).get('status', 'stable'))
        return (
            "🖼️ <b>Hourly Scanner Dashboard</b>\n"
            f"Regime: {regime_label}\n"
            f"Benchmark drift: {drift_label}\n"
            f"Active: {active_count} | Watchlist: {watchlist_count}"
        )