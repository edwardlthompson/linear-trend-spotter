"""
Notification message formatting
"""

import html
from typing import Dict, List, Tuple
from urllib.parse import quote

from config.constants import DEFAULT_TARGET_EXCHANGES, EXCHANGE_EMOJIS
from config.settings import settings


class MessageFormatter:
    """Format notification messages per spec §10.1-10.2"""

    @staticmethod
    def _tg_html_text(value: object) -> str:
        """Escape dynamic text for compact HTML-style captions (body text, not href)."""
        return html.escape(str(value or ""), quote=False)

    @staticmethod
    def _tg_html_attr(value: object) -> str:
        """Escape dynamic values for use inside HTML double-quoted attributes."""
        return html.escape(str(value or ""), quote=True)

    @staticmethod
    def _build_cmc_url(coin: Dict) -> str:
        """Prefer CoinMarketCap ``/currencies/{slug}/`` URLs only (never ``/search/``)."""
        explicit = str(coin.get('cmc_url') or '').strip()
        if explicit and "coinmarketcap.com/search" not in explicit.lower():
            return explicit

        cmc_slug_resolved = str(coin.get('cmc_slug') or '').strip().lower()
        if cmc_slug_resolved:
            return f"https://coinmarketcap.com/currencies/{quote(cmc_slug_resolved, safe='')}/"

        slug = str(coin.get('slug', '') or '').strip().lower()
        gecko_id = str(coin.get('gecko_id') or coin.get('cg_id') or '').strip().lower()
        # Top-coin snapshot from CoinGecko stores the API coin id in `slug`; that is not a CMC slug.
        if slug and not (gecko_id and slug == gecko_id):
            return f"https://coinmarketcap.com/currencies/{quote(slug, safe='')}/"

        return ''

    @staticmethod
    def _volume_listed_for_exchange(raw: object) -> bool:
        if raw is None:
            return False
        s = str(raw).strip().upper()
        if not s or s in {'N/A', 'NA', 'NONE', 'NULL'}:
            return False
        try:
            return float(s) > 0
        except ValueError:
            return True

    @staticmethod
    def exchange_url_buttons(coin: Dict) -> List[Tuple[str, str]]:
        """Per-exchange trade URLs for targets that show non-empty listing volume on the coin."""
        symbol = str(coin.get('symbol', '') or '').strip().upper()
        if not symbol:
            return []
        vols = coin.get('exchange_volumes') or {}
        out: List[Tuple[str, str]] = []
        if MessageFormatter._volume_listed_for_exchange(vols.get('coinbase')):
            out.append(('Coinbase', f'https://www.coinbase.com/advanced-trade/{symbol}-USD'))
        if MessageFormatter._volume_listed_for_exchange(vols.get('kraken')):
            pair = f'{symbol.lower()}-usd'
            out.append(('Kraken', f'https://pro.kraken.com/app/trade/{pair}'))
        if MessageFormatter._volume_listed_for_exchange(vols.get('mexc')):
            out.append(('MEXC', f'https://www.mexc.com/exchange/{symbol}_USDT'))
        return out

    @staticmethod
    def primary_market_url(coin: Dict) -> str:
        """Deep link for listings: CMC when available, else non-Gecko source_url, else CoinGecko."""
        url = MessageFormatter._build_cmc_url(coin)
        if url:
            return url
        su = str(coin.get('source_url') or '').strip()
        if not su:
            return MessageFormatter._build_coingecko_url(coin)
        if "coinmarketcap.com" in su.lower():
            if "coinmarketcap.com/search" in su.lower():
                return MessageFormatter._build_coingecko_url(coin)
            return su
        if 'coingecko.com' in su.lower():
            return MessageFormatter._build_coingecko_url(coin)
        return su

    @staticmethod
    def _build_coingecko_url(coin: Dict) -> str:
        gecko_id = str(coin.get('gecko_id') or coin.get('cg_id') or '').strip()
        if gecko_id:
            return f"https://www.coingecko.com/en/coins/{gecko_id}"

        slug = str(coin.get('slug', '') or '').strip().lower()
        if slug:
            return f"https://www.coingecko.com/en/coins/{slug}"

        symbol = str(coin.get('symbol', '') or '').strip()
        if symbol:
            return f"https://www.coingecko.com/en/search?query={symbol}"

        return "https://www.coingecko.com/"

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
    def _symbol_quality_line_html(coin: Dict) -> str:
        """Optional HTML line: reliability, OHLCV provider, signal age (Milestone L2)."""
        if not settings.notification_symbol_quality_line:
            return ""
        parts: list[str] = []
        rel = coin.get("data_reliability_score")
        if isinstance(rel, (int, float)):
            label = coin.get("data_reliability_label")
            lab = MessageFormatter._tg_html_text(label) if label else ""
            suffix = f" ({lab})" if lab else ""
            parts.append(f"reliability {float(rel):.0f}/100{suffix}")
        src = coin.get("ohlcv_source")
        if src:
            parts.append(f"OHLCV {MessageFormatter._tg_html_text(src)}")
        sig = coin.get("signal_age_label")
        if sig:
            parts.append(f"signal {MessageFormatter._tg_html_text(sig)}")
        if not parts:
            return ""
        joined = " · ".join(parts)
        return f"📡 <b>Data quality</b>: {joined}\n"

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
        Returns HTML-formatted caption for rich notification-style blocks
        """
        header_url = MessageFormatter.primary_market_url(coin)

        # Get data
        symbol = coin["symbol"]
        name = coin["name"]
        gain_7d = coin['gains'].get('7d', 0)
        gain_30d = coin['gains'].get('30d', 0)
        score = coin.get('uniformity_score', 0)
        
        sym_t = MessageFormatter._tg_html_text(symbol)
        name_t = MessageFormatter._tg_html_text(name)
        # Header with HTML link (CMC-first; see primary_market_url)
        if header_url:
            href = MessageFormatter._tg_html_attr(header_url)
            caption = f"🟢 <a href='{href}'>{sym_t} ({name_t})</a>\n\n"
        else:
            caption = f"🟢 {sym_t} ({name_t})\n\n"
        
        # Gains section
        caption += "📊 Gains:\n"
        caption += f"   7d: +{gain_7d:.1f}%\n"
        caption += f"   30d: +{gain_30d:.1f}%\n\n"
        
        # Uniformity score
        caption += f"📈 Uniformity Score: {score:.0f}/100\n"

        health_score = coin.get('health_score')
        if isinstance(health_score, (int, float)):
            caption += f"🩺 Health Score: {float(health_score):.0f}/100"
            if coin.get("health_label"):
                caption += f" ({MessageFormatter._tg_html_text(coin.get('health_label'))})"
            caption += "\n"

        sq = MessageFormatter._symbol_quality_line_html(coin)
        if sq:
            caption += sq

        caption += "\n"

        current_rank = coin.get('current_rank')
        previous_rank = coin.get('previous_rank')
        rank_status = coin.get('rank_status')
        rank_delta = coin.get('rank_delta')
        if isinstance(current_rank, int):
            if isinstance(previous_rank, int) and rank_status in {'up', 'down', 'flat'}:
                arrow = '↑' if rank_status == 'up' else '↓' if rank_status == 'down' else '→'
                rd = rank_delta if isinstance(rank_delta, (int, float)) else 0
                change_text = '' if rank_delta in (None, 0) else f" ({abs(int(rd))})"
                caption += f"🏁 Rank: #{current_rank} {arrow} from #{previous_rank}{change_text}\n"
            else:
                caption += f"🏁 Rank: #{current_rank} (new)\n"

        volume_acceleration_pct = coin.get('volume_acceleration_pct')
        volume_window_days = coin.get('volume_acceleration_window_days')
        if isinstance(volume_acceleration_pct, (int, float)) and isinstance(volume_window_days, int):
            caption += f"🚀 Volume Acceleration: {float(volume_acceleration_pct):+.0f}% vs prior {volume_window_days}d avg\n"

        if any(
            value is not None
            for value in [current_rank, volume_acceleration_pct, health_score]
        ):
            caption += "\n"

        # Total CMC 24h volume
        total_volume_24h = coin.get('volume_24h', 0)
        if isinstance(total_volume_24h, (int, float)) and total_volume_24h > 0:
            caption += f"💵 Total 24h Volume (Provider): ${total_volume_24h:,.0f}\n\n"
        else:
            caption += "💵 Total 24h Volume (Provider): No volume\n\n"
        
        # Exchange volumes
        caption += "💰 Exchange Volumes:\n"
        
        volumes = coin.get('exchange_volumes', {})
        listed_on = coin.get('listed_on', list(DEFAULT_TARGET_EXCHANGES))
        
        for exchange in listed_on:
            volume = volumes.get(exchange, "N/A")
            exchange_emoji = EXCHANGE_EMOJIS.get(exchange, "💱")
            
            # Show "No volume" instead of $0 or N/A per spec §10.1
            if volume == "N/A" or volume == 0 or volume == "0":
                caption += f"{exchange_emoji} {exchange.title()}: No volume\n"
            elif isinstance(volume, (int, float)):
                caption += f"{exchange_emoji} {exchange.title()}: ${volume:,.0f}\n"
            else:
                caption += (
                    f"{exchange_emoji} {exchange.title()}: "
                    f"{MessageFormatter._tg_html_text(volume)}\n"
                )
        
        return caption
    
    @staticmethod
    def format_exit(coin: Dict) -> str:
        """
        Format exit notification per spec §10.2
        Returns plain text message
        """
        symbol = MessageFormatter._tg_html_text(coin["symbol"])
        name = MessageFormatter._tg_html_text(coin["name"])
        market_url = MessageFormatter.primary_market_url(coin)
        reason = MessageFormatter._tg_html_text(
            coin.get("exit_reason", "No longer met qualification criteria")
        )

        message = f"🔴 {symbol} ({name})\n"
        message += f"🔗 {MessageFormatter._tg_html_text(market_url)}\n"
        message += "has left the qualified list\n"
        message += f"Reason: {reason}"

        sq = MessageFormatter._symbol_quality_line_html(coin)
        if sq:
            message += "\n" + sq.rstrip("\n")

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
            header += f"\nRegime: {MessageFormatter._tg_html_text(regime)}"
        if drift_status:
            header += f" | Drift: {MessageFormatter._tg_html_text(drift_status)}"

        if not active_rows:
            return [header + "\n\nNo active coins this scan."]

        lines = []
        for row in active_rows:
            active_rank = row.get('active_rank')
            rank_label = f"A#{int(active_rank)}" if isinstance(active_rank, int) else "A#?"
            movement = MessageFormatter._format_rank_change(str(row.get('rank_status', 'new')), row.get('rank_delta'))
            since_entry = MessageFormatter._format_pct(row.get('gain_since_entry_pct'))
            time_on_list = str(row.get('time_on_list') or 'n/a')
            health = MessageFormatter._format_score(row.get('health_score'))
            symbol = MessageFormatter._tg_html_text(str(row.get("symbol", "")).upper())
            lines.append(
                f"{rank_label} {movement} <b>{symbol}</b> | H: {health} | Since alert: {since_entry} | On list: {time_on_list}"
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
        max_chars: int = 3800,
    ) -> str:
        lines: List[str] = []
        lines.append("📋 <b>Scanner Event Report</b>")
        lines.append(
            f"Entries: {entries_count} | Exits: {exits_count} | Cooldown blocked: {blocked_count} | Active: {len(active_rows)}"
        )

        lines.append("")
        lines.append("🏁 <b>Active Rankings</b>")
        if active_rows:
            for row in active_rows[:15]:
                active_rank = row.get('active_rank')
                active_label = f"A#{int(active_rank)}" if isinstance(active_rank, int) else "A#?"
                movement = MessageFormatter._format_rank_change(str(row.get('rank_status', 'new')), row.get('rank_delta'))
                health = MessageFormatter._format_score(row.get('health_score'))
                since_entry = MessageFormatter._format_pct(row.get('gain_since_entry_pct'))
                time_on_list = str(row.get('time_on_list') or 'n/a')
                symbol = MessageFormatter._tg_html_text(str(row.get("symbol", "")).upper())
                lines.append(
                    f"• {active_label} {movement} <b>{symbol}</b> | H {health} | Alert {since_entry} | On list {time_on_list}"
                )
        else:
            lines.append("• No active coins this scan.")



        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 20].rstrip() + "\n…truncated"

    @staticmethod
    def format_summary_caption(
        active_count: int,
        backtest_diff_plain: str | None = None,
    ) -> str:
        base = (
            "🖼️ <b>Scanner Event Dashboard</b>\n"
            f"Active: {active_count}"
        )
        if backtest_diff_plain:
            base += (
                "\n📉 <b>BT top Δ</b> "
                + MessageFormatter._tg_html_text(backtest_diff_plain)
            )
        return base
