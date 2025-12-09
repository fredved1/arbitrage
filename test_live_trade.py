#!/usr/bin/env python3
"""
Live Trading Test - Full Cycle

This script executes a complete trading cycle:
1. Check account balance
2. Entry: Buy Spot + Short Perp
3. Wait briefly
4. Exit: Sell Spot + Close Perp
5. Report all fees and costs

Use this to verify the full trading flow with real funds.
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Tuple
import json

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants
from eth_account import Account

import config


class LiveTradingTest:
    """Execute a complete live trading cycle for testing."""
    
    def __init__(self):
        self.account = Account.from_key(config.PRIVATE_KEY)
        self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
        self.exchange = Exchange(
            self.account,
            constants.MAINNET_API_URL,
            account_address=config.ACCOUNT_ADDRESS  # Main wallet
        )
        
        # Trade tracking
        self.entry_spot_fill = None
        self.entry_perp_fill = None
        self.exit_spot_fill = None
        self.exit_perp_fill = None
        
        # Fee tracking
        self.total_fees = 0.0
        self.spot_fees = 0.0
        self.perp_fees = 0.0
        
    def get_account_state(self) -> Dict:
        """Get current account state."""
        try:
            # Get spot balances
            spot_state = self.info.spot_user_state(config.ACCOUNT_ADDRESS)
            
            # Get perp state
            perp_state = self.info.user_state(config.ACCOUNT_ADDRESS)
            
            return {
                "spot": spot_state,
                "perp": perp_state
            }
        except Exception as e:
            print(f"❌ Error getting account state: {e}")
            return {}
    
    def get_current_prices(self) -> Tuple[float, float, float, float]:
        """Get current spot and perp prices."""
        try:
            # Get L2 book for spot
            spot_book = self.info.l2_snapshot(config.SPOT_SYMBOL)
            spot_bid = float(spot_book["levels"][0][0]["px"]) if spot_book["levels"][0] else 0
            spot_ask = float(spot_book["levels"][1][0]["px"]) if spot_book["levels"][1] else 0
            
            # Get L2 book for perp
            perp_book = self.info.l2_snapshot(config.PERP_SYMBOL)
            perp_bid = float(perp_book["levels"][0][0]["px"]) if perp_book["levels"][0] else 0
            perp_ask = float(perp_book["levels"][1][0]["px"]) if perp_book["levels"][1] else 0
            
            return spot_bid, spot_ask, perp_bid, perp_ask
        except Exception as e:
            print(f"❌ Error getting prices: {e}")
            return 0, 0, 0, 0
    
    def get_funding_rate(self) -> float:
        """Get current HYPE funding rate."""
        try:
            meta = self.info.meta()
            for asset in meta.get("universe", []):
                if asset.get("name") == config.PERP_SYMBOL:
                    return float(asset.get("funding", 0))
            return 0.0
        except Exception as e:
            print(f"❌ Error getting funding rate: {e}")
            return 0.0
    
    def place_spot_order(self, is_buy: bool, size: float, price: float) -> Dict:
        """Place a spot order."""
        print(f"   {'Buying' if is_buy else 'Selling'} {size} {config.SPOT_SYMBOL} @ ${price:.4f}")
        
        result = self.exchange.order(
            name=config.SPOT_SYMBOL,
            is_buy=is_buy,
            sz=size,
            limit_px=price,
            order_type={"limit": {"tif": "Ioc"}},  # IOC
            reduce_only=False
        )
        return result
    
    def place_perp_order(self, is_buy: bool, size: float, price: float, reduce_only: bool = False) -> Dict:
        """Place a perpetual order."""
        action = "Closing short" if is_buy and reduce_only else ("Longing" if is_buy else "Shorting")
        print(f"   {action} {size} {config.PERP_SYMBOL} @ ${price:.4f}")
        
        result = self.exchange.order(
            name=config.PERP_SYMBOL,
            is_buy=is_buy,
            sz=size,
            limit_px=price,
            order_type={"limit": {"tif": "Ioc"}},
            reduce_only=reduce_only
        )
        return result
    
    def parse_order_result(self, result: Dict, order_name: str) -> Dict:
        """Parse order result and extract fill info."""
        print(f"\n   {order_name} Result:")
        
        if result.get("status") != "ok":
            print(f"   ❌ Order failed: {result}")
            return {"success": False, "error": str(result)}
        
        response = result.get("response", {})
        if response.get("type") == "order":
            data = response.get("data", {})
            statuses = data.get("statuses", [])
            
            for status in statuses:
                if "filled" in status:
                    filled = status["filled"]
                    total_sz = float(filled.get("totalSz", 0))
                    avg_px = float(filled.get("avgPx", 0))
                    
                    # Calculate fee (taker fee is typically 0.025%)
                    fee = total_sz * avg_px * 0.00025
                    self.total_fees += fee
                    
                    print(f"   ✅ Filled: {total_sz} @ ${avg_px:.4f}")
                    print(f"   💰 Estimated fee: ${fee:.4f}")
                    
                    return {
                        "success": True,
                        "size": total_sz,
                        "price": avg_px,
                        "fee": fee,
                        "oid": filled.get("oid")
                    }
                elif "error" in status:
                    print(f"   ❌ Error: {status['error']}")
                    return {"success": False, "error": status["error"]}
        
        print(f"   ⚠️ Unknown result: {result}")
        return {"success": False, "error": "Unknown result format"}
    
    def run_test(self, size_usd: float = 10.0):
        """
        Run a complete live trading test.
        
        Args:
            size_usd: Position size in USD (default $10)
        """
        print("\n" + "=" * 70)
        print("🐋 PERFECT WHALE - LIVE TRADING TEST")
        print("=" * 70)
        print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💵 Test size: ${size_usd}")
        print(f"📍 Wallet: {config.API_WALLET_ADDRESS[:10]}...{config.API_WALLET_ADDRESS[-8:]}")
        print("=" * 70)
        
        # Step 1: Check account state
        print("\n📊 STEP 1: Checking Account State")
        print("-" * 40)
        state = self.get_account_state()
        
        if "perp" in state:
            perp = state["perp"]
            margin = float(perp.get("marginSummary", {}).get("accountValue", 0))
            print(f"   Perp margin available: ${margin:.2f}")
        
        # Step 2: Get current prices
        print("\n📈 STEP 2: Getting Current Prices")
        print("-" * 40)
        spot_bid, spot_ask, perp_bid, perp_ask = self.get_current_prices()
        
        if spot_ask == 0 or perp_bid == 0:
            print("❌ Failed to get prices. Aborting.")
            return
        
        print(f"   Spot ({config.SPOT_SYMBOL}): Bid ${spot_bid:.4f} / Ask ${spot_ask:.4f}")
        print(f"   Perp ({config.PERP_SYMBOL}): Bid ${perp_bid:.4f} / Ask ${perp_ask:.4f}")
        
        current_spread = (perp_bid - spot_ask) / spot_ask * 100
        print(f"   Current spread: {current_spread:.4f}%")
        
        # Step 3: Get funding rate
        print("\n💹 STEP 3: Checking Funding Rate")
        print("-" * 40)
        funding = self.get_funding_rate()
        funding_direction = "shorts earn" if funding > 0 else "shorts pay"
        print(f"   HYPE funding rate: {funding*100:.4f}% ({funding_direction})")
        
        # Calculate position size
        size = round(size_usd / spot_ask, 2)
        print(f"\n   Position size: {size} HYPE (≈${size * spot_ask:.2f})")
        
        # Step 4: Execute Entry
        print("\n🟢 STEP 4: Executing ENTRY (Buy Spot + Short Perp)")
        print("-" * 40)
        
        # Use slightly aggressive prices to ensure fill
        entry_spot_price = round(spot_ask * 1.001, 4)  # 0.1% above ask
        entry_perp_price = round(perp_bid * 0.999, 4)  # 0.1% below bid
        
        # Place spot buy
        spot_result = self.place_spot_order(
            is_buy=True,
            size=size,
            price=entry_spot_price
        )
        self.entry_spot_fill = self.parse_order_result(spot_result, "Spot Buy")
        
        # Place perp short
        perp_result = self.place_perp_order(
            is_buy=False,
            size=size,
            price=entry_perp_price
        )
        self.entry_perp_fill = self.parse_order_result(perp_result, "Perp Short")
        
        # Check if entry was successful
        if not (self.entry_spot_fill.get("success") and self.entry_perp_fill.get("success")):
            print("\n⚠️ Entry partially failed. Manual cleanup may be needed.")
            self._print_summary()
            return
        
        print("\n✅ Entry complete! Position is now open.")
        
        # Step 5: Wait briefly
        print("\n⏳ STEP 5: Holding position for 5 seconds...")
        print("-" * 40)
        for i in range(5, 0, -1):
            print(f"   {i}...", end="\r")
            time.sleep(1)
        print("   Done!    ")
        
        # Step 6: Execute Exit
        print("\n🔴 STEP 6: Executing EXIT (Sell Spot + Close Perp)")
        print("-" * 40)
        
        # Get fresh prices
        spot_bid, spot_ask, perp_bid, perp_ask = self.get_current_prices()
        print(f"   Current prices: Spot ${spot_bid:.4f} / Perp ${perp_ask:.4f}")
        
        # Use slightly aggressive prices
        exit_spot_price = round(spot_bid * 0.999, 4)  # 0.1% below bid
        exit_perp_price = round(perp_ask * 1.001, 4)  # 0.1% above ask
        
        filled_spot_size = self.entry_spot_fill.get("size", size)
        filled_perp_size = self.entry_perp_fill.get("size", size)
        
        # Sell spot
        spot_result = self.place_spot_order(
            is_buy=False,
            size=filled_spot_size,
            price=exit_spot_price
        )
        self.exit_spot_fill = self.parse_order_result(spot_result, "Spot Sell")
        
        # Close perp short
        perp_result = self.place_perp_order(
            is_buy=True,  # Buy to close short
            size=filled_perp_size,
            price=exit_perp_price,
            reduce_only=True
        )
        self.exit_perp_fill = self.parse_order_result(perp_result, "Perp Close")
        
        # Step 7: Summary
        self._print_summary()
    
    def _print_summary(self):
        """Print comprehensive trade summary."""
        print("\n" + "=" * 70)
        print("📋 TRADE SUMMARY")
        print("=" * 70)
        
        # Entry details
        if self.entry_spot_fill and self.entry_spot_fill.get("success"):
            entry_spot = self.entry_spot_fill
            print(f"\n🟢 ENTRY - Spot Buy:")
            print(f"   Size: {entry_spot['size']} HYPE @ ${entry_spot['price']:.4f}")
            print(f"   Value: ${entry_spot['size'] * entry_spot['price']:.2f}")
            print(f"   Fee: ${entry_spot['fee']:.4f}")
        
        if self.entry_perp_fill and self.entry_perp_fill.get("success"):
            entry_perp = self.entry_perp_fill
            print(f"\n🟢 ENTRY - Perp Short:")
            print(f"   Size: {entry_perp['size']} HYPE @ ${entry_perp['price']:.4f}")
            print(f"   Value: ${entry_perp['size'] * entry_perp['price']:.2f}")
            print(f"   Fee: ${entry_perp['fee']:.4f}")
        
        # Exit details
        if self.exit_spot_fill and self.exit_spot_fill.get("success"):
            exit_spot = self.exit_spot_fill
            print(f"\n🔴 EXIT - Spot Sell:")
            print(f"   Size: {exit_spot['size']} HYPE @ ${exit_spot['price']:.4f}")
            print(f"   Value: ${exit_spot['size'] * exit_spot['price']:.2f}")
            print(f"   Fee: ${exit_spot['fee']:.4f}")
        
        if self.exit_perp_fill and self.exit_perp_fill.get("success"):
            exit_perp = self.exit_perp_fill
            print(f"\n🔴 EXIT - Perp Close:")
            print(f"   Size: {exit_perp['size']} HYPE @ ${exit_perp['price']:.4f}")
            print(f"   Value: ${exit_perp['size'] * exit_perp['price']:.2f}")
            print(f"   Fee: ${exit_perp['fee']:.4f}")
        
        # Calculate P&L
        print("\n" + "-" * 40)
        print("💰 P&L BREAKDOWN")
        print("-" * 40)
        
        if all([self.entry_spot_fill, self.entry_perp_fill, 
                self.exit_spot_fill, self.exit_perp_fill]):
            
            if all([f.get("success") for f in [self.entry_spot_fill, self.entry_perp_fill,
                                                self.exit_spot_fill, self.exit_perp_fill]]):
                # Spot P&L
                spot_pnl = (self.exit_spot_fill["price"] - self.entry_spot_fill["price"]) * self.entry_spot_fill["size"]
                
                # Perp P&L (short, so entry - exit)
                perp_pnl = (self.entry_perp_fill["price"] - self.exit_perp_fill["price"]) * self.entry_perp_fill["size"]
                
                gross_pnl = spot_pnl + perp_pnl
                net_pnl = gross_pnl - self.total_fees
                
                print(f"   Spot P&L: ${spot_pnl:+.4f}")
                print(f"   Perp P&L: ${perp_pnl:+.4f}")
                print(f"   Gross P&L: ${gross_pnl:+.4f}")
                print(f"   Total Fees: ${self.total_fees:.4f}")
                print(f"   ────────────────────")
                print(f"   NET P&L: ${net_pnl:+.4f}")
                
                # ROI
                total_value = self.entry_spot_fill["size"] * self.entry_spot_fill["price"]
                roi = (net_pnl / total_value) * 100 if total_value > 0 else 0
                print(f"   ROI: {roi:+.4f}%")
        
        print("\n" + "=" * 70)
        print(f"⏰ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)


def main():
    """Run the live trading test."""
    print("\n⚠️  WARNING: This will execute REAL trades with REAL money!")
    print("    Press Ctrl+C within 5 seconds to cancel...\n")
    
    try:
        for i in range(5, 0, -1):
            print(f"    Starting in {i}...", end="\r")
            time.sleep(1)
        print("    Starting now!      \n")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
        return
    
    test = LiveTradingTest()
    test.run_test(size_usd=10.0)  # $10 test position


if __name__ == "__main__":
    main()
