"""
WebSocket Manager for Hyperliquid L2 Order Book Streaming

Handles real-time order book updates for both Spot and Perp markets.
Maintains local state of best bid/ask prices for immediate spread calculations.
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional, Any
from dataclasses import dataclass, field
import websockets
from websockets.exceptions import ConnectionClosed

import config

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)


@dataclass
class OrderBookState:
    """Holds the current state of an order book."""
    symbol: str
    best_bid: float = 0.0
    best_ask: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    last_update: float = 0.0
    
    def is_valid(self) -> bool:
        """Check if we have valid prices."""
        return self.best_bid > 0 and self.best_ask > 0


@dataclass
class PriceState:
    """Combined price state for both markets."""
    spot: OrderBookState = field(default_factory=lambda: OrderBookState(symbol=config.SPOT_SYMBOL))
    perp: OrderBookState = field(default_factory=lambda: OrderBookState(symbol=config.PERP_SYMBOL))
    
    def is_ready(self) -> bool:
        """Check if both markets have valid prices."""
        return self.spot.is_valid() and self.perp.is_valid()
    
    def get_entry_spread(self) -> float:
        """
        Calculate entry spread: (Perp_Bid - Spot_Ask) / Spot_Ask
        Positive spread = opportunity to buy spot and short perp
        """
        if not self.is_ready():
            return 0.0
        return (self.perp.best_bid - self.spot.best_ask) / self.spot.best_ask
    
    def get_exit_spread(self) -> float:
        """
        Calculate exit spread: (Perp_Ask - Spot_Bid) / Spot_Bid
        When this goes below exit threshold, close the position
        """
        if not self.is_ready():
            return float('inf')
        return (self.perp.best_ask - self.spot.best_bid) / self.spot.best_bid


class WebSocketManager:
    """
    Manages WebSocket connections to Hyperliquid for L2 order book data.
    
    Features:
    - Subscribes to L2 book for both Spot (@107) and Perp (HYPE)
    - Maintains local price state for low-latency spread calculations
    - Triggers callback on every price update
    - Auto-reconnects on disconnect with exponential backoff
    """
    
    def __init__(self, on_price_update: Optional[Callable[[PriceState], None]] = None):
        """
        Initialize WebSocket manager.
        
        Args:
            on_price_update: Callback function triggered on every price update.
                            Receives PriceState as argument.
        """
        self.ws_url = config.WS_URL
        self.on_price_update = on_price_update
        self.price_state = PriceState()
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._reconnect_delay = config.WS_RECONNECT_DELAY
        
    async def connect(self) -> None:
        """Establish WebSocket connection and start listening."""
        self._running = True
        
        while self._running:
            try:
                logger.info(f"Connecting to WebSocket: {self.ws_url}")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=config.WS_PING_INTERVAL,
                    ping_timeout=10
                ) as ws:
                    self._ws = ws
                    self._reconnect_delay = config.WS_RECONNECT_DELAY  # Reset on successful connect
                    
                    # Subscribe to both order books
                    await self._subscribe_l2_book(config.SPOT_SYMBOL)
                    await self._subscribe_l2_book(config.PERP_SYMBOL)
                    
                    logger.info("✅ WebSocket connected and subscribed to L2 books")
                    
                    # Listen for messages
                    await self._listen()
                    
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self._running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                # Exponential backoff
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    config.WS_RECONNECT_MAX_DELAY
                )
    
    async def _subscribe_l2_book(self, symbol: str) -> None:
        """Subscribe to L2 order book for a symbol."""
        if not self._ws:
            return
            
        subscription = {
            "method": "subscribe",
            "subscription": {
                "type": "l2Book",
                "coin": symbol
            }
        }
        
        await self._ws.send(json.dumps(subscription))
        logger.debug(f"Subscribed to L2 book: {symbol}")
    
    async def _listen(self) -> None:
        """Listen for WebSocket messages and update state."""
        if not self._ws:
            return
            
        async for message in self._ws:
            try:
                data = json.loads(message)
                await self._handle_message(data)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {e}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
    
    async def _handle_message(self, data: Dict[str, Any]) -> None:
        """Process incoming WebSocket message and update price state."""
        channel = data.get("channel")
        
        if channel == "subscriptionResponse":
            logger.debug(f"Subscription confirmed: {data}")
            return
        
        if channel == "l2Book":
            book_data = data.get("data", {})
            coin = book_data.get("coin", "")
            levels = book_data.get("levels", [[], []])
            
            # levels[0] = bids, levels[1] = asks
            bids = levels[0] if len(levels) > 0 else []
            asks = levels[1] if len(levels) > 1 else []
            
            # Get best bid and ask
            best_bid = float(bids[0]["px"]) if bids else 0.0
            best_ask = float(asks[0]["px"]) if asks else 0.0
            bid_size = float(bids[0]["sz"]) if bids else 0.0
            ask_size = float(asks[0]["sz"]) if asks else 0.0
            
            # Update appropriate order book
            import time
            timestamp = time.time()
            
            if coin == config.SPOT_SYMBOL:
                self.price_state.spot = OrderBookState(
                    symbol=coin,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    bid_size=bid_size,
                    ask_size=ask_size,
                    last_update=timestamp
                )
                logger.debug(f"Spot update: bid={best_bid}, ask={best_ask}")
                
            elif coin == config.PERP_SYMBOL:
                self.price_state.perp = OrderBookState(
                    symbol=coin,
                    best_bid=best_bid,
                    best_ask=best_ask,
                    bid_size=bid_size,
                    ask_size=ask_size,
                    last_update=timestamp
                )
                logger.debug(f"Perp update: bid={best_bid}, ask={best_ask}")
            
            # Trigger callback if set
            if self.on_price_update and self.price_state.is_ready():
                self.on_price_update(self.price_state)
    
    def get_prices(self) -> PriceState:
        """Get current price state."""
        return self.price_state
    
    async def disconnect(self) -> None:
        """Gracefully disconnect from WebSocket."""
        self._running = False
        if self._ws:
            await self._ws.close()
            logger.info("WebSocket disconnected")
    
    async def test_connection(self) -> bool:
        """
        Test the WebSocket connection.
        Returns True if connection is successful and receives data.
        """
        try:
            logger.info("Testing WebSocket connection...")
            
            async with websockets.connect(self.ws_url, close_timeout=5) as ws:
                # Subscribe to perp book as a test
                subscription = {
                    "method": "subscribe",
                    "subscription": {
                        "type": "l2Book",
                        "coin": config.PERP_SYMBOL
                    }
                }
                await ws.send(json.dumps(subscription))
                
                # Wait for response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)
                
                logger.info(f"✅ Connection test successful! Received: {data.get('channel')}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False


# Quick test
if __name__ == "__main__":
    async def on_update(state: PriceState):
        spread = state.get_entry_spread()
        print(f"Spot: {state.spot.best_bid}/{state.spot.best_ask} | "
              f"Perp: {state.perp.best_bid}/{state.perp.best_ask} | "
              f"Spread: {spread*100:.4f}%")
    
    async def main():
        manager = WebSocketManager(on_price_update=on_update)
        
        # Test connection first
        if await manager.test_connection():
            print("\n--- Starting live feed (Ctrl+C to stop) ---\n")
            await manager.connect()
    
    asyncio.run(main())
