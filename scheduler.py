#!/usr/bin/env python3
"""
Scheduler Module - Prevents overlapping scans and manages execution
Run this via cron instead of running main.py directly
"""

import os
import sys
import time
import fcntl
import json
import logging
import gc
from datetime import datetime
from pathlib import Path

# Add the current directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import our modules - fix the import path
from config.settings import settings
from utils.logger import setup_logger

class ScanLock:
    """
    Prevents multiple scans from running simultaneously using file locking
    """

    def __init__(self, lock_file=None):
        if lock_file is None:
            self.lock_file = Path(settings.BASE_DIR) / 'scan.lock'
        else:
            self.lock_file = Path(lock_file)
        self.fp = None
        self.logger = logging.getLogger('ScanLock')

    def __enter__(self):
        """Acquire the lock"""
        try:
            self.fp = open(self.lock_file, 'w')
            # Try to acquire an exclusive lock without blocking
            fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.logger.info(f"Lock acquired: {self.lock_file}")
            # Write PID to lock file for debugging
            self.fp.write(str(os.getpid()))
            self.fp.flush()
            return self
        except IOError:
            # Another process has the lock
            raise RuntimeError(f"Another scan is already running (lock file exists: {self.lock_file})")
        except Exception as e:
            self.logger.error(f"Error acquiring lock: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release the lock"""
        if self.fp:
            try:
                fcntl.flock(self.fp, fcntl.LOCK_UN)
                self.fp.close()
                # Try to remove the lock file
                try:
                    self.lock_file.unlink()
                except:
                    pass
                self.logger.info("Lock released")
            except Exception as e:
                self.logger.error(f"Error releasing lock: {e}")

class ScanScheduler:
    """
    Manages scan scheduling and execution
    """

    def __init__(self):
        self.logger = setup_logger('scheduler')
        self.lock = ScanLock()
        self.stats_file = Path(settings.BASE_DIR) / 'scan_stats.json'

    def should_run(self):
        """
        Check if we should run based on time and last run
        Returns True if scan should execute
        """
        # Always run - cron handles scheduling
        # This method is here for future enhancements like:
        # - Rate limiting
        # - Cooldown periods
        # - Time-based restrictions
        return True

    def run_scan(self):
        """Execute the main scan with locking"""
        start_time = time.time()
        self.logger.info("=" * 50)
        self.logger.info("📊 SCAN STARTED")
        self.logger.info(f"Time: {datetime.now()}")
        self.logger.info("=" * 50)

        try:
            # Import main here to avoid circular imports - use renamed function
            from main import run_scanner as scan_main

            # Run the main scan
            scan_main()

            elapsed = time.time() - start_time
            self.logger.info("=" * 50)
            self.logger.info(f"✅ SCAN COMPLETED in {elapsed:.2f} seconds")
            self.logger.info("=" * 50)

            # Save stats
            self._save_stats(elapsed)

            # Force garbage collection to close any lingering connections
            import gc
            gc.collect()

        except Exception as e:
            self.logger.error(f"❌ Scan failed: {e}", exc_info=True)
            raise

    def _save_stats(self, duration):
        """Save scan statistics"""
        stats = {
            'last_run': datetime.now().isoformat(),
            'duration': duration,
            'success': True
        }

        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r') as f:
                    history = json.load(f)
            else:
                history = []

            history.append(stats)

            # Keep only last 100 runs
            if len(history) > 100:
                history = history[-100:]

            with open(self.stats_file, 'w') as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving stats: {e}")

    def run(self):
        """Main entry point"""
        if not self.should_run():
            self.logger.info("Skipping scan - should_run() returned False")
            return

        try:
            with self.lock:
                self.run_scan()
        except RuntimeError as e:
            self.logger.warning(str(e))
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)

def main():
    """CLI entry point"""
    scheduler = ScanScheduler()
    scheduler.run()

if __name__ == "__main__":
    main()