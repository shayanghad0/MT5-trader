import MetaTrader5 as mt5
import json
import time
import sys
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)


def main():
    print("=== MT5 Login ===")

    account = input("Enter account number: ")
    password = input("Enter password: ")          # no getpass
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

    # Ask for order type
    order_type = input("Enter order type (buy/sell): ").strip().lower()
    if order_type not in ("buy", "sell"):
        print("Invalid order type. Use 'buy' or 'sell'.")
        mt5.shutdown()
        sys.exit(1)

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Cannot get tick for {symbol}")
        mt5.shutdown()
        sys.exit(1)

    # Prepare request based on type
    if order_type == "buy":
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": 234000,
            "comment": "python bot buy",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        open_price = tick.ask
    else:  # sell
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "deviation": 20,
            "magic": 234000,
            "comment": "python bot sell",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        open_price = tick.bid

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order failed, retcode={result.retcode}")
        mt5.shutdown()
        sys.exit(1)

    print(f"{order_type.capitalize()} order placed! Ticket: {result.order}, Volume: {lot}, Price: {result.price}")

    # Save trade details
    trade_data = {
        "ticket": result.order,
        "symbol": symbol,
        "volume": lot,
        "open_price": result.price,
        "time": time.time(),
        "type": order_type
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
    print("\nMonitoring price... Press Ctrl+C to stop.")
    print(f"Open price: {result.price:.2f}")

    try:
        while True:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print("Error getting tick")
                break

            # For buy: current = bid, diff = current - open
            # For sell: current = ask, diff = open - current (profit when price drops)
            if order_type == "buy":
                current_price = tick.bid
                diff = current_price - result.price
            else:  # sell
                current_price = tick.ask
                diff = result.price - current_price

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
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        mt5.shutdown()
        print("MT5 shutdown.")


if __name__ == "__main__":
    main()