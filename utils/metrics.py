"""
Metrics Collection Module
Tracks API calls, cache hits, timing, and performance metrics
"""

import time
import json
from datetime import datetime
from collections import defaultdict
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

class MetricsCollector:
    """
    Collect and report performance metrics
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.reset()
    
    def reset(self):
        """Reset all metrics"""
        self.start_time = time.time()
        self.counts = defaultdict(int)
        self.timings = defaultdict(list)
        self.errors = defaultdict(int)
        self.api_calls = defaultdict(int)
        self.cache_hits = defaultdict(int)
        self.cache_misses = defaultdict(int)
        self.coins_processed = 0
    
    def increment(self, metric: str, value: int = 1):
        """Increment a counter metric"""
        self.counts[metric] += value
    
    def timing(self, name: str) -> Callable:
        """Decorator to time a function"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start
                    self.timings[name].append(duration)
                    # Keep only last 100 timings
                    if len(self.timings[name]) > 100:
                        self.timings[name] = self.timings[name][-100:]
            return wrapper
        return decorator
    
    def api_call(self, service: str):
        """Decorator to track API calls"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                self.api_calls[service] += 1
                self.increment(f'api_calls_total')
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    duration = time.time() - start
                    self.timings[f'api_{service}'].append(duration)
            return wrapper
        return decorator
    
    def cache_operation(self, cache_type: str, hit: bool):
        """Track cache hits/misses"""
        if hit:
            self.cache_hits[cache_type] += 1
            self.increment('cache_hits_total')
        else:
            self.cache_misses[cache_type] += 1
            self.increment('cache_misses_total')
    
    def error(self, error_type: str):
        """Track an error"""
        self.errors[error_type] += 1
        self.increment('errors_total')
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        elapsed = time.time() - self.start_time
        
        # Calculate averages
        avg_timings = {}
        for name, timings in self.timings.items():
            if timings:
                avg_timings[name] = sum(timings) / len(timings)
            else:
                avg_timings[name] = 0
        
        return {
            'duration': elapsed,
            'counts': dict(self.counts),
            'api_calls': dict(self.api_calls),
            'cache_hits': dict(self.cache_hits),
            'cache_misses': dict(self.cache_misses),
            'errors': dict(self.errors),
            'avg_timings': avg_timings,
            'coins_processed': self.coins_processed,
            'timestamp': datetime.now().isoformat()
        }
    
    def report(self) -> str:
        """Generate a human-readable report"""
        summary = self.get_summary()
        
        lines = [
            "\n" + "=" * 50,
            "📊 METRICS REPORT",
            "=" * 50,
            f"⏱️  Duration: {summary['duration']:.2f}s",
            f"🪙  Coins processed: {summary['coins_processed']}",
            "",
            "📡 API Calls:",
        ]
        
        for service, count in summary['api_calls'].items():
            lines.append(f"   • {service}: {count}")
        
        lines.extend([
            "",
            "💾 Cache:",
        ])
        
        for cache_type, hits in summary['cache_hits'].items():
            misses = summary['cache_misses'].get(cache_type, 0)
            total = hits + misses
            if total > 0:
                hit_rate = (hits / total) * 100
                lines.append(f"   • {cache_type}: {hits} hits, {misses} misses ({hit_rate:.1f}% hit rate)")
        
        if summary['errors']:
            lines.extend([
                "",
                "❌ Errors:",
            ])
            for error_type, count in summary['errors'].items():
                lines.append(f"   • {error_type}: {count}")
        
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def save(self, filepath: Optional[Path] = None):
        """Save metrics to file"""
        if filepath is None:
            filepath = Path(__file__).parent.parent / 'metrics.json'
        
        try:
            # Load existing history
            if filepath.exists():
                with open(filepath, 'r') as f:
                    history = json.load(f)
            else:
                history = []
            
            # Add current metrics
            history.append(self.get_summary())
            
            # Keep only last 100 runs
            if len(history) > 100:
                history = history[-100:]
            
            # Save back
            with open(filepath, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            print(f"Error saving metrics: {e}")

# Global metrics instance
metrics = MetricsCollector()

# Context manager for timing blocks
class timed_block:
    """Context manager for timing code blocks"""
    
    def __init__(self, name: str):
        self.name = name
        self.start = None
    
    def __enter__(self):
        self.start = time.time()
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start
        metrics.timings[self.name].append(duration)