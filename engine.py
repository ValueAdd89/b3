import threading
import pandas as pd
import numpy as np
from collections import deque
from polygon import WebSocketClient
from polygon.websocket.models import WebSocketMessage

class PolygonTradingEngine:
    def __init__(self, api_key, symbol="AAPL", max_history=60):
        self.api_key = api_key
        self.symbol = symbol.upper()
        self.max_history = max_history
        self.lock = threading.Lock()
        
        # State Arrays
        self.current_price = 0.0
        self.bids = {}
        self.asks = {}
        self.history = deque(maxlen=max_history)
        self.footprint = {}
        self.alerts = deque(maxlen=15)
        
        self.ws_client = None

    def handle_messages(self, msgs):
        """Processes real-time streams arriving from Polygon's NBBO network"""
        with self.lock:
            for msg in msgs:
                # --- PROCESS LIVE NBBO QUOTES (Liquidity Walls) ---
                if msg.event_type == "Q":  # Q = Quote Event
                    bid_price = float(msg.bid_price)
                    bid_size = float(msg.bid_size)
                    ask_price = float(msg.ask_price)
                    ask_size = float(msg.ask_size)
                    
                    self.current_price = (bid_price + ask_price) / 2.0
                    
                    # Store current inside market liquidity layers
                    self.bids = {bid_price: bid_size}
                    self.asks = {ask_price: ask_size}
                    
                    self.history.append({
                        "time": pd.Timestamp.now(),
                        "price": self.current_price,
                        "bids": self.bids.copy(),
                        "asks": self.asks.copy()
                    })
                    
                # --- PROCESS LIVE TAPE TRADES (Footprint & Blocks) ---
                elif msg.event_type == "T":  # T = Trade Event
                    price = round(float(msg.price), 2)
                    qty = int(msg.size)
                    
                    # Estimate side based on proximity to bid/ask midpoint
                    if self.current_price > 0:
                        is_sell_side = price <= self.current_price
                    else:
                        is_sell_side = True
                    
                    # Update Footprint matrix array
                    if price not in self.footprint:
                        self.footprint[price] = {"Bid_Vol": 0, "Ask_Vol": 0}
                    
                    if is_sell_side:
                        self.footprint[price]["Bid_Vol"] += qty
                    else:
                        self.footprint[price]["Ask_Vol"] += qty
                        
                    # Institutional Stock Block Filter (e.g., individual orders > 10,000 shares)
                    if qty >= 10000:
                        side = "SELL" if is_sell_side else "BUY"
                        self.alerts.append({
                            "time": pd.Timestamp.now().strftime('%H:%M:%S'),
                            "type": "⚠️ EQUITY WHALE BLOCK",
                            "msg": f"Large institutional {side} sweep of {qty:,} shares of {self.symbol} at ${price:,.2f}"
                        })

    def start(self):
        """Spins up a non-blocking background link to Polygon's servers"""
        def run_socket():
            # Subscribes to real-time Trades and Quotes for your specific ticker
            subscriptions = [f"T.{self.symbol}", f"Q.{self.symbol}"]
            self.ws_client = WebSocketClient(
                api_key=self.api_key,
                subscriptions=subscriptions,
                process_message=self.handle_messages
            )
            self.ws_client.run()

        threading.Thread(target=run_socket, daemon=True).start()

    def get_snapshot(self):
        with self.lock:
            return list(self.history), self.bids.copy(), self.asks.copy(), self.current_price, self.footprint.copy(), list(self.alerts)