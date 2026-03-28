# Polymarket Market Making Bot (1H)

## Overview

This project implements a simple market making strategy on Polymarket hourly BTC Up/Down markets.

The bot automatically:
- Identifies the current hourly market (based on Eastern Time)
- Streams the live order book
- Places bid and ask orders
- Manages inventory
- Cancels outdated orders
- Liquidates positions before market resolution

---

## Strategy Logic

The strategy is a basic market making approach:

- Place a buy order (bid) at the best bid price  
- Place a sell order (ask) at the best ask price  
- Continuously update orders when prices change  
- Maintain a maximum inventory limit  
- Exit positions in the last 15 minutes of the market  

---

