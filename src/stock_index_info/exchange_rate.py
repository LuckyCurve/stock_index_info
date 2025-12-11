"""Exchange rate utilities for currency conversion."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from curl_cffi import requests

logger = logging.getLogger(__name__)

# Cache expiration time in seconds (24 hours)
_CACHE_EXPIRATION_SECONDS = 24 * 60 * 60

# Track last API call time for logging
_last_api_call_time: float = 0.0


@dataclass
class _ExchangeRateCache:
    """Cache container for exchange rates with timestamp."""

    rates: dict[str, float]
    timestamp: float  # Unix timestamp when cache was created


# Cache exchange rates to avoid repeated API calls
_exchange_rates_cache: Optional[_ExchangeRateCache] = None


def get_exchange_rates() -> Optional[dict[str, float]]:
    """Fetch current exchange rates from USD to other currencies.

    Returns:
        Dict mapping currency code to rate (1 USD = X currency),
        or None if API call fails.
    """
    global _exchange_rates_cache, _last_api_call_time

    # Check if cache exists and is not expired
    if _exchange_rates_cache is not None:
        age = time.time() - _exchange_rates_cache.timestamp
        if age < _CACHE_EXPIRATION_SECONDS:
            logger.debug(f"[API] get_exchange_rates(): using cached rates (age: {age:.0f}s)")
            return _exchange_rates_cache.rates
        else:
            logger.info(f"[API] get_exchange_rates(): cache expired (age: {age:.0f}s), refreshing")

    url = "https://open.er-api.com/v6/latest/USD"
    logger.info(f"[API] get_exchange_rates(): requesting {url}")
    start_time = time.time()

    try:
        response = requests.get(url, timeout=30)
        elapsed_ms = (time.time() - start_time) * 1000
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"[API] get_exchange_rates(): "
            f"response status={response.status_code}, elapsed={elapsed_ms:.0f}ms"
        )

        if data.get("result") != "success":
            logger.warning(f"[API] get_exchange_rates(): API returned non-success result: {data}")
            return None

        rates_data = data.get("rates")
        if not rates_data:
            logger.warning("[API] get_exchange_rates(): API returned no rates")
            return None

        rates: dict[str, float] = dict(rates_data)
        _exchange_rates_cache = _ExchangeRateCache(rates=rates, timestamp=time.time())
        logger.info(
            f"[API] get_exchange_rates(): successfully fetched rates for {len(rates)} currencies"
        )
        return rates

    except requests.RequestsError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_exchange_rates(): "
            f"request failed after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_exchange_rates(): "
            f"unexpected error after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


def convert_to_usd(amount: float, from_currency: str) -> Optional[float]:
    """Convert an amount from a foreign currency to USD.

    Args:
        amount: The amount in the source currency
        from_currency: The source currency code (e.g., "DKK", "EUR")

    Returns:
        The amount in USD, or None if conversion fails.
    """
    if from_currency == "USD":
        return amount

    logger.debug(f"[API] convert_to_usd(): converting {amount} {from_currency} to USD")

    rates = get_exchange_rates()
    if rates is None:
        logger.warning(f"[API] convert_to_usd(): failed to get exchange rates for {from_currency}")
        return None

    rate = rates.get(from_currency)
    if rate is None:
        logger.warning(f"[API] convert_to_usd(): no exchange rate found for {from_currency}")
        return None

    if rate <= 0:
        logger.warning(f"[API] convert_to_usd(): invalid exchange rate for {from_currency}: {rate}")
        return None

    # rates are "1 USD = X currency", so we divide to get USD
    usd_amount = amount / rate
    logger.debug(
        f"[API] convert_to_usd(): {amount} {from_currency} = {usd_amount} USD (rate: {rate})"
    )
    return usd_amount


def clear_exchange_rate_cache() -> None:
    """Clear the cached exchange rates. Useful for testing or long-running processes."""
    global _exchange_rates_cache
    _exchange_rates_cache = None
