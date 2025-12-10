"""Exchange rate utilities for currency conversion."""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from curl_cffi import requests

logger = logging.getLogger(__name__)

# Cache expiration time in seconds (24 hours)
_CACHE_EXPIRATION_SECONDS = 24 * 60 * 60


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
    global _exchange_rates_cache

    # Check if cache exists and is not expired
    if _exchange_rates_cache is not None:
        age = time.time() - _exchange_rates_cache.timestamp
        if age < _CACHE_EXPIRATION_SECONDS:
            return _exchange_rates_cache.rates
        else:
            logger.debug(f"Exchange rate cache expired (age: {age:.0f}s), refreshing")

    try:
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("result") != "success":
            logger.warning(f"Exchange rate API returned non-success: {data}")
            return None

        rates_data = data.get("rates")
        if not rates_data:
            logger.warning("Exchange rate API returned no rates")
            return None

        rates: dict[str, float] = dict(rates_data)
        _exchange_rates_cache = _ExchangeRateCache(rates=rates, timestamp=time.time())
        logger.debug(f"Fetched exchange rates for {len(rates)} currencies")
        return rates

    except Exception as e:
        logger.warning(f"Failed to fetch exchange rates: {type(e).__name__}: {e}")
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

    rates = get_exchange_rates()
    if rates is None:
        return None

    rate = rates.get(from_currency)
    if rate is None:
        logger.warning(f"No exchange rate found for {from_currency}")
        return None

    if rate <= 0:
        logger.warning(f"Invalid exchange rate for {from_currency}: {rate}")
        return None

    # rates are "1 USD = X currency", so we divide to get USD
    usd_amount = amount / rate
    return usd_amount


def clear_exchange_rate_cache() -> None:
    """Clear the cached exchange rates. Useful for testing or long-running processes."""
    global _exchange_rates_cache
    _exchange_rates_cache = None
