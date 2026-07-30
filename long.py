import MetaTrader5 as mt5
import json
import time
import sys
from colorama import Fore, Style, init as colorama_init

# Initialize colorama for cross‑platform colored terminal output
colorama_init(autoreset=True)

# --- CONFIGURABLE TARGET (change this value in the code if desired) ---
TARGET_POINTS = 80.0 # default target in points (can be overridden by user input)


def main():
    print("=== MT5 Login ===")

    # Get login credentials
    account = input("Enter account number: ")
    password = input("Enter password: ")
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

    # Get target points (optional, default from TARGET_POINTS)
    target_input = input(f"Enter target points (default {TARGET_POINTS}, press Enter to use default): ").strip()
    if target_input == "":
        target_points = TARGET_POINTS
    else:
        try:
            target_points = float(target_input)
            if target_points <= 0:
                raise ValueError("Target points must be positive")
        except ValueError as e:
            print(f"Invalid target points, using default {TARGET_POINTS}")
            target_points = TARGET_POINTS

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
    print(f"Target: {target_points:.1f} points profit → will close automatically.")

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

            # If profit reaches target points or more, close the buy position
            if points >= target_points:
                print("\nTarget profit reached! Closing position...")
                # Send a market sell order to close the buy position
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": mt5.ORDER_TYPE_SELL,
                    "price": tick.bid,          # Sell at bid price
                    "deviation": 20,
                    "magic": 234000,
                    "comment": "close buy",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                close_result = mt5.order_send(close_request)
                if close_result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"Position closed successfully! Sell ticket: {close_result.order}, Price: {close_result.price}")
                    # Update trade_data with closing info
                    trade_data["close_price"] = close_result.price
                    trade_data["close_time"] = time.time()
                    trade_data["profit_points"] = points
                    # Update the last entry in history
                    try:
                        with open("trade_history.json", "r") as f:
                            history = json.load(f)
                        if history:
                            history[-1].update(trade_data)
                        with open("trade_history.json", "w") as f:
                            json.dump(history, f, indent=4)
                    except:
                        pass
                else:
                    print(f"Failed to close position, retcode={close_result.retcode}")
                break  # exit monitoring loop

            time.sleep(1)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

    finally:
        mt5.shutdown()
        print("MT5 shutdown.")


if __name__ == "__main__":
    main()