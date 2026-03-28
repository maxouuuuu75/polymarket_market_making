import os
import time
import json
import asyncio
import aiohttp
import requests
from dotenv import load_dotenv

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.clob_types import OpenOrderParams

from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

load_dotenv()

HOST = "https://clob.polymarket.com"
CHAIN_ID = 137

private_key = os.getenv("PRIVATE_KEY_POLYMARKET")

# client polymarket
temp_client = ClobClient(HOST, key=private_key, chain_id=CHAIN_ID)
api_creds = temp_client.create_or_derive_api_creds()

client = ClobClient(
    HOST,
    key=private_key,
    chain_id=CHAIN_ID,
    creds=api_creds,
    signature_type=1,
    funder="0xdaf613dc39c35142BCCa60d9D60fD5844980b05f"
)

client.set_api_creds(client.create_or_derive_api_creds())

print("Wallet:", client.get_address())


# paramètres
MAX_SHARES = 15
ORDER_SIZE = 5
SLEEP_TIME = 10

open_orders = []

state = {
    "slug": None,
    "token_id": None,
    "event_id": None,
    "question_id": None,
    "best_bid": None,
    "best_ask": None,
    "bids": [],
    "asks": [],
    "last_slot": None,

    # suivi des ordres actifs
    "current_bid_order": None,
    "current_ask_order": None,
    "current_bid_price": None,
    "current_ask_price": None
}

from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+

def get_hourly_slug():
    # Heure actuelle en ET
    now_et = datetime.now(ZoneInfo("America/New_York"))
    
    hour = now_et.hour
    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12
    am_pm = "am" if hour < 12 else "pm"
    
    month = now_et.strftime("%B").lower()  # 'march'
    day = now_et.day
    
    slug = f"bitcoin-up-or-down-{month}-{day}-{hour_12}{am_pm}-et"
    return slug

print(get_hourly_slug())

def clean_old_orders(token_id, bid, ask):

    try:

        orders = client.get_orders(
            OpenOrderParams(asset_id=token_id)
        )

        for order in orders:

            price = float(order["price"])
            order_id = order["id"]
            side = order["side"]

            if side == "BUY" and price != bid:

                print("Cancel outdated BID:", price)
                client.cancel(order_id)

            if side == "SELL" and price != ask:

                print("Cancel outdated ASK:", price)
                client.cancel(order_id)

    except Exception as e:

        print("Order cleaning error:", e)
# ----------------------------------
# stream orderbook
# ----------------------------------


async def stream_orderbook():
    async with aiohttp.ClientSession() as session:

        last_slug = None

        while True:
            # --- 1️⃣ Générer le slug horaire ET ---
            now_et = datetime.now(ZoneInfo("America/New_York"))
            hour = now_et.hour
            hour_12 = hour % 12
            if hour_12 == 0:
                hour_12 = 12
            am_pm = "am" if hour < 12 else "pm"

            month = now_et.strftime("%B").lower()  # 'march'
            day = now_et.day

            slug = f"bitcoin-up-or-down-{month}-{day}-{hour_12}{am_pm}-et"

            # --- 2️⃣ Changement de marché ---
            if slug != last_slug:
                url_market = f"https://gamma-api.polymarket.com/markets/slug/{slug}"
                try:
                    async with session.get(url_market, timeout=5) as resp_market:
                        if resp_market.status == 200:
                            market = await resp_market.json()
                            clob_ids = json.loads(market["clobTokenIds"])
                            state["token_id"] = clob_ids[0]
                            state["slug"] = market["slug"]

                            events = market.get("events", [])
                            state["event_id"] = events[0]["id"] if events else None
                            state["question_id"] = market.get("questionID")

                            last_slug = slug
                            print(f"\n[{time.strftime('%H:%M:%S')}] Nouveau marché : {state['slug']}")
                            print(f"Event ID : {state['event_id']}, Question ID : {state['question_id']}")

                except Exception as e:
                    print("Market fetch error:", e)

            # --- 3️⃣ Récupérer orderbook ---
            token_id = state["token_id"]
            if token_id:
                url_book = f"{HOST}/book?token_id={token_id}"
                try:
                    async with session.get(url_book, timeout=5) as resp_book:
                        if resp_book.status == 200:
                            ob = await resp_book.json()
                            bids = ob.get("bids", [])
                            asks = ob.get("asks", [])
                            if bids and asks:
                                state["best_bid"] = float(bids[-1]["price"])
                                state["best_ask"] = float(asks[-1]["price"])
                                # facultatif : garder les top bids/asks
                                state["bids"] = bids
                                state["asks"] = asks

                                print(state["best_bid"] )
                except Exception as e:
                    print("Orderbook error:", e)

            await asyncio.sleep(0.3)
# ----------------------------------
# inventory
# ----------------------------------

def get_inventory(event_id):

    address = "0xdaf613dc39c35142BCCa60d9D60fD5844980b05f"

    url = f"https://data-api.polymarket.com/positions?user={address}&sizeThreshold=1&limit=100&sortBy=TOKENS&sortDirection=DESC"

    try:

        resp = requests.get(url)

        if resp.status_code != 200:

            print("Erreur positions:", resp.status_code)
            return 0

        positions = resp.json()

        for pos in positions:

            if pos.get("eventId") == event_id:
                return float(pos.get("size", 0))

    except Exception as e:

        print("Erreur get_inventory:", e)

    return 0


# ----------------------------------
# trading loop
# ----------------------------------
async def trading_loop():

    while True:

        bid = state.get("best_bid")
        ask = state.get("best_ask")
        token_id = state.get("token_id")
        event_id = state.get("event_id")

        if not bid or not ask:

            await asyncio.sleep(1)
            continue

        now = int(time.time())
        period = 60 * 60
        time_left = period - (now % period)

        print("\nMarket snapshot")
        print("Bid:", bid)
        print("Ask:", ask)
        print("Time left:", time_left)
        clean_old_orders(token_id, bid, ask)

        try:
            inventory = get_inventory(event_id)
        except Exception as e:
            print("Erreur get_inventory:", e)
            inventory = 0

        print("Inventory:", inventory)

        # ----------------------------------
        # liquidation 15 dernières minutes
        # ----------------------------------

        if time_left < 15 * 60:

            print("⚠️ Last 15 minutes → closing position")

            try:
                client.cancel_market_orders(asset_id=token_id)
                print("Orders for this token cancelled")
            except Exception as e:
                print("Cancel error:", e)

            if inventory > 0:

                try:

                    sell_order = OrderArgs(
                        price=bid,
                        size=inventory,
                        side="SELL",
                        token_id=token_id
                    )

                    signed = client.create_order(sell_order)

                    client.post_order(signed, OrderType.GTC)

                    print("Position closed")

                except Exception as e:

                    print("Erreur liquidation:", e)

            await asyncio.sleep(SLEEP_TIME)
            continue

        spread = ask - bid
        print("Spread:", spread)

        # ----------------------------------
        # BID LOGIC
        # ----------------------------------

        if inventory < MAX_SHARES and token_id:

            size = max(ORDER_SIZE, MAX_SHARES - inventory)

            if state["current_bid_price"] != bid:

                if state["current_bid_order"]:

                    try:
                        client.cancel(state["current_bid_order"])
                        print("Old BID cancelled")
                    except Exception as e:
                        print("Cancel BID error:", e)

                try:

                    buy_order = OrderArgs(
                        price=bid,
                        size=size,
                        side="BUY",
                        token_id=token_id
                    )

                    signed = client.create_order(buy_order)

                    resp = client.post_order(signed, OrderType.GTC)

                    state["current_bid_order"] = resp.get("orderID")
                    state["current_bid_price"] = bid

                    print("New BID placed")

                except Exception as e:

                    print("Erreur BUY:", e)

        # ----------------------------------
        # ASK LOGIC
        # ----------------------------------

        if inventory > 0 and token_id:

            if state["current_ask_price"] != ask:

                if state["current_ask_order"]:

                    try:
                        client.cancel(state["current_ask_order"])
                        print("Old ASK cancelled")
                    except Exception as e:
                        print("Cancel ASK error:", e)

                try:

                    sell_order = OrderArgs(
                        price=ask,
                        size=inventory,
                        side="SELL",
                        token_id=token_id
                    )

                    signed = client.create_order(sell_order)

                    resp = client.post_order(signed, OrderType.GTC)

                    state["current_ask_order"] = resp.get("orderID")
                    state["current_ask_price"] = ask

                    print("New ASK placed")

                except Exception as e:

                    print("Erreur SELL:", e)

        print("Sleep")

        await asyncio.sleep(SLEEP_TIME)
# ----------------------------------
# main
# ----------------------------------

async def main():

    await asyncio.gather(
        stream_orderbook(),
#        trading_loop()
    )


await main()


