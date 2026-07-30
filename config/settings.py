"""Configuration management"""
import json
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

from dotenv import load_dotenv

from config.constants import DEFAULT_TARGET_EXCHANGES

# Load environment variables from .env file
load_dotenv()

_logger = logging.getLogger(__name__)

class Settings:
    """Centralized settings management"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.CODE_DIR = Path(__file__).parent.parent
        data_dir_raw = os.getenv('DATA_DIR', '').strip()
        self.DATA_DIR = Path(data_dir_raw).expanduser() if data_dir_raw else self.CODE_DIR
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.BASE_DIR = self.CODE_DIR
        self.config_path = Path(config_path) if config_path else self.CODE_DIR / 'config.json'
        
        # Initialize with defaults
        self._config = self._get_default_config()
        
        # Try to load config file (for non-sensitive settings only)
        try:
            loaded_config = self._load_config()
            if loaded_config:
                self._config.update(loaded_config)
        except ValueError:
            raise
        except Exception as e:
            _logger.warning("Could not load config file: %s", e)

        # Fail-fast safety validation and normalization
        self._config = self._validate_and_normalize(self._config)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values per spec §9.3"""
        return {
            'MIN_VOLUME_M': 1000000,
            'GAIN_FILTER_MIN_7D_PERCENT': 7.0,
            'GAIN_FILTER_MIN_30D_PERCENT': 30.0,
            'TARGET_EXCHANGES': list(DEFAULT_TARGET_EXCHANGES),
            'UNIFORMITY_MIN_SCORE': 55,
            'UNIFORMITY_PERIOD': 30,
            'TOP_COINS_LIMIT': 4000,
            'TOP_COINS_PROVIDER': 'cmc',
            'ENTRY_NOTIFICATIONS': True,
            'EXIT_NOTIFICATIONS': True,
            'NO_CHANGE_NOTIFICATIONS': False,
            'RETRY_MAX_ATTEMPTS': 3,
            'RETRY_DELAY': 2,
            'RETRY_BACKOFF': 2,
            'COINGECKO_CALLS_PER_MINUTE': 30,
            'CMC_CALLS_PER_MINUTE': 333,
            'POLYGON_CALLS_PER_MINUTE': 5,
            'CMC_SYMBOL_ALIASES': {
                'CRYPGPT': 'CGPT',
            },
            'COINGECKO_ID_ALIASES': {
                'CRYPGPT': 'crypgpt',
            },
            'CACHE_GECKO_ID_DAYS': 30,
            'CACHE_EXCHANGE_HOURS': 24,
            'CACHE_PRICE_HOURS': 12,
            'OHLCV_UNIFORMITY_SOURCE_ORDER': 'coingecko,polygon,cmc',
            'CIRCUIT_FAILURE_THRESHOLD': 5,
            'CIRCUIT_RECOVERY_TIMEOUT': 60,
            'BACKTEST_ENABLED': True,
            'BACKTEST_REQUIRE_TARGET_EXCHANGE': False,
            'BACKTEST_EXCHANGES': ['kraken'],
            'BACKTEST_STARTING_CAPITAL': 1000,
            'BACKTEST_FEE_BPS_ROUND_TRIP': 52,
            'BACKTEST_MAX_PARAM_COMBOS': 100,
            'BACKTEST_PARALLEL_WORKERS': 4,
            'BACKTEST_PER_COIN_TIMEOUT_SECONDS': 1800,
            'BACKTEST_MAX_COINS_PER_RUN': 0,
            'BACKTEST_TIMEFRAMES': ['1h', '4h'],
            'BACKTEST_INDICATORS': [],
            'BACKTEST_TRAILING_STOP_MIN': 2,
            'BACKTEST_TRAILING_STOP_MAX': 20,
            'BACKTEST_TRAILING_STOP_STEP': 2,
            'BACKTEST_AB_SHADOW_ENABLED': False,
            'BACKTEST_AB_SHADOW_MAX_COINS': 3,
            'BACKTEST_AB_SHADOW_MAX_PARAM_COMBOS': 25,
            'BACKTEST_AB_SHADOW_TRAILING_STOP_MIN': 2,
            'BACKTEST_AB_SHADOW_TRAILING_STOP_MAX': 20,
            'BACKTEST_AB_SHADOW_TRAILING_STOP_STEP': 2,
            'BACKTEST_AB_SHADOW_RESULTS_FILE': 'backtest_shadow_results.json',
            'BACKTEST_AB_SHADOW_CHECKPOINT_FILE': 'backtest_shadow_checkpoint.json',
            'BACKTEST_AB_SHADOW_TELEMETRY_FILE': 'backtest_shadow_telemetry.jsonl',
            'BACKTEST_RESUME_ENABLED': True,
            'BACKTEST_CHECKPOINT_FILE': 'backtest_checkpoint.json',
            'BACKTEST_TELEMETRY_FILE': 'backtest_telemetry.jsonl',
            'BACKTEST_FAILURE_SAMPLES_LIMIT': 200,
            'OHLCV_MIN_1H_BARS_PER_DAY': 24,
            'OHLCV_MIN_1H_BARS_SLACK': 12,
            'OHLCV_MIN_1H_BARS_FLOOR': 600,
            'OHLCV_MIN_1D_BARS_SLACK': 2,
            'OHLCV_MIN_1D_BARS_FLOOR': 25,
            'ARTIFACT_HYGIENE_ENABLED': True,
            'ARTIFACT_RETENTION_DAYS': 7,
            'ARTIFACT_ARCHIVE_DIR': '.archive/auto',
            'NOTIFICATION_INCLUDE_QUALITY_PANEL': True,
            'NOTIFICATION_SYMBOL_QUALITY_LINE': False,
            'EXIT_ANALYTICS_FILE': 'exit_reason_analytics.json',
            'USE_14D_FILTER': False,
            'ALERT_COOLDOWN_HOURS': 6,
            'ANOMALY_ALERTS_ENABLED': True,
            'ANOMALY_MAX_MISSING_CG_RATIO': 0.35,
            'ANOMALY_MIN_OHLCV_SUCCESS_RATIO': 0.60,
            'ANOMALY_MAX_NO_TICKER_RATIO': 0.50,
            'WATCHLIST_ENABLED': True,
            'WATCHLIST_SCORE_BUFFER': 8,
            'WATCHLIST_EXPORT_ENABLED': False,
            'WATCHLIST_EXPORT_CSV_FILE': 'watchlist_export.csv',
            'WATCHLIST_EXPORT_JSON_FILE': 'watchlist_export.json',
            'PORTFOLIO_SIM_ENABLED': True,
            'PORTFOLIO_SIM_STARTING_CAPITAL': 10000,
            'PORTFOLIO_MULTI_SIM_ENABLED': False,
            'PORTFOLIO_MULTI_SIM_FILE': 'portfolio_multi_simulation.json',
            'PORTFOLIO_MULTI_SIM_CAPITALS': [1000, 5000, 10000],
            'ALERT_BACKTEST_REPORT_ENABLED': False,
            'ALERT_BACKTEST_REPORT_FILE': 'alert_backtest_report.json',
            'ALERT_BACKTEST_REPORT_TOP_N': 10,
            'REGIME_FILTER_ENABLED': False,
            'REGIME_FILTER_BTC_MIN_30D_GAIN': 0.0,
            'REGIME_FILTER_BTC_MAX_ABS_7D_GAIN': 25.0,
            'SCANNER_INSIGHTS_FILE': 'scanner_insights.json',
            'WEEKLY_DIGEST_ENABLED': False,
            'WEEKLY_DIGEST_WEEKDAY_UTC': 0,
            'WEEKLY_DIGEST_HOUR_UTC': 12,
            'WEEKLY_DIGEST_STATE_FILE': 'weekly_digest_state.json',
            'SCAN_HEARTBEAT_ENABLED': False,
            'SCAN_HEARTBEAT_FILE': 'scan_heartbeat.json',
            'PUBLIC_QUALIFIED_SNAPSHOT_ENABLED': True,
            'PUBLIC_QUALIFIED_SNAPSHOT_FILE': 'qualified_public_snapshot.json',
            'PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET': 'full',
            'SCAN_INTERVAL_SECONDS': 3600,
            'SCAN_COSTS_ENABLED': False,
            'SCAN_COSTS_FILE': 'scan_costs.json',
            'SCAN_COST_PANEL_COINGECKO_MONTHLY_HTTP_CAP': 0,
            'SCAN_COST_PANEL_POLYGON_MONTHLY_HTTP_CAP': 0,
            'SCAN_COST_PANEL_CMC_MONTHLY_HTTP_CAP': 0,
            'DEGRADE_SKIP_BACKTEST_ENABLED': False,
            'DEGRADE_PRIOR_CG_HTTP_SKIP_GE': 0,
            'CMC_SLUG_MAP_ENABLED': True,
            'CMC_SLUG_MAP_MAX_AGE_HOURS': 72,
            'CMC_SLUG_MAP_CACHE_FILE': 'cmc_cryptocurrency_map_cache.json',
            'CMC_SLUG_LEARN_FILE': 'gecko_id_to_cmc_slug.json',
            'NTFY_ENABLED': False,
            'NTFY_BASE_URL': 'https://ntfy.sh',
            'NTFY_TOPIC': '',
            'NTFY_TOKEN': '',
            'NTFY_PRIORITY': 'default',
            'NTFY_DASHBOARD_URL': '',
        }

    def _validate_and_normalize(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Validate config shape/ranges and normalize values.

        Raises ValueError with actionable diagnostics when invalid.
        """
        normalized = dict(candidate)
        defaults = self._get_default_config()

        unknown = sorted(set(normalized.keys()) - set(defaults.keys()))
        if unknown:
            _logger.warning(
                "Unknown config keys ignored by app logic: %s",
                ", ".join(unknown),
            )

        errors: list[str] = []

        def require_bool(key: str) -> None:
            if not isinstance(normalized.get(key), bool):
                errors.append(f"{key} must be boolean")

        def require_int(key: str, min_value: int | None = None, max_value: int | None = None) -> None:
            value = normalized.get(key)
            if not isinstance(value, int):
                errors.append(f"{key} must be integer")
                return
            if min_value is not None and value < min_value:
                errors.append(f"{key} must be >= {min_value}")
            if max_value is not None and value > max_value:
                errors.append(f"{key} must be <= {max_value}")

        def require_number(key: str, min_value: float | None = None, max_value: float | None = None) -> None:
            value = normalized.get(key)
            if not isinstance(value, (int, float)):
                errors.append(f"{key} must be numeric")
                return
            as_float = float(value)
            if min_value is not None and as_float < min_value:
                errors.append(f"{key} must be >= {min_value}")
            if max_value is not None and as_float > max_value:
                errors.append(f"{key} must be <= {max_value}")

        require_int('MIN_VOLUME_M', min_value=0)
        require_int('UNIFORMITY_MIN_SCORE', min_value=0, max_value=100)
        require_int('UNIFORMITY_PERIOD', min_value=7, max_value=120)
        require_int('TOP_COINS_LIMIT', min_value=1, max_value=10000)

        provider = str(normalized.get('TOP_COINS_PROVIDER', 'cmc')).strip().lower()
        if provider not in {'cmc', 'coingecko'}:
            errors.append("TOP_COINS_PROVIDER must be one of: cmc, coingecko")
        else:
            normalized['TOP_COINS_PROVIDER'] = provider

        _src_order_raw = str(normalized.get("OHLCV_UNIFORMITY_SOURCE_ORDER", "coingecko,polygon,cmc")).strip()
        _src_parts = [p.strip().lower() for p in _src_order_raw.split(",") if p.strip()]
        _allowed_ohlcv = {"coingecko", "polygon", "cmc"}
        if len(_src_parts) != 3 or set(_src_parts) != _allowed_ohlcv:
            errors.append(
                "OHLCV_UNIFORMITY_SOURCE_ORDER must list each of coingecko, polygon, cmc exactly once "
                "(comma-separated; default coingecko,polygon,cmc)",
            )
        else:
            normalized["OHLCV_UNIFORMITY_SOURCE_ORDER"] = ",".join(_src_parts)

        for bool_key in [
            'ENTRY_NOTIFICATIONS',
            'EXIT_NOTIFICATIONS',
            'NO_CHANGE_NOTIFICATIONS',
            'BACKTEST_ENABLED',
            'BACKTEST_REQUIRE_TARGET_EXCHANGE',
            'BACKTEST_RESUME_ENABLED',
            'ARTIFACT_HYGIENE_ENABLED',
            'NOTIFICATION_INCLUDE_QUALITY_PANEL',
            'NOTIFICATION_SYMBOL_QUALITY_LINE',
            'USE_14D_FILTER',
            'ANOMALY_ALERTS_ENABLED',
            'WATCHLIST_ENABLED',
            'WATCHLIST_EXPORT_ENABLED',
            'PORTFOLIO_SIM_ENABLED',
            'PORTFOLIO_MULTI_SIM_ENABLED',
            'ALERT_BACKTEST_REPORT_ENABLED',
            'REGIME_FILTER_ENABLED',
            'WEEKLY_DIGEST_ENABLED',
            'SCAN_HEARTBEAT_ENABLED',
            'PUBLIC_QUALIFIED_SNAPSHOT_ENABLED',
            'SCAN_COSTS_ENABLED',
            'DEGRADE_SKIP_BACKTEST_ENABLED',
            'BACKTEST_AB_SHADOW_ENABLED',
            'CMC_SLUG_MAP_ENABLED',
            'NTFY_ENABLED',
        ]:
            require_bool(bool_key)

        for int_key, lower, upper in [
            ('RETRY_MAX_ATTEMPTS', 1, 10),
            ('RETRY_DELAY', 1, 60),
            ('RETRY_BACKOFF', 1, 10),
            ('COINGECKO_CALLS_PER_MINUTE', 1, 120),
            ('CMC_CALLS_PER_MINUTE', 1, 1000),
            ('POLYGON_CALLS_PER_MINUTE', 1, 300),
            ('CACHE_GECKO_ID_DAYS', 1, 365),
            ('CACHE_EXCHANGE_HOURS', 1, 168),
            ('CACHE_PRICE_HOURS', 1, 72),
            ('CIRCUIT_FAILURE_THRESHOLD', 1, 100),
            ('CIRCUIT_RECOVERY_TIMEOUT', 1, 3600),
            ('BACKTEST_MAX_PARAM_COMBOS', 1, 5000),
            ('BACKTEST_PARALLEL_WORKERS', 1, 32),
            ('BACKTEST_PER_COIN_TIMEOUT_SECONDS', 30, 86400),
            ('BACKTEST_MAX_COINS_PER_RUN', 0, 10000),
            ('BACKTEST_TRAILING_STOP_MIN', 1, 100),
            ('BACKTEST_TRAILING_STOP_MAX', 0, 100),
            ('BACKTEST_TRAILING_STOP_STEP', 1, 20),
            ('BACKTEST_AB_SHADOW_MAX_COINS', 1, 500),
            ('BACKTEST_AB_SHADOW_MAX_PARAM_COMBOS', 1, 5000),
            ('BACKTEST_AB_SHADOW_TRAILING_STOP_MIN', 1, 100),
            ('BACKTEST_AB_SHADOW_TRAILING_STOP_MAX', 0, 100),
            ('BACKTEST_AB_SHADOW_TRAILING_STOP_STEP', 1, 20),
            ('BACKTEST_FAILURE_SAMPLES_LIMIT', 10, 5000),
            ('OHLCV_MIN_1H_BARS_PER_DAY', 1, 48),
            ('OHLCV_MIN_1H_BARS_SLACK', 0, 5000),
            ('OHLCV_MIN_1H_BARS_FLOOR', 1, 20000),
            ('OHLCV_MIN_1D_BARS_SLACK', 0, 500),
            ('OHLCV_MIN_1D_BARS_FLOOR', 1, 2000),
            ('ARTIFACT_RETENTION_DAYS', 1, 3650),
            ('ALERT_COOLDOWN_HOURS', 0, 720),
            ('WATCHLIST_SCORE_BUFFER', 1, 30),
            ('PORTFOLIO_SIM_STARTING_CAPITAL', 100, 1000000000),
            ('WEEKLY_DIGEST_WEEKDAY_UTC', 0, 6),
            ('WEEKLY_DIGEST_HOUR_UTC', 0, 23),
            ('DEGRADE_PRIOR_CG_HTTP_SKIP_GE', 0, 10_000_000),
            ('CMC_SLUG_MAP_MAX_AGE_HOURS', 1, 8760),
            ('SCAN_INTERVAL_SECONDS', 60, 604800),
            ('ALERT_BACKTEST_REPORT_TOP_N', 1, 200),
            ('SCAN_COST_PANEL_COINGECKO_MONTHLY_HTTP_CAP', 0, 100_000_000),
            ('SCAN_COST_PANEL_POLYGON_MONTHLY_HTTP_CAP', 0, 100_000_000),
            ('SCAN_COST_PANEL_CMC_MONTHLY_HTTP_CAP', 0, 100_000_000),
        ]:
            require_int(int_key, min_value=lower, max_value=upper)

        for number_key, num_lower, num_upper in [
            ('ANOMALY_MAX_MISSING_CG_RATIO', 0.0, 1.0),
            ('ANOMALY_MIN_OHLCV_SUCCESS_RATIO', 0.0, 1.0),
            ('ANOMALY_MAX_NO_TICKER_RATIO', 0.0, 1.0),
            ('REGIME_FILTER_BTC_MIN_30D_GAIN', -100.0, 500.0),
            ('REGIME_FILTER_BTC_MAX_ABS_7D_GAIN', 0.0, 500.0),
        ]:
            require_number(number_key, min_value=num_lower, max_value=num_upper)

        require_number('GAIN_FILTER_MIN_7D_PERCENT', min_value=-100.0, max_value=500.0)
        require_number('GAIN_FILTER_MIN_30D_PERCENT', min_value=-100.0, max_value=500.0)

        cmc_symbol_aliases = normalized.get('CMC_SYMBOL_ALIASES', {})
        if not isinstance(cmc_symbol_aliases, dict):
            errors.append('CMC_SYMBOL_ALIASES must be an object mapping exchange symbol -> CMC symbol')
        else:
            normalized_aliases: dict[str, str] = {}
            for raw_key, raw_value in cmc_symbol_aliases.items():
                if not isinstance(raw_key, str) or not raw_key.strip() or not isinstance(raw_value, str) or not raw_value.strip():
                    errors.append('CMC_SYMBOL_ALIASES must contain non-empty string keys and values only')
                    break
                normalized_aliases[raw_key.strip().upper()] = raw_value.strip().upper()
            normalized['CMC_SYMBOL_ALIASES'] = normalized_aliases

        coingecko_id_aliases = normalized.get('COINGECKO_ID_ALIASES', {})
        if not isinstance(coingecko_id_aliases, dict):
            errors.append('COINGECKO_ID_ALIASES must be an object mapping exchange symbol -> CoinGecko coin id')
        else:
            normalized_id_aliases: dict[str, str] = {}
            for raw_key, raw_value in coingecko_id_aliases.items():
                if not isinstance(raw_key, str) or not raw_key.strip() or not isinstance(raw_value, str) or not raw_value.strip():
                    errors.append('COINGECKO_ID_ALIASES must contain non-empty string keys and values only')
                    break
                normalized_id_aliases[raw_key.strip().upper()] = raw_value.strip().lower()
            normalized['COINGECKO_ID_ALIASES'] = normalized_id_aliases

        stop_min = int(normalized.get('BACKTEST_TRAILING_STOP_MIN', 1))
        stop_max = int(normalized.get('BACKTEST_TRAILING_STOP_MAX', 20))
        if stop_max < stop_min:
            errors.append('BACKTEST_TRAILING_STOP_MAX must be >= BACKTEST_TRAILING_STOP_MIN')

        shadow_stop_min = int(normalized.get('BACKTEST_AB_SHADOW_TRAILING_STOP_MIN', 1))
        shadow_stop_max = int(normalized.get('BACKTEST_AB_SHADOW_TRAILING_STOP_MAX', 20))
        if shadow_stop_max < shadow_stop_min:
            errors.append('BACKTEST_AB_SHADOW_TRAILING_STOP_MAX must be >= BACKTEST_AB_SHADOW_TRAILING_STOP_MIN')

        require_number('BACKTEST_STARTING_CAPITAL', min_value=1.0)
        require_number('BACKTEST_FEE_BPS_ROUND_TRIP', min_value=0.0, max_value=1000.0)
        require_number('PORTFOLIO_SIM_STARTING_CAPITAL', min_value=1.0)

        multi_caps = normalized.get('PORTFOLIO_MULTI_SIM_CAPITALS', [])
        if not isinstance(multi_caps, list) or not multi_caps:
            errors.append('PORTFOLIO_MULTI_SIM_CAPITALS must be a non-empty list')
        else:
            cleaned_caps: list[float] = []
            for raw in multi_caps:
                try:
                    v = float(raw)
                except Exception:
                    errors.append('PORTFOLIO_MULTI_SIM_CAPITALS must contain numbers only')
                    cleaned_caps = []
                    break
                if v <= 0:
                    errors.append('PORTFOLIO_MULTI_SIM_CAPITALS must contain values > 0')
                    cleaned_caps = []
                    break
                cleaned_caps.append(v)
            if cleaned_caps:
                normalized['PORTFOLIO_MULTI_SIM_CAPITALS'] = cleaned_caps

        exchanges = normalized.get('TARGET_EXCHANGES')
        if not isinstance(exchanges, list) or not exchanges:
            errors.append('TARGET_EXCHANGES must be a non-empty list')
        elif any(not isinstance(item, str) or not item.strip() for item in exchanges):
            errors.append('TARGET_EXCHANGES must contain non-empty strings only')
        else:
            normalized['TARGET_EXCHANGES'] = [item.strip().lower() for item in exchanges]

        backtest_exchanges = normalized.get('BACKTEST_EXCHANGES')
        if not isinstance(backtest_exchanges, list):
            errors.append('BACKTEST_EXCHANGES must be a list')
        elif any(not isinstance(item, str) or not item.strip() for item in backtest_exchanges):
            errors.append('BACKTEST_EXCHANGES must contain non-empty strings only')
        else:
            normalized['BACKTEST_EXCHANGES'] = [item.strip().lower() for item in backtest_exchanges]

        allowed_timeframes = {'1h', '4h', '1d'}
        timeframes = normalized.get('BACKTEST_TIMEFRAMES')
        if not isinstance(timeframes, list) or not timeframes:
            errors.append('BACKTEST_TIMEFRAMES must be a non-empty list')
        else:
            normalized_tfs = [str(item).strip().lower() for item in timeframes if str(item).strip()]
            if not normalized_tfs:
                errors.append('BACKTEST_TIMEFRAMES cannot be empty')
            elif any(item not in allowed_timeframes for item in normalized_tfs):
                errors.append('BACKTEST_TIMEFRAMES supports only: 1h, 4h, 1d')
            else:
                normalized['BACKTEST_TIMEFRAMES'] = normalized_tfs

        indicators = normalized.get('BACKTEST_INDICATORS', [])
        if not isinstance(indicators, list):
            errors.append('BACKTEST_INDICATORS must be a list')
        elif any(not isinstance(item, str) or not item.strip() for item in indicators):
            errors.append('BACKTEST_INDICATORS must contain non-empty strings only')
        else:
            normalized['BACKTEST_INDICATORS'] = [str(item).strip() for item in indicators]

        field_set = str(normalized.get('PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET', 'full')).strip().lower()
        if field_set not in {'full', 'minimal'}:
            errors.append('PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET must be one of: full, minimal')
        else:
            normalized['PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET'] = field_set

        for path_key in [
            'BACKTEST_CHECKPOINT_FILE',
            'BACKTEST_TELEMETRY_FILE',
            'ARTIFACT_ARCHIVE_DIR',
            'EXIT_ANALYTICS_FILE',
            'SCANNER_INSIGHTS_FILE',
            'WEEKLY_DIGEST_STATE_FILE',
            'SCAN_COSTS_FILE',
            'CMC_SLUG_MAP_CACHE_FILE',
            'CMC_SLUG_LEARN_FILE',
            'WATCHLIST_EXPORT_CSV_FILE',
            'WATCHLIST_EXPORT_JSON_FILE',
        ]:
            value = normalized.get(path_key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path_key} must be a non-empty string path")

        # Architectural policy: integrated backtesting is mandatory for this app.
        # Keep key for compatibility, but enforce enabled behavior consistently.
        if normalized.get('BACKTEST_ENABLED') is False:
            _logger.warning(
                "BACKTEST_ENABLED=false is ignored; backtesting is always enabled by design."
            )
            normalized['BACKTEST_ENABLED'] = True

        if errors:
            joined = '\n- '.join(errors)
            raise ValueError(f"Invalid configuration in {self.config_path}:\n- {joined}")

        return normalized
    
    def _load_config(self) -> Dict[str, Any]:
        """Load non-sensitive settings from config.json.

        If the file exists but is not valid JSON, raise ValueError (fail-fast).
        """
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {self.config_path}: {e}") from e
    
    @property
    def cmc_api_key(self) -> str:
        """CoinMarketCap API key from environment"""
        return os.getenv('CMC_API_KEY', '')
    
    @property
    def min_volume(self) -> int:
        """Minimum 24h volume in USD"""
        return self._config.get('MIN_VOLUME_M', 1000000)

    @property
    def gain_filter_min_7d_percent(self) -> float:
        """FILTER 1: minimum provider-reported 7d gain (percent) to stay in the pipeline."""
        return float(self._config.get('GAIN_FILTER_MIN_7D_PERCENT', 7.0))

    @property
    def gain_filter_min_30d_percent(self) -> float:
        """FILTER 1: 30d gain must be strictly greater than this value (percent)."""
        return float(self._config.get('GAIN_FILTER_MIN_30D_PERCENT', 30.0))

    @property
    def chart_img_api_key(self) -> str:
        """Chart-IMG API key from environment"""
        return os.getenv('CHART_IMG_API_KEY', '')
    
    @property
    def target_exchanges(self) -> list:
        return self._config.get('TARGET_EXCHANGES', list(DEFAULT_TARGET_EXCHANGES))
    
    @property
    def uniformity_min_score(self) -> int:
        return self._config.get('UNIFORMITY_MIN_SCORE', 55)
    
    @property
    def uniformity_period(self) -> int:
        return self._config.get('UNIFORMITY_PERIOD', 30)
    
    @property
    def top_coins_limit(self) -> int:
        return self._config.get('TOP_COINS_LIMIT', 4000)

    @property
    def top_coins_provider(self) -> str:
        return str(self._config.get('TOP_COINS_PROVIDER', 'cmc')).strip().lower()
    
    @property
    def entry_notifications(self) -> bool:
        return self._config.get('ENTRY_NOTIFICATIONS', True)
    
    @property
    def exit_notifications(self) -> bool:
        return self._config.get('EXIT_NOTIFICATIONS', True)

    @property
    def no_change_notifications(self) -> bool:
        return self._config.get('NO_CHANGE_NOTIFICATIONS', False)

    @property
    def portfolio_multi_sim_enabled(self) -> bool:
        return bool(self._config.get('PORTFOLIO_MULTI_SIM_ENABLED', False))

    @property
    def portfolio_multi_sim_file(self) -> Path:
        raw_path = str(self._config.get('PORTFOLIO_MULTI_SIM_FILE', 'portfolio_multi_simulation.json')).strip()
        return self.DATA_DIR / (raw_path or 'portfolio_multi_simulation.json')

    @property
    def portfolio_multi_sim_capitals(self) -> list[float]:
        values = self._config.get('PORTFOLIO_MULTI_SIM_CAPITALS', [1000, 5000, 10000])
        if isinstance(values, list) and values:
            out: list[float] = []
            for item in values:
                try:
                    v = float(item)
                except Exception:
                    continue
                if v > 0:
                    out.append(v)
            if out:
                return out
        return [1000.0, 5000.0, 10000.0]

    @property
    def regime_filter_enabled(self) -> bool:
        return bool(self._config.get('REGIME_FILTER_ENABLED', False))

    @property
    def regime_filter_btc_min_30d_gain(self) -> float:
        return float(self._config.get('REGIME_FILTER_BTC_MIN_30D_GAIN', 0.0))

    @property
    def regime_filter_btc_max_abs_7d_gain(self) -> float:
        return float(self._config.get('REGIME_FILTER_BTC_MAX_ABS_7D_GAIN', 25.0))

    @property
    def alert_backtest_report_enabled(self) -> bool:
        return bool(self._config.get('ALERT_BACKTEST_REPORT_ENABLED', False))

    @property
    def alert_backtest_report_file(self) -> Path:
        raw_path = str(self._config.get('ALERT_BACKTEST_REPORT_FILE', 'alert_backtest_report.json')).strip()
        return self.DATA_DIR / (raw_path or 'alert_backtest_report.json')

    @property
    def alert_backtest_report_top_n(self) -> int:
        return int(self._config.get('ALERT_BACKTEST_REPORT_TOP_N', 10))
    
    @property
    def coingecko_calls_per_minute(self) -> int:
        return self._config.get('COINGECKO_CALLS_PER_MINUTE', 30)
    
    @property
    def cmc_calls_per_minute(self) -> int:
        return self._config.get('CMC_CALLS_PER_MINUTE', 333)

    @property
    def polygon_calls_per_minute(self) -> int:
        return int(self._config.get('POLYGON_CALLS_PER_MINUTE', 5))

    @property
    def cmc_symbol_aliases(self) -> Dict[str, str]:
        value = self._config.get('CMC_SYMBOL_ALIASES', {})
        return value if isinstance(value, dict) else {}

    @property
    def coingecko_id_aliases(self) -> Dict[str, str]:
        value = self._config.get('COINGECKO_ID_ALIASES', {})
        return value if isinstance(value, dict) else {}
    
    @property
    def cache_gecko_id_days(self) -> int:
        return self._config.get('CACHE_GECKO_ID_DAYS', 30)
    
    @property
    def cache_exchange_hours(self) -> int:
        return self._config.get('CACHE_EXCHANGE_HOURS', 24)
    
    @property
    def cache_price_hours(self) -> int:
        return self._config.get('CACHE_PRICE_HOURS', 12)

    @property
    def ohlcv_uniformity_source_order(self) -> tuple[str, ...]:
        """Order to try hourly OHLCV sources for uniformity (cache then live API per source)."""
        raw = str(self._config.get("OHLCV_UNIFORMITY_SOURCE_ORDER", "coingecko,polygon,cmc")).strip()
        parts = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
        allowed = {"coingecko", "polygon", "cmc"}
        if len(parts) == 3 and set(parts) == allowed:
            return parts
        return ("coingecko", "polygon", "cmc")
    
    @property
    def circuit_failure_threshold(self) -> int:
        return self._config.get('CIRCUIT_FAILURE_THRESHOLD', 5)
    
    @property
    def circuit_recovery_timeout(self) -> int:
        return self._config.get('CIRCUIT_RECOVERY_TIMEOUT', 60)

    @property
    def backtest_enabled(self) -> bool:
        # Always-on policy for this application.
        return True

    @property
    def backtest_require_target_exchange(self) -> bool:
        return bool(self._config.get('BACKTEST_REQUIRE_TARGET_EXCHANGE', False))

    @property
    def backtest_exchanges(self) -> list:
        return self._config.get('BACKTEST_EXCHANGES', ['kraken'])

    @property
    def backtest_starting_capital(self) -> float:
        return float(self._config.get('BACKTEST_STARTING_CAPITAL', 1000))

    @property
    def backtest_fee_bps_round_trip(self) -> int:
        return self._config.get('BACKTEST_FEE_BPS_ROUND_TRIP', 52)

    @property
    def backtest_max_param_combos(self) -> int:
        return self._config.get('BACKTEST_MAX_PARAM_COMBOS', 100)

    @property
    def backtest_parallel_workers(self) -> int:
        configured = int(self._config.get('BACKTEST_PARALLEL_WORKERS', 4))
        if os.getenv('RENDER') or os.getenv('RENDER_EXTERNAL_URL'):
            # Max 2 workers on Render Basic plan (0.5 CPU) to prevent stalling
            return min(configured, 2)
        return configured

    @property
    def backtest_per_coin_timeout_seconds(self) -> int:
        return int(self._config.get('BACKTEST_PER_COIN_TIMEOUT_SECONDS', 1800))

    @property
    def backtest_max_coins_per_run(self) -> int:
        return self._config.get('BACKTEST_MAX_COINS_PER_RUN', 0)

    @property
    def backtest_timeframes(self) -> list:
        values = self._config.get('BACKTEST_TIMEFRAMES', ['1h', '4h', '1d'])
        if isinstance(values, list) and values:
            return [str(item).lower() for item in values]
        return ['1h', '4h', '1d']

    @property
    def backtest_indicators(self) -> list:
        values = self._config.get('BACKTEST_INDICATORS', [])
        if isinstance(values, list):
            return [str(item).strip() for item in values if str(item).strip()]
        return []

    @property
    def backtest_trailing_stop_min(self) -> int:
        return int(self._config.get('BACKTEST_TRAILING_STOP_MIN', 1))

    @property
    def backtest_trailing_stop_max(self) -> int:
        return int(self._config.get('BACKTEST_TRAILING_STOP_MAX', 20))

    @property
    def backtest_trailing_stop_step(self) -> int:
        return int(self._config.get('BACKTEST_TRAILING_STOP_STEP', 1))

    @property
    def backtest_ab_shadow_enabled(self) -> bool:
        return bool(self._config.get('BACKTEST_AB_SHADOW_ENABLED', False))

    @property
    def backtest_ab_shadow_max_coins(self) -> int:
        return int(self._config.get('BACKTEST_AB_SHADOW_MAX_COINS', 3))

    @property
    def backtest_ab_shadow_max_param_combos(self) -> int:
        return int(self._config.get('BACKTEST_AB_SHADOW_MAX_PARAM_COMBOS', 25))

    @property
    def backtest_ab_shadow_trailing_stop_min(self) -> int:
        return int(self._config.get('BACKTEST_AB_SHADOW_TRAILING_STOP_MIN', 2))

    @property
    def backtest_ab_shadow_trailing_stop_max(self) -> int:
        return int(self._config.get('BACKTEST_AB_SHADOW_TRAILING_STOP_MAX', 20))

    @property
    def backtest_ab_shadow_trailing_stop_step(self) -> int:
        return int(self._config.get('BACKTEST_AB_SHADOW_TRAILING_STOP_STEP', 2))

    @property
    def backtest_ab_shadow_results_file(self) -> Path:
        raw_path = str(self._config.get('BACKTEST_AB_SHADOW_RESULTS_FILE', 'backtest_shadow_results.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def backtest_ab_shadow_checkpoint_file(self) -> Path:
        raw_path = str(self._config.get('BACKTEST_AB_SHADOW_CHECKPOINT_FILE', 'backtest_shadow_checkpoint.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def backtest_ab_shadow_telemetry_file(self) -> Path:
        raw_path = str(self._config.get('BACKTEST_AB_SHADOW_TELEMETRY_FILE', 'backtest_shadow_telemetry.jsonl')).strip()
        return self.DATA_DIR / raw_path

    @property
    def backtest_resume_enabled(self) -> bool:
        return bool(self._config.get('BACKTEST_RESUME_ENABLED', True))

    @property
    def backtest_checkpoint_file(self) -> Path:
        raw_path = str(self._config.get('BACKTEST_CHECKPOINT_FILE', 'backtest_checkpoint.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def backtest_telemetry_file(self) -> Path:
        raw_path = str(self._config.get('BACKTEST_TELEMETRY_FILE', 'backtest_telemetry.jsonl')).strip()
        return self.DATA_DIR / raw_path

    @property
    def backtest_failure_samples_limit(self) -> int:
        return int(self._config.get('BACKTEST_FAILURE_SAMPLES_LIMIT', 200))

    @property
    def ohlcv_min_1h_bars_per_day(self) -> int:
        return int(self._config.get('OHLCV_MIN_1H_BARS_PER_DAY', 24))

    @property
    def ohlcv_min_1h_bars_slack(self) -> int:
        return int(self._config.get('OHLCV_MIN_1H_BARS_SLACK', 12))

    @property
    def ohlcv_min_1h_bars_floor(self) -> int:
        return int(self._config.get('OHLCV_MIN_1H_BARS_FLOOR', 600))

    @property
    def ohlcv_min_1d_bars_slack(self) -> int:
        return int(self._config.get('OHLCV_MIN_1D_BARS_SLACK', 2))

    @property
    def ohlcv_min_1d_bars_floor(self) -> int:
        return int(self._config.get('OHLCV_MIN_1D_BARS_FLOOR', 25))

    @property
    def artifact_hygiene_enabled(self) -> bool:
        return bool(self._config.get('ARTIFACT_HYGIENE_ENABLED', True))

    @property
    def artifact_retention_days(self) -> int:
        return int(self._config.get('ARTIFACT_RETENTION_DAYS', 7))

    @property
    def artifact_archive_dir(self) -> Path:
        raw_path = str(self._config.get('ARTIFACT_ARCHIVE_DIR', '.archive/auto')).strip()
        return self.DATA_DIR / raw_path

    @property
    def notification_include_quality_panel(self) -> bool:
        return bool(self._config.get('NOTIFICATION_INCLUDE_QUALITY_PANEL', True))

    @property
    def notification_symbol_quality_line(self) -> bool:
        return bool(self._config.get('NOTIFICATION_SYMBOL_QUALITY_LINE', False))

    @property
    def exit_analytics_file(self) -> Path:
        raw_path = str(self._config.get('EXIT_ANALYTICS_FILE', 'exit_reason_analytics.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def alert_cooldown_hours(self) -> int:
        return int(self._config.get('ALERT_COOLDOWN_HOURS', 6))

    @property
    def anomaly_alerts_enabled(self) -> bool:
        return bool(self._config.get('ANOMALY_ALERTS_ENABLED', True))

    @property
    def anomaly_max_missing_cg_ratio(self) -> float:
        return float(self._config.get('ANOMALY_MAX_MISSING_CG_RATIO', 0.35))

    @property
    def anomaly_min_ohlcv_success_ratio(self) -> float:
        return float(self._config.get('ANOMALY_MIN_OHLCV_SUCCESS_RATIO', 0.60))

    @property
    def anomaly_max_no_ticker_ratio(self) -> float:
        return float(self._config.get('ANOMALY_MAX_NO_TICKER_RATIO', 0.50))

    @property
    def watchlist_enabled(self) -> bool:
        return bool(self._config.get('WATCHLIST_ENABLED', True))

    @property
    def watchlist_score_buffer(self) -> int:
        return int(self._config.get('WATCHLIST_SCORE_BUFFER', 8))

    @property
    def watchlist_export_enabled(self) -> bool:
        return bool(self._config.get('WATCHLIST_EXPORT_ENABLED', False))

    @property
    def watchlist_export_csv_file(self) -> str:
        name = str(self._config.get('WATCHLIST_EXPORT_CSV_FILE', 'watchlist_export.csv')).strip()
        return name or 'watchlist_export.csv'

    @property
    def watchlist_export_json_file(self) -> str:
        name = str(self._config.get('WATCHLIST_EXPORT_JSON_FILE', 'watchlist_export.json')).strip()
        return name or 'watchlist_export.json'

    @property
    def portfolio_sim_enabled(self) -> bool:
        return bool(self._config.get('PORTFOLIO_SIM_ENABLED', True))

    @property
    def portfolio_sim_starting_capital(self) -> int:
        return int(self._config.get('PORTFOLIO_SIM_STARTING_CAPITAL', 10000))

    @property
    def scanner_insights_file(self) -> Path:
        raw_path = str(self._config.get('SCANNER_INSIGHTS_FILE', 'scanner_insights.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def weekly_digest_enabled(self) -> bool:
        return bool(self._config.get('WEEKLY_DIGEST_ENABLED', True))

    @property
    def weekly_digest_weekday_utc(self) -> int:
        return int(self._config.get('WEEKLY_DIGEST_WEEKDAY_UTC', 0))

    @property
    def weekly_digest_hour_utc(self) -> int:
        return int(self._config.get('WEEKLY_DIGEST_HOUR_UTC', 12))

    @property
    def weekly_digest_state_file(self) -> Path:
        raw_path = str(self._config.get('WEEKLY_DIGEST_STATE_FILE', 'weekly_digest_state.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def scan_heartbeat_enabled(self) -> bool:
        return bool(self._config.get('SCAN_HEARTBEAT_ENABLED', False))

    @property
    def scan_heartbeat_file(self) -> str:
        name = str(self._config.get('SCAN_HEARTBEAT_FILE', 'scan_heartbeat.json')).strip()
        return name or 'scan_heartbeat.json'

    @property
    def public_qualified_snapshot_enabled(self) -> bool:
        return bool(self._config.get('PUBLIC_QUALIFIED_SNAPSHOT_ENABLED', True))

    @property
    def public_qualified_snapshot_file(self) -> str:
        name = str(self._config.get('PUBLIC_QUALIFIED_SNAPSHOT_FILE', 'qualified_public_snapshot.json')).strip()
        return name or 'qualified_public_snapshot.json'

    @property
    def public_qualified_snapshot_field_set(self) -> str:
        return str(self._config.get('PUBLIC_QUALIFIED_SNAPSHOT_FIELD_SET', 'full')).strip().lower()

    @property
    def scan_interval_seconds(self) -> int:
        """Nominal seconds between worker scans (Render `SCAN_INTERVAL_SECONDS` overrides config)."""
        env_raw = os.getenv('SCAN_INTERVAL_SECONDS', '').strip()
        if env_raw:
            try:
                v = int(env_raw)
                if 60 <= v <= 604800:
                    return v
            except ValueError:
                pass
        return int(self._config.get('SCAN_INTERVAL_SECONDS', 3600))

    @property
    def scan_costs_enabled(self) -> bool:
        return bool(self._config.get('SCAN_COSTS_ENABLED', False))

    @property
    def scan_costs_file(self) -> str:
        name = str(self._config.get('SCAN_COSTS_FILE', 'scan_costs.json')).strip()
        return name or 'scan_costs.json'

    @property
    def scan_cost_panel_coingecko_monthly_http_cap(self) -> int:
        return int(self._config.get('SCAN_COST_PANEL_COINGECKO_MONTHLY_HTTP_CAP', 0))

    @property
    def scan_cost_panel_polygon_monthly_http_cap(self) -> int:
        return int(self._config.get('SCAN_COST_PANEL_POLYGON_MONTHLY_HTTP_CAP', 0))

    @property
    def scan_cost_panel_cmc_monthly_http_cap(self) -> int:
        return int(self._config.get('SCAN_COST_PANEL_CMC_MONTHLY_HTTP_CAP', 0))

    @property
    def degrade_skip_backtest_enabled(self) -> bool:
        return bool(self._config.get('DEGRADE_SKIP_BACKTEST_ENABLED', False))

    @property
    def degrade_prior_cg_http_skip_ge(self) -> int:
        return int(self._config.get('DEGRADE_PRIOR_CG_HTTP_SKIP_GE', 0))

    @property
    def cmc_slug_map_enabled(self) -> bool:
        return bool(self._config.get('CMC_SLUG_MAP_ENABLED', True))

    @property
    def cmc_slug_map_max_age_hours(self) -> int:
        return int(self._config.get('CMC_SLUG_MAP_MAX_AGE_HOURS', 72))

    @property
    def cmc_slug_map_cache_file(self) -> str:
        name = str(self._config.get('CMC_SLUG_MAP_CACHE_FILE', 'cmc_cryptocurrency_map_cache.json')).strip()
        return name or 'cmc_cryptocurrency_map_cache.json'

    @property
    def cmc_slug_learn_file(self) -> str:
        name = str(self._config.get('CMC_SLUG_LEARN_FILE', 'gecko_id_to_cmc_slug.json')).strip()
        return name or 'gecko_id_to_cmc_slug.json'

    def _env_or_config_str(self, key: str, default: str = '') -> str:
        env_raw = os.getenv(key)
        if env_raw is not None:
            return str(env_raw).strip()
        return str(self._config.get(key, default)).strip()

    def _env_or_config_bool(self, key: str, default: bool = False) -> bool:
        env_raw = os.getenv(key)
        if env_raw is not None:
            return str(env_raw).strip().lower() in ('1', 'true', 'yes', 'on')
        return bool(self._config.get(key, default))

    @property
    def ntfy_enabled(self) -> bool:
        return self._env_or_config_bool('NTFY_ENABLED', False)

    @property
    def ntfy_base_url(self) -> str:
        return self._env_or_config_str('NTFY_BASE_URL', 'https://ntfy.sh')

    @property
    def ntfy_topic(self) -> str:
        return self._env_or_config_str('NTFY_TOPIC', '')

    @property
    def ntfy_token(self) -> str:
        return self._env_or_config_str('NTFY_TOKEN', '')

    @property
    def ntfy_priority(self) -> str:
        raw = self._env_or_config_str('NTFY_PRIORITY', 'default').lower()
        return raw if raw in ('min', 'low', 'default', 'high', 'max', 'urgent') else 'default'

    @property
    def ntfy_dashboard_url(self) -> str:
        return self._env_or_config_str('NTFY_DASHBOARD_URL', '')

    @property
    def ntfy_public_subscribe_url(self) -> str:
        """HTTPS subscribe URL for dashboard hints (no publish token)."""
        if not self.ntfy_enabled:
            return ''
        topic = self.ntfy_topic
        if not topic:
            return ''
        base = self.ntfy_base_url.rstrip('/') or 'https://ntfy.sh'
        return f'{base}/{topic}'

    @property
    def base_dir(self) -> Path:
        return self.DATA_DIR
    
    @property
    def db_paths(self) -> Dict[str, Path]:
        return {
            'scanner': self.DATA_DIR / 'scanner.db',
            'exchanges': self.DATA_DIR / 'exchanges.db',
            'mappings': self.DATA_DIR / 'mappings.db',
            'tv_mappings': self.DATA_DIR / 'tv_mappings.db'
        }
    
    @property
    def lock_file(self) -> Path:
        return self.DATA_DIR / 'scan.lock'
    
    @property
    def metrics_file(self) -> Path:
        return self.DATA_DIR / 'metrics.json'
    
    @property
    def log_file(self) -> Path:
        return self.DATA_DIR / 'trend_scanner.log'
    
    @property
    def retry_settings(self) -> dict:
        return {
            'max_attempts': self._config.get('RETRY_MAX_ATTEMPTS', 3),
            'delay': self._config.get('RETRY_DELAY', 2),
            'backoff': self._config.get('RETRY_BACKOFF', 2)
        }

# Global settings instance
settings = Settings()