#!/usr/bin/env python3
"""
Delta Neutral Arbitrage Bot - Entry Point

Perfect Wheel Strategy for Hyperliquid
HYPE Spot (@107) vs HYPE Perpetual

Usage:
    python main.py             # Run with dry_run mode (default)
    python main.py --live      # Run live trading (BE CAREFUL!)
    python main.py --test      # Test WebSocket connection only
"""

import asyncio
import signal
import sys
import argparse
import logging

import config
from bot import ArbitrageBot
from websocket_manager import WebSocketManager

# Configure root logger
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('arbitrage_bot.log')
    ]
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print startup banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   🐋 PERFECT WHALE - Delta Neutral Arbitrage Bot             ║
    ║                                                               ║
    ║   Strategy: HYPE Spot (@107) vs HYPE Perpetual               ║
    ║   Platform: Hyperliquid                                       ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)


async def test_connection():
    """Test WebSocket connection and show sample data."""
    print("\n🔌 Testing WebSocket connection...\n")
    
    manager = WebSocketManager()
    
    if await manager.test_connection():
        print("\n✅ Connection successful!")
        print("\n📊 Fetching sample prices for 10 seconds...\n")
        
        # Create a task to show prices
        received_count = [0]
        
        def on_update(prices):
            received_count[0] += 1
            spread = prices.get_entry_spread()
            threshold_met = "🟢 ENTRY" if spread > config.MIN_SPREAD_THRESHOLD else "⚪️"
            print(f"[{received_count[0]:3d}] Spot: ${prices.spot.best_ask:.4f} | "
                  f"Perp: ${prices.perp.best_bid:.4f} | "
                  f"Spread: {spread*100:+.4f}% {threshold_met}")
        
        manager = WebSocketManager(on_price_update=on_update)
        
        # Run for 10 seconds
        try:
            async def run_for_seconds(seconds):
                task = asyncio.create_task(manager.connect())
                await asyncio.sleep(seconds)
                await manager.disconnect()
                task.cancel()
            
            await run_for_seconds(10)
            
        except asyncio.CancelledError:
            pass
        
        print(f"\n📈 Received {received_count[0]} price updates in 10 seconds")
        return True
    else:
        print("\n❌ Connection failed!")
        return False


async def run_bot(live_mode: bool = False):
    """Run the arbitrage bot."""
    
    # Override dry_run if live mode specified
    if live_mode:
        config.DRY_RUN = False
        logger.warning("⚠️ LIVE TRADING MODE ENABLED - Real orders will be placed!")
    else:
        config.DRY_RUN = True
        logger.info("📝 DRY RUN MODE - No real orders will be placed")
    
    bot = ArbitrageBot()
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info("\n🛑 Shutdown signal received...")
        asyncio.create_task(shutdown(bot))
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await bot.run()


async def shutdown(bot: ArbitrageBot):
    """Graceful shutdown."""
    logger.info("Shutting down bot...")
    if bot.ws_manager:
        await bot.ws_manager.disconnect()
    
    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    
    logger.info("Shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Delta Neutral Arbitrage Bot for Hyperliquid"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test WebSocket connection only"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading (disables dry_run)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        config.LOG_LEVEL = "DEBUG"
    
    print_banner()
    
    print(f"📋 Configuration:")
    print(f"   Wallet: {config.API_WALLET_ADDRESS[:10]}...{config.API_WALLET_ADDRESS[-8:]}")
    print(f"   Spot Symbol: {config.SPOT_SYMBOL}")
    print(f"   Perp Symbol: {config.PERP_SYMBOL}")
    print(f"   Entry Threshold: {config.MIN_SPREAD_THRESHOLD*100:.2f}%")
    print(f"   Exit Threshold: {config.EXIT_THRESHOLD*100:.2f}%")
    print(f"   Max Position: ${config.MAX_POSITION_USD}")
    print(f"   Dry Run: {config.DRY_RUN if not args.live else False}")
    print()
    
    try:
        if args.test:
            asyncio.run(test_connection())
        else:
            if args.live:
                print("⚠️  WARNING: Live trading mode!")
                print("    Press Ctrl+C within 5 seconds to cancel...")
                import time
                time.sleep(5)
            
            asyncio.run(run_bot(live_mode=args.live))
            
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
