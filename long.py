import MetaTrader5 as mt5
import json
import time
import sys
from colorama import Fore, Style, init as colorama_init

# Initialize colorama for cross‑platform colored terminal output
colorama_init(autoreset=True)


def main():
    print("=== MT5 Login ===")

    # Get login credentials
    account = input("Enter account number: ")
    password = ("Enter password: ")
    server = input("Enter server name: ")

    # Initialize MT5 connection
    if not mt5.initialize():
        print("MT5 initialization failed")
        sys.exit(1)

    # Log in to the trading account
    authorized = mt5.login(login=int(account), password=password, server=server)
    if not authorized:
        print(f"Login failed, error: {mt5.last_error()}")
        mt5.shutdown()
        sys.exit(1)

    # Retrieve and display account information
    account_info = mt5.account_info()
    if account_info:
        print(f"Login successful!\nAccount: {account_info.login} | Balance: {account_info.balance:.2f} USD")
    else:
        print("Failed to get account info")
        mt5.shutdown()
        sys.exit(1)

    # Ask for symbol and validate it
    symbol = input("Enter symbol (e.g., XAUUSD, EURUSD): ").strip().upper()
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found")
        mt5.shutdown()
        sys.exit(1)

    # Ensure the symbol is available for trading
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"Failed to select symbol {symbol}")
            mt5.shutdown()
            sys.exit(1)

    # Get lot size from user
    try:
        lot = float(input("Enter base lot size (e.g., 0.01): "))
        if lot <= 0:
            raise ValueError("Lot size must be positive")
    except ValueError as e:
        print(f"Invalid lot size: {e}")
        mt5.shutdown()
        sys.exit(1)

    # Prepare market buy order
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
        "price": tick.ask,          # Buy at ask price
        "deviation": 20,            # Slippage tolerance in points
        "magic": 234000,
        "comment": "python bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Send the order
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed, retcode={result.retcode}")
        mt5.shutdown()
        sys.exit(1)

    print(f"Buy order placed successfully! Ticket: {result.order}, Volume: {lot}, Price: {result.price}")

    # Save trade details to JSON
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

    # Get symbol point size (smallest price change)
    point = symbol_info.point

    print("\nMonitoring price... Press Ctrl+C to stop.")
    print(f"Buy price: {result.price:.2f}")

    try:
        while True:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print("Error getting tick")
                break

            current_price = tick.bid      # For a buy position, current value is bid price
            diff = current_price - result.price
            points = diff / point

            # Choose colour based on profit/loss
            if points > 0:
                color = Fore.GREEN
                sign = "+"
            elif points < 0:
                color = Fore.RED
                sign = ""
            else:
                color = Fore.WHITE
                sign = " "

            # Overwrite the same line with the updated price and point difference
            print(f"\r{color}Current price: {current_price:.2f} | Points: {sign}{points:.1f} points{Style.RESET_ALL}", end="")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

    finally:
        mt5.shutdown()
        print("MT5 shutdown.")


if __name__ == "__main__":
    main()