This ensures it always trades the active hourly market.
## Key Features

### 1. Dynamic Market Selection

The bot generates the correct Polymarket slug using US Eastern Time:
---

### 2. Orderbook Streaming

The bot continuously fetches:
- Best bid
- Best ask

Using Polymarket CLOB API.

---

### 3. Order Management

- Cancels outdated orders if prices move  
- Keeps only one active bid and one active ask  
- Prevents stale orders from staying in the book  

---

### 4. Inventory Control

- Maximum position: `MAX_SHARES`  
- Order size: `ORDER_SIZE`  
- Avoids overexposure  

---

### 5. Risk Management

- Stops trading and closes positions in the last 15 minutes  
- Cancels all open orders  
- Sells remaining inventory at market  

---

## Architecture

The bot is structured into two main asynchronous loops:

### `stream_orderbook()`
- Detects current market
- Updates prices
- Maintains global state

### `trading_loop()`
- Executes trading logic
- Places/cancels orders
- Manages risk and inventory

Both run concurrently using `asyncio`.

---

## Requirements

- Python 3.9+
- Polymarket API access
- Environment variable: