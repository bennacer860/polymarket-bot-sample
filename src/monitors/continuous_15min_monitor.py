"""Continuous monitor for 15-minute crypto markets."""

import asyncio
from typing import Optional

from .multi_event_monitor import MultiEventMonitor
from ..markets.fifteen_min import get_market_slug, get_current_15m_utc, MarketSelection
from ..logging_config import get_logger

logger = get_logger(__name__)


class ContinuousFifteenMinMonitor:
    """Monitor that continuously tracks the current 15-minute market."""

    def __init__(
        self,
        market_selections: list[MarketSelection],
        output_file: str = "bids_0999.csv",
        ws_url: Optional[str] = None,
        check_interval: int = 60,
        ticker_change_file: str = "ticker_changes.csv",
    ):
        """
        Initialize the continuous 15-minute monitor.

        Args:
            market_selections: List of crypto assets to monitor (e.g., ["BTC", "ETH"])
            output_file: CSV file to save bid data
            ws_url: Optional WebSocket URL override
            check_interval: How often to check if markets are still active (seconds)
            ticker_change_file: CSV file to save ticker change events
        """
        self.market_selections = market_selections
        self.output_file = output_file
        self.ws_url = ws_url
        self.check_interval = check_interval
        self.ticker_change_file = ticker_change_file
        self.running = False
        self.current_monitor: Optional[MultiEventMonitor] = None

    def get_current_slugs(self) -> list[str]:
        """Get slugs for the current 15-minute period for all selected markets."""
        timestamp = get_current_15m_utc()
        slugs = []
        
        for selection in self.market_selections:
            try:
                slug = get_market_slug(selection, timestamp)
                slugs.append(slug)
                logger.debug("Current slug for %s: %s", selection, slug)
            except ValueError as e:
                logger.error("Failed to get slug for %s: %s", selection, e)
        
        return slugs

    async def run(self):
        """Run the continuous monitor."""
        logger.info(
            "Starting continuous 15-minute monitor for: %s",
            ", ".join(self.market_selections),
        )
        
        self.running = True
        
        while self.running:
            # Get slugs for the current 15-minute period
            current_slugs = self.get_current_slugs()
            
            if not current_slugs:
                logger.error("No valid slugs generated. Waiting 60 seconds before retry.")
                await asyncio.sleep(60)
                continue
            
            logger.info("Monitoring current 15-minute markets: %s", ", ".join(current_slugs))
            
            # Create and run monitor for these slugs
            self.current_monitor = MultiEventMonitor(
                event_slugs=current_slugs,
                output_file=self.output_file,
                ws_url=self.ws_url,
                check_interval=self.check_interval,
                ticker_change_file=self.ticker_change_file,
            )
            
            # Run the monitor (it will exit when all markets end)
            await self.current_monitor.run()
            
            logger.info("Current 15-minute period ended. Transitioning to next period.")
            
            # Small delay before starting next period
            await asyncio.sleep(5)
        
        logger.info("Continuous monitor stopped")

    def run_sync(self):
        """Run the monitor synchronously (blocking)."""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            logger.info("Continuous monitor stopped by user")
            self.running = False
