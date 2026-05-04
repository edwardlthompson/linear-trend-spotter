"""

CoinMarketCap API client - Optimized for bulk gain data

Verify limits on https://coinmarketcap.com/api/pricing/ (e.g. Basic free credits/month, RPM).

"""



from __future__ import annotations



import logging

import time

from typing import Any, Dict, List, Optional

from urllib.parse import quote



import requests



from utils.provider_http_usage import record_cmc_http

from utils.provider_rate_limit import MinIntervalGate, backoff_seconds_for_attempt



class CoinMarketCapClient:

    """

    CoinMarketCap API client - perfect for bulk gain data

    One call gets ALL coins with 7d, 30d, 60d, 90d gains

    """



    BASE_URL = "https://pro-api.coinmarketcap.com/v1"



    def __init__(

        self,

        api_key: str,

        *,

        rate_gate: MinIntervalGate | None = None,

        calls_per_minute: int = 30,

    ):

        self.api_key = api_key

        self.session = requests.Session()

        self.logger = logging.getLogger("CoinMarketCap")

        self.session.headers.update(

            {

                "X-CMC_PRO_API_KEY": api_key,

                "Accept": "application/json",

            }

        )

        self._gate = rate_gate if rate_gate is not None else MinIntervalGate(calls_per_minute)



    def _get_with_retries(

        self,

        url: str,

        params: Dict[str, Any],

        *,

        timeout: float,

        max_retries: int = 6,

    ) -> Optional[requests.Response]:

        """Pace per ``MinIntervalGate``, then GET with 429/transient backoff."""

        for attempt in range(max_retries):

            self._gate.wait()

            try:

                response = self.session.get(url, params=params, timeout=timeout)

                record_cmc_http(url)

                if response.status_code == 200:

                    return response

                if response.status_code == 429:

                    if attempt >= max_retries - 1:

                        self.logger.warning("CMC 429: max retries reached for %s", url[:80])

                        return response

                    wait_s = backoff_seconds_for_attempt(attempt, response=response)

                    self.logger.warning("CMC rate limited (429). Sleeping %.1fs (attempt %s)", wait_s, attempt + 1)

                    time.sleep(wait_s)

                    continue

                if response.status_code in (408, 500, 502, 503, 504) and attempt < max_retries - 1:

                    wait_s = min(5 * (2**attempt), 60) + 0.25

                    self.logger.warning("CMC transient HTTP %s; retry in %.1fs", response.status_code, wait_s)

                    time.sleep(wait_s)

                    continue

                return response

            except requests.exceptions.Timeout:

                if attempt >= max_retries - 1:

                    self.logger.warning("CMC timeout; giving up on %s", url[:80])

                    return None

                wait_s = min(5 * (2**attempt), 45) + 0.25

                self.logger.warning("CMC timeout; retry in %.1fs", wait_s)

                time.sleep(wait_s)

            except Exception as exc:

                self.logger.error("CMC request error: %s", exc)

                if attempt >= max_retries - 1:

                    return None

                time.sleep(min(5 * (2**attempt), 30))

        return None



    def get_all_coins_with_gains(self, limit: int = 2500) -> Optional[List[Dict]]:

        """

        Get ALL coins in ONE call with 7d, 30d, 60d, 90d gains

        Default limit is 2500 to preserve free-plan API credits.

        """

        url = f"{self.BASE_URL}/cryptocurrency/listings/latest"

        params = {

            "start": "1",

            "limit": limit,

            "convert": "USD",

        }



        self.logger.info(f"📡 Fetching {limit} coins with gains from CoinMarketCap...")



        response = self._get_with_retries(url, params, timeout=15.0)

        if response is None:

            return None

        if response.status_code != 200:

            self.logger.error(f"❌ CMC API error: {response.status_code}")

            return None

        try:

            data = response.json()

            coins = data.get("data", [])

            self.logger.info(f"✅ Got {len(coins)} coins with gain data")

            return coins

        except Exception as exc:

            self.logger.error(f"❌ CMC JSON parse error: {exc}")

            return None



    def fetch_cryptocurrency_map_page(

        self,

        *,

        start: int = 1,

        limit: int = 5000,

        listing_status: str = "active",

    ) -> Optional[List[Dict]]:

        """One page of ``/v1/cryptocurrency/map`` for slug resolution (paginate externally)."""

        url = f"{self.BASE_URL}/cryptocurrency/map"

        params: Dict[str, Any] = {

            "listing_status": listing_status,

            "start": max(1, int(start)),

            "limit": min(5000, max(1, int(limit))),

        }

        response = self._get_with_retries(url, params, timeout=60.0, max_retries=6)

        if response is None:

            return None

        if response.status_code != 200:

            self.logger.error("CMC map HTTP %s: %s", response.status_code, response.text[:200])

            return None

        try:

            payload = response.json()

            data = payload.get("data")

            if not isinstance(data, list):

                return None

            return data

        except Exception as exc:

            self.logger.error("CMC map JSON error: %s", exc)

            return None



    def extract_gains(self, coin_data: Dict) -> Dict:

        """

        Extract gain percentages from CMC data format

        Returns dict with 7d, 30d, 60d, 90d gains

        """

        quote = coin_data.get("quote", {}).get("USD", {})



        return {

            "7d": quote.get("percent_change_7d", 0),

            "30d": quote.get("percent_change_30d", 0),

            "60d": quote.get("percent_change_60d", 0),

            "90d": quote.get("percent_change_90d", 0),

        }



    def extract_coin_data(self, coin_data: Dict) -> Dict:

        """Extract basic coin data"""

        slug = str(coin_data.get("slug", "") or "").strip()

        slug_key = slug.lower()

        cmc_page = f"https://coinmarketcap.com/currencies/{quote(slug_key, safe='')}/" if slug_key else ""

        raw_id = coin_data.get("id")

        cmc_id: int | None = None

        if raw_id is not None:

            try:

                cmc_id = int(raw_id)

            except (TypeError, ValueError):

                cmc_id = None

        return {

            "symbol": coin_data.get("symbol", "").upper(),

            "name": coin_data.get("name", ""),

            "slug": slug,

            "cmc_id": cmc_id,

            "rank": coin_data.get("cmc_rank", 0),

            "price": coin_data.get("quote", {}).get("USD", {}).get("price", 0),

            "volume_24h": coin_data.get("quote", {}).get("USD", {}).get("volume_24h", 0),

            "cmc_url": cmc_page,

            "source_url": cmc_page or None,

        }

