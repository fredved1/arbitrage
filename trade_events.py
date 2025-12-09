"""
Trade Events - Shared state between bot and dashboard
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any
from dataclasses import dataclass, asdict
import threading

EVENTS_FILE = "trade_events.json"

@dataclass
class TradeEvent:
    timestamp: str
    event_type: str  # "entry", "exit", "opportunity", "error"
    message: str
    details: Dict[str, Any] = None
    
    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "message": self.message,
            "details": self.details or {}
        }

class TradeEventManager:
    """Manages trade events for communication between bot and dashboard."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._events = []
            cls._instance._trades_executed = 0
            cls._instance._total_pnl = 0.0
            cls._instance._current_position = None
            cls._instance._load()
        return cls._instance
    
    def _load(self):
        """Load events from file."""
        if os.path.exists(EVENTS_FILE):
            try:
                with open(EVENTS_FILE, 'r') as f:
                    data = json.load(f)
                    self._events = data.get("events", [])[-100:]  # Keep last 100
                    self._trades_executed = data.get("trades_executed", 0)
                    self._total_pnl = data.get("total_pnl", 0.0)
                    self._current_position = data.get("current_position")
            except:
                pass
    
    def _save(self):
        """Save events to file."""
        with self._lock:
            data = {
                "events": self._events[-100:],
                "trades_executed": self._trades_executed,
                "total_pnl": self._total_pnl,
                "current_position": self._current_position,
                "last_update": datetime.now().isoformat()
            }
            with open(EVENTS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
    
    def add_event(self, event_type: str, message: str, details: Dict = None):
        """Add a trade event."""
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            message=message,
            details=details
        )
        self._events.append(event.to_dict())
        self._save()
    
    def entry_executed(self, size: float, spot_price: float, perp_price: float, spread: float):
        """Record an entry trade."""
        self._current_position = {
            "size": size,
            "entry_spot": spot_price,
            "entry_perp": perp_price,
            "entry_spread": spread,
            "entry_time": datetime.now().isoformat()
        }
        self.add_event(
            "entry",
            f"🟢 ENTRY: {size} HYPE @ Spot ${spot_price:.2f}, Perp ${perp_price:.2f}",
            {"size": size, "spot_price": spot_price, "perp_price": perp_price, "spread": spread}
        )
    
    def exit_executed(self, size: float, spot_price: float, perp_price: float, net_pnl: float):
        """Record an exit trade."""
        self._trades_executed += 1
        self._total_pnl += net_pnl
        self._current_position = None
        self.add_event(
            "exit",
            f"🔴 EXIT: {size} HYPE @ Spot ${spot_price:.2f}, Perp ${perp_price:.2f} | P&L: ${net_pnl:+.4f}",
            {"size": size, "spot_price": spot_price, "perp_price": perp_price, "net_pnl": net_pnl}
        )
    
    def error(self, message: str, details: Dict = None):
        """Record an error."""
        self.add_event("error", f"⚠️ ERROR: {message}", details)
    
    def get_events(self, limit: int = 50) -> List[Dict]:
        """Get recent events."""
        self._load()  # Refresh from file
        return self._events[-limit:]
    
    def get_stats(self) -> Dict:
        """Get current stats."""
        self._load()  # Refresh from file
        return {
            "trades_executed": self._trades_executed,
            "total_pnl": self._total_pnl,
            "current_position": self._current_position
        }
    
    def reset(self):
        """Reset all events and stats."""
        self._events = []
        self._trades_executed = 0
        self._total_pnl = 0.0
        self._current_position = None
        self._save()


# Global instance
trade_events = TradeEventManager()
