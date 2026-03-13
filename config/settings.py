"""Configuration management"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
        except Exception as e:
            print(f"⚠️ Warning: Could not load config file: {e}")

        # Fail-fast safety validation and normalization
        self._config = self._validate_and_normalize(self._config)
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values per spec §9.3"""
        return {
            'MIN_VOLUME_M': 1000000,
            'TARGET_EXCHANGES': ['coinbase', 'kraken', 'mexc'],
            'UNIFORMITY_MIN_SCORE': 55,
            'UNIFORMITY_PERIOD': 30,
            'TOP_COINS_LIMIT': 4000,
            'TOP_COINS_PROVIDER': 'coingecko',
            'ENTRY_NOTIFICATIONS': True,
            'EXIT_NOTIFICATIONS': True,
            'NO_CHANGE_NOTIFICATIONS': False,
            'RETRY_MAX_ATTEMPTS': 3,
            'RETRY_DELAY': 2,
            'RETRY_BACKOFF': 2,
            'COINGECKO_CALLS_PER_MINUTE': 30,
            'CMC_CALLS_PER_MINUTE': 333,
            'CMC_SYMBOL_ALIASES': {
                'CRYPGPT': 'CGPT',
            },
            'COINGECKO_ID_ALIASES': {
                'CRYPGPT': 'crypgpt',
            },
            'CACHE_GECKO_ID_DAYS': 30,
            'CACHE_EXCHANGE_HOURS': 24,
            'CACHE_PRICE_HOURS': 6,
            'CIRCUIT_FAILURE_THRESHOLD': 5,
            'CIRCUIT_RECOVERY_TIMEOUT': 60,
            'BACKTEST_ENABLED': True,
            'BACKTEST_REQUIRE_TARGET_EXCHANGE': False,
            'BACKTEST_EXCHANGES': ['kraken'],
            'BACKTEST_STARTING_CAPITAL': 1000,
            'BACKTEST_FEE_BPS_ROUND_TRIP': 52,
            'BACKTEST_MAX_PARAM_COMBOS': 100,
            'BACKTEST_PARALLEL_WORKERS': 4,
            'BACKTEST_MAX_COINS_PER_RUN': 0,
            'BACKTEST_TIMEFRAMES': ['1h', '4h', '1d'],
            'BACKTEST_INDICATORS': [],
            'BACKTEST_TRAILING_STOP_MIN': 1,
            'BACKTEST_TRAILING_STOP_MAX': 20,
            'BACKTEST_TRAILING_STOP_STEP': 1,
            'BACKTEST_RESUME_ENABLED': True,
            'BACKTEST_CHECKPOINT_FILE': 'backtest_checkpoint.json',
            'BACKTEST_TELEMETRY_FILE': 'backtest_telemetry.jsonl',
            'BACKTEST_FAILURE_SAMPLES_LIMIT': 200,
            'ARTIFACT_HYGIENE_ENABLED': True,
            'ARTIFACT_RETENTION_DAYS': 7,
            'ARTIFACT_ARCHIVE_DIR': '.archive/auto',
            'NOTIFICATION_INCLUDE_QUALITY_PANEL': True,
            'EXIT_ANALYTICS_FILE': 'exit_reason_analytics.json',
            'USE_14D_FILTER': False,
            'ALERT_COOLDOWN_HOURS': 6,
            'EXCHANGE_QUALITY_MIN_SCORE': 25,
            'ANOMALY_ALERTS_ENABLED': True,
            'ANOMALY_MAX_MISSING_CG_RATIO': 0.35,
            'ANOMALY_MIN_OHLCV_SUCCESS_RATIO': 0.60,
            'ANOMALY_MAX_NO_TICKER_RATIO': 0.50,
            'EARLY_WARNING_ENABLED': True,
            'WATCHLIST_ENABLED': True,
            'WATCHLIST_SCORE_BUFFER': 8,
            'PORTFOLIO_SIM_ENABLED': True,
            'PORTFOLIO_SIM_STARTING_CAPITAL': 10000,
            'HOURLY_SUMMARY_IMAGE_ENABLED': True,
            'SCANNER_INSIGHTS_FILE': 'scanner_insights.json',
            'WEEKLY_DIGEST_ENABLED': True,
            'WEEKLY_DIGEST_WEEKDAY_UTC': 0,
            'WEEKLY_DIGEST_HOUR_UTC': 12,
            'WEEKLY_DIGEST_STATE_FILE': 'weekly_digest_state.json',
        }

    def _validate_and_normalize(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Validate config shape/ranges and normalize values.

        Raises ValueError with actionable diagnostics when invalid.
        """
        normalized = dict(candidate)
        defaults = self._get_default_config()

        unknown = sorted(set(normalized.keys()) - set(defaults.keys()))
        if unknown:
            print(f"⚠️ Warning: Unknown config keys ignored by app logic: {', '.join(unknown)}")

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

        for bool_key in [
            'ENTRY_NOTIFICATIONS',
            'EXIT_NOTIFICATIONS',
            'NO_CHANGE_NOTIFICATIONS',
            'BACKTEST_ENABLED',
            'BACKTEST_REQUIRE_TARGET_EXCHANGE',
            'BACKTEST_RESUME_ENABLED',
            'ARTIFACT_HYGIENE_ENABLED',
            'NOTIFICATION_INCLUDE_QUALITY_PANEL',
            'USE_14D_FILTER',
            'ANOMALY_ALERTS_ENABLED',
            'EARLY_WARNING_ENABLED',
            'WATCHLIST_ENABLED',
            'PORTFOLIO_SIM_ENABLED',
            'HOURLY_SUMMARY_IMAGE_ENABLED',
            'WEEKLY_DIGEST_ENABLED',
        ]:
            require_bool(bool_key)

        for int_key, lower, upper in [
            ('RETRY_MAX_ATTEMPTS', 1, 10),
            ('RETRY_DELAY', 1, 60),
            ('RETRY_BACKOFF', 1, 10),
            ('COINGECKO_CALLS_PER_MINUTE', 1, 120),
            ('CMC_CALLS_PER_MINUTE', 1, 1000),
            ('CACHE_GECKO_ID_DAYS', 1, 365),
            ('CACHE_EXCHANGE_HOURS', 1, 168),
            ('CACHE_PRICE_HOURS', 1, 72),
            ('CIRCUIT_FAILURE_THRESHOLD', 1, 100),
            ('CIRCUIT_RECOVERY_TIMEOUT', 1, 3600),
            ('BACKTEST_MAX_PARAM_COMBOS', 1, 5000),
            ('BACKTEST_PARALLEL_WORKERS', 1, 32),
            ('BACKTEST_MAX_COINS_PER_RUN', 0, 10000),
            ('BACKTEST_TRAILING_STOP_MIN', 1, 100),
            ('BACKTEST_TRAILING_STOP_MAX', 0, 100),
            ('BACKTEST_TRAILING_STOP_STEP', 1, 20),
            ('BACKTEST_FAILURE_SAMPLES_LIMIT', 10, 5000),
            ('ARTIFACT_RETENTION_DAYS', 1, 3650),
            ('ALERT_COOLDOWN_HOURS', 0, 720),
            ('EXCHANGE_QUALITY_MIN_SCORE', 0, 100),
            ('WATCHLIST_SCORE_BUFFER', 1, 30),
            ('PORTFOLIO_SIM_STARTING_CAPITAL', 100, 1000000000),
            ('WEEKLY_DIGEST_WEEKDAY_UTC', 0, 6),
            ('WEEKLY_DIGEST_HOUR_UTC', 0, 23),
        ]:
            require_int(int_key, min_value=lower, max_value=upper)

        for number_key, lower, upper in [
            ('ANOMALY_MAX_MISSING_CG_RATIO', 0.0, 1.0),
            ('ANOMALY_MIN_OHLCV_SUCCESS_RATIO', 0.0, 1.0),
            ('ANOMALY_MAX_NO_TICKER_RATIO', 0.0, 1.0),
        ]:
            require_number(number_key, min_value=lower, max_value=upper)

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

        require_number('BACKTEST_STARTING_CAPITAL', min_value=1.0)
        require_number('BACKTEST_FEE_BPS_ROUND_TRIP', min_value=0.0, max_value=1000.0)

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

        for path_key in ['BACKTEST_CHECKPOINT_FILE', 'BACKTEST_TELEMETRY_FILE', 'ARTIFACT_ARCHIVE_DIR', 'EXIT_ANALYTICS_FILE', 'SCANNER_INSIGHTS_FILE', 'WEEKLY_DIGEST_STATE_FILE']:
            value = normalized.get(path_key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{path_key} must be a non-empty string path")

        # Architectural policy: integrated backtesting is mandatory for this app.
        # Keep key for compatibility, but enforce enabled behavior consistently.
        if normalized.get('BACKTEST_ENABLED') is False:
            print("⚠️ Warning: BACKTEST_ENABLED=false is ignored; backtesting is always enabled by design.")
            normalized['BACKTEST_ENABLED'] = True

        if errors:
            joined = '\n- '.join(errors)
            raise ValueError(f"Invalid configuration in {self.config_path}:\n- {joined}")

        return normalized
    
    def _load_config(self) -> Dict[str, Any]:
        """Load non-sensitive settings from config.json"""
        try:
            if not self.config_path.exists():
                return {}
                
            with open(self.config_path, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return {}
    
    @property
    def cmc_api_key(self) -> str:
        """CoinMarketCap API key from environment"""
        return os.getenv('CMC_API_KEY', '')
    
    @property
    def min_volume(self) -> int:
        """Minimum 24h volume in USD"""
        return self._config.get('MIN_VOLUME_M', 1000000)
    
    @property
    def telegram(self) -> Optional[Dict[str, str]]:
        """Telegram credentials from environment"""
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        if bot_token and chat_id:
            return {
                'bot_token': bot_token,
                'chat_id': chat_id
            }
        return None
    
    @property
    def chart_img_api_key(self) -> str:
        """Chart-IMG API key from environment"""
        return os.getenv('CHART_IMG_API_KEY', '')
    
    @property
    def target_exchanges(self) -> list:
        return self._config.get('TARGET_EXCHANGES', ['coinbase', 'kraken', 'mexc'])
    
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
        return str(self._config.get('TOP_COINS_PROVIDER', 'coingecko')).strip().lower()
    
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
    def coingecko_calls_per_minute(self) -> int:
        return self._config.get('COINGECKO_CALLS_PER_MINUTE', 30)
    
    @property
    def cmc_calls_per_minute(self) -> int:
        return self._config.get('CMC_CALLS_PER_MINUTE', 333)

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
        return self._config.get('CACHE_PRICE_HOURS', 6)
    
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
        return self._config.get('BACKTEST_PARALLEL_WORKERS', 4)

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
    def exit_analytics_file(self) -> Path:
        raw_path = str(self._config.get('EXIT_ANALYTICS_FILE', 'exit_reason_analytics.json')).strip()
        return self.DATA_DIR / raw_path

    @property
    def alert_cooldown_hours(self) -> int:
        return int(self._config.get('ALERT_COOLDOWN_HOURS', 6))

    @property
    def exchange_quality_min_score(self) -> int:
        return int(self._config.get('EXCHANGE_QUALITY_MIN_SCORE', 25))

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
    def early_warning_enabled(self) -> bool:
        return bool(self._config.get('EARLY_WARNING_ENABLED', True))

    @property
    def watchlist_enabled(self) -> bool:
        return bool(self._config.get('WATCHLIST_ENABLED', True))

    @property
    def watchlist_score_buffer(self) -> int:
        return int(self._config.get('WATCHLIST_SCORE_BUFFER', 8))

    @property
    def portfolio_sim_enabled(self) -> bool:
        return bool(self._config.get('PORTFOLIO_SIM_ENABLED', True))

    @property
    def portfolio_sim_starting_capital(self) -> int:
        return int(self._config.get('PORTFOLIO_SIM_STARTING_CAPITAL', 10000))

    @property
    def hourly_summary_image_enabled(self) -> bool:
        return bool(self._config.get('HOURLY_SUMMARY_IMAGE_ENABLED', True))

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