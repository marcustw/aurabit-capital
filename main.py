from __future__ import annotations
import asyncio
from functools import reduce
import os
from threading import Thread
from typing import Optional

import websocket
import json
import requests
import re
import math
import signal
import sys
from multiprocessing import Pool
from dataclasses import dataclass

HOST = "stream.binance.com"
PORT = 9443
PATH = "/ws"
URI = f"wss://{HOST}:{PORT}{PATH}"

BINANCE_API_BASE = "https://api1.binance.com/api/v3"
EXCHANGE_INFO_PATH = "/exchangeInfo"
TICKER_24HR_PATH = "/ticker/24hr"

EXCHANGE_INFO_URI = f"{BINANCE_API_BASE}{EXCHANGE_INFO_PATH}"
TICKER_24HR_URI = f"{BINANCE_API_BASE}{TICKER_24HR_PATH}"

REQUEST_MESSAGE = lambda symbol : f"{symbol}@trade"

USD_PEGGED_COIN = "USDT"

TAU = 10

@dataclass
class TradeResponse:
    e: str    # Event type
    E: int    # Event time
    s: str    # Symbol
    t: int    # Trade ID
    p: float  # Price
    q: int    # Quantity
    b: int    # Buyer order ID
    a: int    # Seller order ID
    T: int    # Trade time
    m: bool   # Is the buyer the market maker
    M: bool   # ignore


class TradingPair:
    def __init__(self, base_currency: str, quote_currency: str):
        self._base_currency = base_currency
        self._quote_currency = quote_currency
    
    def get_quote_usdt(self) -> TradingPair:
        return TradingPair(self._quote_currency, USD_PEGGED_COIN)

    def get_base_usdt(self) -> TradingPair:
        return TradingPair(self._base_currency, USD_PEGGED_COIN)
    
    def get_symbol_lower(self) -> str:
        return f"{self._base_currency}{self._quote_currency}".lower()
    
    def get_symbol_upper(self) -> str:
        return f"{self._base_currency}{self._quote_currency}".upper()
    
    def __str__(self):
        return f"{self._base_currency}/{self._quote_currency}".upper()


quote_usdt_ltp = {}
base_ema = {}
base_t = {}
base_usdt_24hr_vol = {}

class WebSocketClient:
    def __init__(self, target_symbol: str):
        self._symbols = self._get_symbols(target_symbol)
        self._trading_pairs = self._get_trading_pairs(self._symbols)
        self._setup()
    
    def _setup(self):
        def _get_24hr_usd_volume(trading_pair_symbol, quote_usdt_symbol, usdt_quote_symbol) -> float:
            res = requests.get(TICKER_24HR_URI, params={"symbol": trading_pair_symbol})
            volume = float(res.json()["volume"])
            res = requests.get(TICKER_24HR_URI, params={"symbol": quote_usdt_symbol})
            try:
                wap = float(res.json()["weightedAvgPrice"])
            except KeyError:
                res = requests.get(TICKER_24HR_URI, params={"symbol": usdt_quote_symbol})
                wap = 1.0 / float(res.json()["weightedAvgPrice"])
            return volume * wap

        for trading_pair in self._trading_pairs.values():
            base_usdt_24hr_vol[trading_pair.get_symbol_upper()] = _get_24hr_usd_volume(
                trading_pair.get_symbol_upper(),
                trading_pair.get_quote_usdt().get_symbol_upper(),
                (TradingPair(USD_PEGGED_COIN, trading_pair._quote_currency)).get_symbol_upper()
            )
    
    def _get_symbols(self, target_symbol):
        regex = f"^{target_symbol}.*"
        predicate = re.compile(regex)
        res = requests.get(EXCHANGE_INFO_URI)
        return set([symbol["symbol"] for symbol in res.json()["symbols"] if predicate.match(symbol["symbol"]) and not symbol["symbol"].endswith(USD_PEGGED_COIN)])
    
    def _get_trading_pairs(self, symbols):
        return {
            symbol: TradingPair(target_symbol, symbol[len(target_symbol):]) for symbol in symbols
        }
        
    def _calculate_alpha(self, t2, symbol):
        if self._t1 == None:
            return -1.0
        return math.exp(-(t2 - base_t[symbol]) / TAU)
        
    def _on_message(self, ws, message):
        data = json.loads(message)
        if "result" in data and data["result"] == None:
            print("Null data", data)
            return
        data = TradeResponse(**data)
        if data.s not in self._symbols:  # data.s is YYY/USDT
            quote_usdt_ltp[data.s] = float(data.p)
            # print(f"Set quote_usdt_ltp[{data.s}] = {float(data.p)}")
            return
        quote_usdt_pair = self._trading_pairs[data.s].get_quote_usdt().get_symbol_upper()
        if data.s not in base_ema:
            if quote_usdt_ltp[quote_usdt_pair] is None:
                # print("quote_usdt_ltp is None")
                return
            
            # initialise EMA
            base_ema[data.s] = float(data.p) * quote_usdt_ltp[quote_usdt_pair]
            base_t[data.s] = int(data.T, data.s)
            return
        
        alpha = self._calculate_alpha(data.T)
        base_ema[data.s] = alpha * base_ema[data.s] + (1 - alpha) * data.p
        base_t[data.s] = int(data.T, data.s)

    def _on_error(self, ws, error):
        print("Error:", ws, "-", error)

    def _on_close(self, ws, close_status_code, close_msg):
        print("Closed:", ws, "-", close_status_code, "-", close_msg)

    def _on_open(self, ws):
        params = [f"{trading_pair.get_symbol_lower()}@trade" for trading_pair in self._trading_pairs.values()] + [
            f"{trading_pair.get_quote_usdt().get_symbol_lower()}@trade" for trading_pair in self._trading_pairs.values()]
        def on_open(ws):
            print("Connected")
            subscribe_msg = {
                "method": "SUBSCRIBE",
                "params": params,
                "id": 1,
            }
            ws.send(json.dumps(subscribe_msg))
            print("Subscribed")
        return on_open
    
    async def run(self):
        ws = websocket.WebSocketApp(URI,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close)
        ws.on_open = self._on_open(ws)
        websocket.enableTrace(True)
        self.ws = ws
        self.ws.run_forever()
    
    def __str__(self):
        return f"WebSocketClient({self._trading_pair}), USDT pegged: {self._trading_pair.get_complement()})"
    
    def calculate_weighted_average(self):
        total_vol = sum([base_usdt_24hr_vol[symbol] for symbol in base_ema.keys()])
        total_price_vol = sum([base_usdt_24hr_vol[symbol] * base_ema[symbol] for symbol in base_ema.keys()])
        return total_price_vol / total_vol

if __name__ == "__main__":
    target_symbol: str = sys.argv[1] if len(sys.argv) > 1 else "SOL"
    print(target_symbol)
    ws_client = WebSocketClient(target_symbol)
    try:
        asyncio.run(ws_client.run())
    except KeyboardInterrupt:
        # print("======> KeyboardInterrupt")
        # print("Volume:", base_usdt_24hr_vol)
        # print("EMA:", base_ema)
        print(ws_client.calculate_weighted_average())
        ws_client.ws.close()