# airflow/plugins/sensors/new_filing_sensor.py
"""
Sensor to detect new SEC filings

Monitors SEC for new 10-K/10-Q filings and triggers downstream tasks
"""

from airflow.sensors.base import BaseSensorOperator
from airflow.utils.decorators import apply_defaults
from typing import List
from datetime import datetime, timedelta


class NewFilingSensor(BaseSensorOperator):
    """
    Sensor that detects new SEC filings

    Pokes SEC API periodically to check for new filings.
    Returns True when new filings are detected.

    Args:
        tickers: List of company tickers to monitor
        filing_types: List of filing types (default: ['10-K', '10-Q'])
        lookback_hours: Hours to look back for new filings (default: 24)
        poke_interval: Seconds between pokes (default: 4 hours)
    """

    template_fields = ['tickers', 'filing_types']
    ui_color = '#e8f5e9'

    @apply_defaults
    def __init__(
        self,
        tickers: List[str],
        filing_types: List[str] = None,
        lookback_hours: int = 24,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.tickers = tickers
        self.filing_types = filing_types or ['10-K', '10-Q']
        self.lookback_hours = lookback_hours

        # Set poke interval to 4 hours if not specified
        if 'poke_interval' not in kwargs:
            kwargs['poke_interval'] = 4 * 60 * 60

    def poke(self, context):
        """
        Check if any new filings exist

        Returns:
            True if new filings detected, False otherwise
        """
        # Lazy imports
        import sys
        from pathlib import Path
        sys.path.insert(0, '/opt/airflow')

        from src.data_ingestion.sec_fetcher import SECFetcher
        from src.storage.metadata_store_manager import MetadataStoreManager
        from src.utils.logging_config import get_logger

        logger = get_logger("NewFilingSensor")

        fetcher = SECFetcher()
        db = MetadataStoreManager()

        from_date = (
            datetime.now() - timedelta(hours=self.lookback_hours)
        ).strftime('%Y-%m-%d')

        new_filings_found = []

        for ticker in self.tickers:
            try:
                self.log.info(f"Checking for new {self.filing_types} for {ticker}")

                # Fetch recent filings
                recent_filings = fetcher.fetch_filings(
                    ticker=ticker,
                    filing_types=self.filing_types,
                    from_date=from_date
                )

                # Check which are new
                for filing in recent_filings:
                    if not db.check_filing_exists(filing['accession_number']):
                        new_filings_found.append(filing)
                        self.log.info(
                            f"🆕 New filing detected: {ticker} {filing['filing_type']} "
                            f"(Accession: {filing['accession_number']})"
                        )

            except Exception as e:
                self.log.error(f"Error checking filings for {ticker}: {e}")
                continue

        if new_filings_found:
            self.log.info(f"✅ Found {len(new_filings_found)} new filings")
            # Push to XCom for downstream tasks
            context['task_instance'].xcom_push(
                key='new_filings',
                value=new_filings_found
            )
            return True  # Trigger downstream tasks

        self.log.info("No new filings detected, continuing to wait...")
        return False  # Keep waiting
