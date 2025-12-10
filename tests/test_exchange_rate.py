"""Tests for exchange rate module."""


def test_get_exchange_rates():
    """Test fetching exchange rates from API."""
    from stock_index_info.exchange_rate import get_exchange_rates, clear_exchange_rate_cache

    clear_exchange_rate_cache()
    rates = get_exchange_rates()

    assert rates is not None
    assert "USD" in rates
    assert rates["USD"] == 1.0  # Base currency
    assert "EUR" in rates
    assert "DKK" in rates
    assert "GBP" in rates
    assert "JPY" in rates
    # Rates should be positive
    assert all(rate > 0 for rate in rates.values())


def test_get_exchange_rates_cached():
    """Test that exchange rates are cached."""
    from stock_index_info.exchange_rate import get_exchange_rates, clear_exchange_rate_cache

    clear_exchange_rate_cache()

    # First call fetches from API
    rates1 = get_exchange_rates()
    # Second call should return cached rates
    rates2 = get_exchange_rates()

    assert rates1 is rates2  # Same object (cached)


def test_convert_to_usd_same_currency():
    """Test conversion when currency is already USD."""
    from stock_index_info.exchange_rate import convert_to_usd

    result = convert_to_usd(1000.0, "USD")

    assert result == 1000.0


def test_convert_to_usd_dkk():
    """Test conversion from DKK to USD."""
    from stock_index_info.exchange_rate import (
        convert_to_usd,
        get_exchange_rates,
        clear_exchange_rate_cache,
    )

    clear_exchange_rate_cache()

    # Get actual DKK rate
    rates = get_exchange_rates()
    assert rates is not None
    dkk_rate = rates["DKK"]

    # Convert 1000 DKK to USD
    dkk_amount = 1000.0
    result = convert_to_usd(dkk_amount, "DKK")

    assert result is not None
    expected = dkk_amount / dkk_rate
    assert abs(result - expected) < 0.01


def test_convert_to_usd_eur():
    """Test conversion from EUR to USD."""
    from stock_index_info.exchange_rate import (
        convert_to_usd,
        get_exchange_rates,
        clear_exchange_rate_cache,
    )

    clear_exchange_rate_cache()

    # Get actual EUR rate
    rates = get_exchange_rates()
    assert rates is not None
    eur_rate = rates["EUR"]

    # Convert 1000 EUR to USD
    eur_amount = 1000.0
    result = convert_to_usd(eur_amount, "EUR")

    assert result is not None
    expected = eur_amount / eur_rate
    assert abs(result - expected) < 0.01


def test_convert_to_usd_unknown_currency():
    """Test conversion with unknown currency returns None."""
    from stock_index_info.exchange_rate import convert_to_usd, clear_exchange_rate_cache

    clear_exchange_rate_cache()

    result = convert_to_usd(1000.0, "INVALID_CURRENCY")

    assert result is None


def test_clear_exchange_rate_cache():
    """Test clearing the exchange rate cache."""
    from stock_index_info.exchange_rate import (
        get_exchange_rates,
        clear_exchange_rate_cache,
    )
    from stock_index_info import exchange_rate

    clear_exchange_rate_cache()
    assert exchange_rate._exchange_rates_cache is None

    get_exchange_rates()
    assert exchange_rate._exchange_rates_cache is not None

    clear_exchange_rate_cache()
    assert exchange_rate._exchange_rates_cache is None
