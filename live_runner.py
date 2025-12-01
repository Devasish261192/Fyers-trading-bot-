import json
import os
import time
import sys
import datetime as dt

# Add the parent directory to sys.path for module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws, order_ws
from candle_df_multiprocessor import MultiTimeframeProcessor
from plotly_live_plotter import DashPlotter

# Import from final_scripts
from final_scripts.get_access_token import get_access_token
from final_scripts import utilities as utils
from final_scripts import option_chain as opc
from final_scripts.historical import HisData_bydate

# --- Configuration Loading ---
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '01_bot_configuration', 'file_folder_configuration.txt')
with open(config_path, 'r', encoding='utf-8') as f:
    config = json.load(f)

# --- Fyers API Setup ---
current_date_str = dt.datetime.now().strftime('%Y-%m-%d')
access_token = get_access_token()
credentials_path = config['credentials_file']
creds = utils.load_credentials(credentials_path)
client_id = creds['client_id']
log_folder_path = os.path.join(config['api_logs'], current_date_str)
os.makedirs(log_folder_path, exist_ok=True)

fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path=log_folder_path)
profile = fyers.get_profile()
print("Fyers Profile:", profile)

# --- Websocket Logging Setup ---
WS_LOGS_BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ws_logs')
date_for_logs = dt.datetime.now().strftime("%m%d%y")
WS_DATE_DIR = os.path.join(WS_LOGS_BASE_DIR, f"Ws_{date_for_logs}")
os.makedirs(WS_DATE_DIR, exist_ok=True)

# --- TIME-BASED STARTUP LOGIC ---
def wait_for_market_open():
    now = dt.datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if now < market_open:
        wait_seconds = (market_open - now).total_seconds()
        print(f"Market not open. Waiting for {wait_seconds:.0f} seconds until 09:15 AM...")
        time.sleep(wait_seconds)



# --- Dynamic Symbol Generation ---
def get_ws_symbols(fyers_instance):
    symbols_to_trade = ["NSE:NIFTY50-INDEX"]
    try:
        option_chain_data = opc.options_chain_for_trade(symbols_to_trade[0], 20, fyers_instance)
        expiries_list = sorted(list(option_chain_data.keys()), key=lambda x: dt.datetime.strptime(x, '%d-%m-%Y') if '-' in x else dt.datetime.strptime(x, '%Y%m%d'))
        trading_expiry = expiries_list[0]
        trading_option_chain_df = option_chain_data[trading_expiry]
        filtered_chain = trading_option_chain_df[(trading_option_chain_df['ltp'] > 40) & (trading_option_chain_df['ltp'] < 300)]
        option_symbols = list(filtered_chain['symbol'])
        ws_symbols = symbols_to_trade + option_symbols

        # Save config
        json_config_file = os.path.join(WS_DATE_DIR, f"ws_config_{date_for_logs}.json")
        config_data = {"ws_symbols": ws_symbols, "expiry_date": trading_expiry}
        with open(json_config_file, "w") as f:
            json.dump(config_data, f)
        print(f"Config saved: {len(ws_symbols)} symbols, expiry: {trading_expiry}")
        return ws_symbols
    except Exception as e:
        print(f"Error getting option chain: {e}. Subscribing to Nifty index only.")
        return symbols_to_trade

# --- Websocket Callbacks ---
def on_message_factory(processor):
    def on_message(message):
        with open(os.path.join(WS_DATE_DIR, f"ws_{date_for_logs}_raw.txt"), "a") as f:
            f.write(json.dumps(message) + "\n")
        try:
            processor.process_tick(message=message)
        except Exception as e:
            print(f"Error processing tick: {e}")
    return on_message

def format_order_update(message):
    """Formats the raw order update message into a readable string."""
    try:
        if isinstance(message, str):
            message = json.loads(message)
        
        if not isinstance(message, dict) or 'orders' not in message:
            return f"Raw Order Update: {message}"

        order = message['orders']
        
        side_map = {1: "BUY", -1: "SELL"}
        type_map = {1: "LIMIT", 2: "MARKET", 3: "STOP", 4: "STOP-LIMIT"}
        status_map = {
            1: "CANCELED", 2: "TRADED", 4: "PENDING", 
            5: "REJECTED", 6: "PENDING", 8: "TRANSIT"
        }

        symbol = order.get('symbol', 'N/A')
        side = side_map.get(order.get('side'), 'N/A')
        order_type = type_map.get(order.get('type'), 'N/A')
        status = status_map.get(order.get('status'), 'N/A')
        qty = order.get('qty', 'N/A')
        price = order.get('tradedPrice') or order.get('limitPrice') or 'N/A'
        order_id = order.get('id', 'N/A')

        return (
            f"\n--- ORDER UPDATE ---\n"
            f"  ID: {order_id}\n"
            f"  Symbol: {symbol}\n"
            f"  Side: {side} | Type: {order_type} | Status: {status}\n"
            f"  Qty: {qty} | Price: {price}\n"
            f"--------------------"
        )
    except Exception as e:
        return f"Error formatting order update: {e}\nRaw message: {message}"

def on_order_update_factory(processor):
    def on_order_update(message):
        with open(os.path.join(WS_DATE_DIR, f"ws_order_updates_{date_for_logs}.txt"), "a") as f:
            f.write(str(message) + "\n")
        
        print(format_order_update(message))
        
        try:
            # Ensure message is a dict for processing
            if isinstance(message, str): 
                message = json.loads(message)
            
            if 'orders' in message:
                processor.process_order_update(message['orders'])
            else:
                print("Received non-standard order update:", message)
        except Exception as e:
            print(f"Error processing order update: {e}")
    return on_order_update

def on_error(message): print("Error:", message)
def on_close(message): print("Connection closed:", message)

def on_open_data_factory(symbols_list):
    def on_open():
        data_type = "SymbolUpdate"
        fyers_data_ws.subscribe(symbols=symbols_list, data_type=data_type)
        fyers_data_ws.keep_running()
        print(f"WebSocket opened - subscribed to {len(symbols_list)} symbols")
    return on_open

def on_open_order_factory():
    def on_open():
        data_type = "OnOrders,OnTrades,OnPositions,OnGeneral"
        fyers_order_ws.subscribe(data_type=data_type)
        fyers_order_ws.keep_running()
        print("Order WebSocket opened - subscribed to order updates")
    return on_open

# --- Main Execution ---
if __name__ == "__main__":
    # --- Bot Configuration ---
    timeframes_to_process = [1, 3]
    trading_timeframe = 3
    real_trade = False # <<<< SET TO TRUE FOR LIVE TRADING >>>>
    hdf_file_path = os.path.join(config['hdf_files_folder'], 'index_data.h5')

    # --- Initialize Components ---
    plotter = DashPlotter()
    processor = MultiTimeframeProcessor(
        timeframes=timeframes_to_process,
        trading_timeframe=trading_timeframe,
        hdf_file_path=hdf_file_path,
        mode='live',
        fyers_model=fyers,
        plotter=plotter,
        real_trade=real_trade
    )

    # --- Time-based Startup Logic ---
    now = dt.datetime.now()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    
    if now < market_open:
        # --- SCENARIO 1: PRE-MARKET START ---
        print(f"--- Bot started before 09:15. Waiting for market to open... ---")
        wait_for_market_open()

    # --- POST-MARKET START or CONTINUATION FROM PRE-MARKET ---
    print("--- Market is open. Bot starting. Will fetch historical data after collecting initial ticks. ---")
    ws_symbols = get_ws_symbols(fyers)

    # --- Set Capital for Live Trading ---
    try:
        funds_response = fyers.funds()
        if funds_response.get('s') == 'ok' and 'fund_limit' in funds_response:
            available_balance_item = next((item for item in funds_response['fund_limit'] if item['title'] == 'Available Balance'), None)
            if available_balance_item:
                live_capital = available_balance_item['equityAmount']
                print(f"\n--- Fetched Live Capital: {live_capital:.2f} ---")
                processor.trade_manager.set_capital(live_capital)
            else:
                print("Could not find 'Available Balance' in funds response.")
        else:
            print(f"Failed to fetch funds: {funds_response.get('message', 'No error message')}.")
    except Exception as e:
        print(f"An error occurred while fetching funds: {e}.")

    # --- Setup and Connect Websockets ---
    ws_access_token = f"{client_id}:{access_token}"
    
    if not ws_symbols:
        print("--- ws_symbols list is empty, fetching again... ---")
        ws_symbols = get_ws_symbols(fyers)

    fyers_order_ws = order_ws.FyersOrderSocket(
        access_token=ws_access_token, write_to_file=False, log_path="", reconnect=True,
        on_connect=on_open_order_factory(),
        on_close=on_close, on_error=on_error, on_orders=on_order_update_factory(processor)
    )

    fyers_data_ws = data_ws.FyersDataSocket(
        access_token=ws_access_token, log_path="", litemode=False, write_to_file=False, reconnect=True,
        on_connect=on_open_data_factory(ws_symbols),
        on_close=on_close, on_error=on_error, on_message=on_message_factory(processor)
    )

    print("Connecting to Fyers Order Websocket...")
    fyers_order_ws.connect()
    print("Connecting to Fyers Data Websocket...")
    fyers_data_ws.connect()
