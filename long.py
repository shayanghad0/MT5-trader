import MetaTrader5 as mt5
import json
import time
import sys
from colorama import Fore, Style, init as colorama_init

# ========== CONFIGURABLE THRESHOLD (TAKE-PROFIT ONLY) ==========
# Set this to a number (e.g., 80) to skip the prompt.
# Leave as None to be prompted for input.
THRESHOLD_POINTS = None   # <-- Change to 80 to use fixed value without prompt
# ===============================================================

colorama_init(autoreset=True)


def close_position(symbol, ticket, volume, price, deviation=20):
    """Close a buy position with a market sell order."""
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": mt5.ORDER_TYPE_SELL,
        "position": ticket,
        "price": price,
        "deviation": deviation,
        "magic": 234000,
        "comment": "close bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    return mt5.order_send(request)


def main():
    print("=== MT5 Login ===")

    account = input("Enter account number: ")
    password = input("Enter password: ")
    server = input("Enter server name: ")

    if not mt5.initialize():
        print("MT5 initialization failed")
        sys.exit(1)

    authorized = mt5.login(login=int(account), password=password, server=server)
    if not authorized:
        print(f"Login failed, error: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    account_info = mt5.account_info()
    if account_info:
        print(f"Login successful!\nAccount: {account_info.login} | Balance: {account_info.balance:.2f} USD")
    else:
        print("Failed to get account info")
        mt5.shutdown()
        sys.exit(1)

    symbol = input("Enter symbol (e.g., XAUUSD, EURUSD): ").strip().upper()
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found")
        mt5.shutdown()
        sys.exit(1)

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select symbol {symbol}")
            mt5.shutdown()
            sys.exit(1)

    try:
        lot = float(input("Enter base lot size (e.g., 0.01): "))
        if lot <= 0:
            raise ValueError("Lot size must be positive")
    except ValueError as e:
        print(f"Invalid lot size: {e}")
        mt5.shutdown()
        sys.exit(1)

    # ---------- Threshold handling (Take‑Profit only) ----------
    global THRESHOLD_POINTS
    threshold = THRESHOLD_POINTS
    if threshold is None:
        while True:
            try:
                threshold = float(input("Enter TAKE‑PROFIT points (e.g., 80): "))
                if threshold <= 0:
                    print("Threshold must be positive.")
                    continue
                break
            except ValueError:
                print("Please enter a valid number.")
    else:
        print(f"Using preset take‑profit threshold: {threshold} points")

    # ---------- Place buy order ----------
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Cannot get tick for {symbol}")
        mt5.shutdown()
        sys.exit(1)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "deviation": 20,
        "magic": 234000,
        "comment": "python bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed, retcode={result.retcode}")
        mt5.shutdown()
        sys.exit(1)

    print(f"Buy order placed successfully! Ticket: {result.order}, Volume: {lot}, Price: {result.price}")

    # Save trade details
    trade_data = {
        "ticket": result.order,
        "symbol": symbol,
        "volume": lot,
        "open_price": result.price,
        "time": time.time(),
        "type": "buy"
    }
    try:
        with open("trade_history.json", "r") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = []
    history.append(trade_data)
    with open("trade_history.json", "w") as f:
        json.dump(history, f, indent=4)

    point = symbol_info.point
    entry_price = result.price
    ticket = result.order

    print("\nMonitoring price... Press Ctrl+C to stop.")
    print(f"Buy price: {entry_price:.2f}")
    print(f"Auto‑close will trigger ONLY when profit reaches {threshold} points (no stop‑loss).")

    try:
        while True:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print("Error getting tick")
                break

            current_price = tick.bid
            diff = current_price - entry_price
            points = diff / point

            if points > 0:
                color = Fore.GREEN
                sign = "+"
            elif points < 0:
                color = Fore.RED
                sign = ""
            else:
                color = Fore.WHITE
                sign = " "

            print(f"\r{color}Current price: {current_price:.2f} | Points: {sign}{points:.1f} points{Style.RESET_ALL}", end="")

            # ---- CLOSE ONLY ON PROFIT (positive points) ----
            if points >= threshold:
                print(f"\n\nProfit target reached: {points:.1f} points. Closing position...")
                close_result = close_position(symbol, ticket, lot, tick.bid)
                if close_result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"Position closed successfully. Close price: {close_result.price}")
                else:
                    print(f"Failed to close position, retcode={close_result.retcode}")
                break

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

    finally:
        mt5.shutdown()
        print("MT5 shutdown.")


if __name__ == "__main__":
    main()