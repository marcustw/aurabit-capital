# Aurabit-Capital

## Binance Websocket Stream
Request
```json
{
    "method": "SUBSCRIBE",
    "params":
        [
            "btcusdt@aggTrade",
            "btcusdt@depth"
        ],
    "id": 1
}
```

Response
```json
{
  "e": "trade",     // Event type
  "E": 123456789,   // Event time
  "s": "BNBBTC",    // Symbol
  "t": 12345,       // Trade ID
  "p": "0.001",     // Price
  "q": "100",       // Quantity
  "b": 88,          // Buyer order ID
  "a": 50,          // Seller order ID
  "T": 123456785,   // Trade time
  "m": true,        // Is the buyer the market maker?
  "M": true         // Ignore
}
```

## Binance API
GET /ticker/24hr?symbol=SOLUSDT

Response:
```json
{
  "symbol": "BNBBTC",
  "priceChange": "-94.99999800",
  "priceChangePercent": "-95.960",
  "weightedAvgPrice": "0.29628482",
  "prevClosePrice": "0.10002000",
  "lastPrice": "4.00000200",
  "lastQty": "200.00000000",
  "bidPrice": "4.00000000",
  "bidQty": "100.00000000",
  "askPrice": "4.00000200",
  "askQty": "100.00000000",
  "openPrice": "99.00000000",
  "highPrice": "100.00000000",
  "lowPrice": "0.10000000",
  "volume": "8913.30000000",
  "quoteVolume": "15.30000000",
  "openTime": 1499783499040,
  "closeTime": 1499869899040,
  "firstId": 28385,   // First tradeId
  "lastId": 28460,    // Last tradeId
  "count": 76         // Trade count
}
```

## EMA Calculation
$$
EMA[i] = α EMA[i-1] + (1-α) X[i]
$$

## Running Application
```bash
python -m venv env
source env/bin/activate
pip install -r requirements.txt
python main.py [TARGET_SYMBOL] # default target_symbol = SOL
```

### Notes
- Completed in Python because of the simplicity of Websockets in Python
- Cpp will be added soon