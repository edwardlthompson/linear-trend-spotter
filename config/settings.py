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
        """Get default configuration values"""
        return {
            'MIN_VOLUME_M': 1000000,
            'SENSITIVITY': 0.75,
            'TARGET_EXCHANGES': ['coinbase', 'kraken', 'mexc'],
            'UNIFORMITY_MIN_SCORE': 45,
            'UNIFORMITY_PERIOD': 30,
            'USE_14D_FILTER': False,
            'RETRY_MAX_ATTEMPTS': 3,
            'RETRY_DELAY': 2,
            'RETRY_BACKOFF': 2
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
        return self._config.get('UNIFORMITY_MIN_SCORE', 45)
    
    @property
    def uniformity_period(self) -> int:
        return self._config.get('UNIFORMITY_PERIOD', 30)
    
    @property
    def db_paths(self) -> Dict[str, Path]:
        return {
            'history': self.BASE_DIR / 'history.db',
            'mapping': self.BASE_DIR / 'mapping.db',
            'log': self.BASE_DIR / 'scan_log.txt'
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