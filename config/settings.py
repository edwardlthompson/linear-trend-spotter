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
        self.BASE_DIR = Path(__file__).parent.parent
        self.config_path = Path(config_path) if config_path else self.BASE_DIR / 'config.json'
        
        # Initialize with defaults
        self._config = self._get_default_config()
        
        # Try to load config file (for non-sensitive settings only)
        try:
            loaded_config = self._load_config()
            if loaded_config:
                self._config.update(loaded_config)
        except Exception as e:
            print(f"⚠️ Warning: Could not load config file: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values per spec §9.3"""
        return {
            'MIN_VOLUME_M': 1000000,
            'TARGET_EXCHANGES': ['coinbase', 'kraken', 'mexc'],
            'UNIFORMITY_MIN_SCORE': 55,
            'UNIFORMITY_PERIOD': 30,
            'TOP_COINS_LIMIT': 2500,
            'ENTRY_NOTIFICATIONS': True,
            'EXIT_NOTIFICATIONS': True,
            'RETRY_MAX_ATTEMPTS': 3,
            'RETRY_DELAY': 2,
            'RETRY_BACKOFF': 2,
            'COINGECKO_CALLS_PER_MINUTE': 30,
            'CMC_CALLS_PER_MINUTE': 333,
            'CACHE_GECKO_ID_DAYS': 30,
            'CACHE_EXCHANGE_HOURS': 24,
            'CACHE_PRICE_HOURS': 6,
            'CIRCUIT_FAILURE_THRESHOLD': 5,
            'CIRCUIT_RECOVERY_TIMEOUT': 60,
            'USE_14D_FILTER': False
        }
    
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
        return self._config.get('TOP_COINS_LIMIT', 2500)
    
    @property
    def entry_notifications(self) -> bool:
        return self._config.get('ENTRY_NOTIFICATIONS', True)
    
    @property
    def exit_notifications(self) -> bool:
        return self._config.get('EXIT_NOTIFICATIONS', True)
    
    @property
    def coingecko_calls_per_minute(self) -> int:
        return self._config.get('COINGECKO_CALLS_PER_MINUTE', 30)
    
    @property
    def cmc_calls_per_minute(self) -> int:
        return self._config.get('CMC_CALLS_PER_MINUTE', 333)
    
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
    def db_paths(self) -> Dict[str, Path]:
        return {
            'scanner': self.BASE_DIR / 'scanner.db',
            'exchanges': self.BASE_DIR / 'exchanges.db',
            'mappings': self.BASE_DIR / 'mappings.db',
            'tv_mappings': self.BASE_DIR / 'tv_mappings.db'
        }
    
    @property
    def lock_file(self) -> Path:
        return self.BASE_DIR / 'scan.lock'
    
    @property
    def metrics_file(self) -> Path:
        return self.BASE_DIR / 'metrics.json'
    
    @property
    def log_file(self) -> Path:
        return self.BASE_DIR / 'trend_scanner.log'
    
    @property
    def retry_settings(self) -> dict:
        return {
            'max_attempts': self._config.get('RETRY_MAX_ATTEMPTS', 3),
            'delay': self._config.get('RETRY_DELAY', 2),
            'backoff': self._config.get('RETRY_BACKOFF', 2)
        }

# Global settings instance
settings = Settings()