"""SEC EDGAR API client for fetching company filings."""

import logging
import time
from typing import Optional

from curl_cffi import requests

from stock_index_info.models import SECFilingRecord, RecentFilings

logger = logging.getLogger(__name__)


# SEC requires a User-Agent header with contact info
SEC_USER_AGENT = "StockIndexInfoBot contact@example.com"


def get_cik_from_ticker(ticker: str) -> Optional[str]:
    """Get CIK (Central Index Key) from ticker symbol.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        CIK as string without leading zeros, or None if not found
    """
    ticker_upper = ticker.upper()
    url = "https://www.sec.gov/files/company_tickers.json"

    logger.info(f"[API] get_cik_from_ticker({ticker_upper}): requesting SEC company tickers")
    start_time = time.time()

    try:
        response = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30,
        )
        elapsed_ms = (time.time() - start_time) * 1000
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"[API] get_cik_from_ticker({ticker_upper}): "
            f"response status={response.status_code}, elapsed={elapsed_ms:.0f}ms"
        )

        # Data format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
        for entry in data.values():
            if entry.get("ticker") == ticker_upper:
                cik = str(entry["cik_str"])
                logger.info(f"[API] get_cik_from_ticker({ticker_upper}): found CIK={cik}")
                return cik

        logger.warning(f"[API] get_cik_from_ticker({ticker_upper}): ticker not found in SEC data")
        return None
    except requests.RequestsError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_cik_from_ticker({ticker_upper}): "
            f"request failed after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_cik_from_ticker({ticker_upper}): "
            f"unexpected error after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


def get_latest_10q(ticker: str) -> Optional[SECFilingRecord]:
    """Get the latest 10-Q filing for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        SECFilingRecord with filing details, or None if not found
    """
    ticker_upper = ticker.upper()
    logger.info(f"[API] get_latest_10q({ticker_upper}): looking up CIK")

    cik = get_cik_from_ticker(ticker)
    if cik is None:
        logger.warning(f"[API] get_latest_10q({ticker_upper}): CIK lookup failed")
        return None

    # Pad CIK to 10 digits for API
    cik_padded = cik.zfill(10)

    # Query company submissions endpoint
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    logger.info(f"[API] get_latest_10q({ticker_upper}): requesting {url}")
    start_time = time.time()

    try:
        response = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30,
        )
        elapsed_ms = (time.time() - start_time) * 1000
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"[API] get_latest_10q({ticker_upper}): "
            f"response status={response.status_code}, elapsed={elapsed_ms:.0f}ms"
        )

        # Find latest 10-Q in recent filings
        recent_filings = data.get("filings", {}).get("recent", {})
        forms = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        filing_dates = recent_filings.get("filingDate", [])
        primary_documents = recent_filings.get("primaryDocument", [])

        for i, form in enumerate(forms):
            if form == "10-Q":
                accession = accession_numbers[i].replace("-", "")
                filing_date = filing_dates[i]
                primary_doc = primary_documents[i]

                filing_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"
                )

                logger.info(
                    f"[API] get_latest_10q({ticker_upper}): found 10-Q filed on {filing_date}"
                )
                return SECFilingRecord(
                    ticker=ticker_upper,
                    form_type="10-Q",
                    filing_date=filing_date,
                    filing_url=filing_url,
                )

        logger.warning(f"[API] get_latest_10q({ticker_upper}): no 10-Q filings found")
        return None
    except requests.RequestsError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_latest_10q({ticker_upper}): "
            f"request failed after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_latest_10q({ticker_upper}): "
            f"unexpected error after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None


def get_recent_filings(ticker: str) -> Optional[RecentFilings]:
    """Get the latest 4 quarterly (10-Q) and 1 annual (10-K) filings for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        RecentFilings with quarterly and annual filings, or None if ticker not found
    """
    ticker_upper = ticker.upper()
    logger.info(f"[API] get_recent_filings({ticker_upper}): looking up CIK")

    cik = get_cik_from_ticker(ticker)
    if cik is None:
        logger.warning(f"[API] get_recent_filings({ticker_upper}): CIK lookup failed")
        return None

    # Pad CIK to 10 digits for API
    cik_padded = cik.zfill(10)

    # Query company submissions endpoint
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    logger.info(f"[API] get_recent_filings({ticker_upper}): requesting {url}")
    start_time = time.time()

    try:
        response = requests.get(
            url,
            headers={"User-Agent": SEC_USER_AGENT},
            timeout=30,
        )
        elapsed_ms = (time.time() - start_time) * 1000
        response.raise_for_status()
        data = response.json()

        logger.info(
            f"[API] get_recent_filings({ticker_upper}): "
            f"response status={response.status_code}, elapsed={elapsed_ms:.0f}ms"
        )

        # Extract filing arrays
        recent_filings = data.get("filings", {}).get("recent", {})
        forms = recent_filings.get("form", [])
        accession_numbers = recent_filings.get("accessionNumber", [])
        filing_dates = recent_filings.get("filingDate", [])
        primary_documents = recent_filings.get("primaryDocument", [])

        quarterly: list[SECFilingRecord] = []
        annual: Optional[SECFilingRecord] = None

        for i, form in enumerate(forms):
            accession = accession_numbers[i].replace("-", "")
            filing_date = filing_dates[i]
            primary_doc = primary_documents[i]

            filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{primary_doc}"

            if form == "10-Q" and len(quarterly) < 4:
                quarterly.append(
                    SECFilingRecord(
                        ticker=ticker_upper,
                        form_type="10-Q",
                        filing_date=filing_date,
                        filing_url=filing_url,
                    )
                )
            elif form == "10-K" and annual is None:
                annual = SECFilingRecord(
                    ticker=ticker_upper,
                    form_type="10-K",
                    filing_date=filing_date,
                    filing_url=filing_url,
                )

            # Early exit if we have all we need
            if len(quarterly) == 4 and annual is not None:
                break

        logger.info(
            f"[API] get_recent_filings({ticker_upper}): "
            f"found {len(quarterly)} quarterly and {'1 annual' if annual else '0 annual'} filings"
        )
        return RecentFilings(quarterly=quarterly, annual=annual)
    except requests.RequestsError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_recent_filings({ticker_upper}): "
            f"request failed after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}"
        )
        return None
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(
            f"[API] get_recent_filings({ticker_upper}): "
            f"unexpected error after {elapsed_ms:.0f}ms - {type(e).__name__}: {e}",
            exc_info=True,
        )
        return None
