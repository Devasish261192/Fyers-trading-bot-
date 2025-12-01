import json
import os
import sys
import datetime as dt

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from candle_df_multiprocessor import MultiTimeframeProcessor
from plotly_live_plotter import DashPlotter

plotter = DashPlotter()

def stream_json_file(file_path, on_message, delay=0):
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    on_message(item)
                except json.JSONDecodeError as e:
                    print(f"Skipping invalid JSON line: {e}")

def on_message_factory(processor):
    def on_message(message):
        try:
            processor.process_tick(message=message)
        except TypeError as e:
            print(e)
    return on_message

if __name__ == "__main__":
    timeframes_to_process = [1, 3]
    trading_timeframe = 3
    
    # Specify the single data file to process
    data_file = os.path.join(project_root, r'ws_logs\Ws_120125\ws_120125_raw.txt')
    journal_path = 'trade_journal.csv'

    # Define the path to the historical data file
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '01_bot_configuration', 'file_folder_configuration.txt')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    hdf_file_path = os.path.join(config['hdf_files_folder'], 'index_data.h5')

    print(f"\n{ '=' * 40 }\n--- Processing single file: {os.path.basename(data_file)} ---\n{ '=' * 40 }")

    # --- Pre-fetch historical data based on the test file's date ---
    try:
        date_str = os.path.basename(data_file).split('_')[1]
        test_date = dt.datetime.strptime(date_str, '%m%d%y')
        # Set end_date to one second before the test date to include the full previous day.
        end_date = test_date - dt.timedelta(seconds=1)
        start_date = test_date - dt.timedelta(days=30)
        print(f"Test date identified: {test_date.strftime('%Y-%m-%d')}")
        print(f"Fetching historical data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    except (IndexError, ValueError) as e:
        print(f"Could not parse date from filename: {os.path.basename(data_file)}. Error: {e}")
        sys.exit(1) # Exit if we can't determine the date context

    processor = MultiTimeframeProcessor(
        timeframes=timeframes_to_process,
        trading_timeframe=trading_timeframe,
        hdf_file_path=hdf_file_path,
        mode='test',
        plotter=plotter
    )
    
    # Load the historical data BEFORE processing ticks
    df_1m = processor.signal_generator.fetch_historical_data('NSE:NIFTY50-INDEX', start_date, end_date)
    processor.signal_generator.load_pre_fetched_data(df_1m)
    
    # Set starting capital for the test run
    starting_capital = 30000
    processor.trade_manager.set_capital(starting_capital)
    print(f"--- Starting test with capital: {starting_capital} ---")
    
    on_message_callback = on_message_factory(processor)

    print(f"\n--- Streaming live ticks from {os.path.basename(data_file)}... ---")
    stream_json_file(data_file, on_message_callback)

    processor.trade_manager.print_statistics()
    # processor.trade_manager.save_trades_to_journal(os.path.basename(data_file), journal_path)

    # print(f"\n--- Single file processed. Trade journal saved to {journal_path} ---")