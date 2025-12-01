import sys
import os

# Add the project root to the Python path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import pandas as pd
from candle_df_multiprocessor import MultiTimeframeProcessor

# --- Helper Functions (from test_run.py) ---

def stream_json_file(file_path, on_message, delay=0):
    """Reads a file containing one JSON object per line and streams it."""
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    item = json.loads(line)
                    on_message(item)
                except json.JSONDecodeError as e:
                    print(f"Skipping invalid JSON line in {os.path.basename(file_path)}: {e}")

def on_message_factory(processor):
    """Factory to create the on_message callback."""
    def on_message(message):
        try:
            processor.process_tick(message=message)
        except Exception as e:
            print(f"Error processing tick: {e}")
    return on_message

# --- Main Runner Logic ---

def run_full_backtest(test_data_folder):
    """
    Runs the backtest simulation on all .txt files in a given folder,
    tracks capital, and generates a consolidated trade journal.
    """
    # --- Configuration ---
    timeframes_to_process = [1, 3]
    trading_timeframe = 3
    starting_principal = 25000.0
    current_principal = starting_principal
    
    # Get the path for the HDF5 file from the main config
    config_path = os.path.join(os.path.dirname(__file__), '..', '01_bot_configuration', 'file_folder_configuration.txt')
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    hdf_file_path = os.path.join(config['hdf_files_folder'], 'index_data.h5')

    # --- Data Collection ---
    all_trades = []
    
    # Find all test files in the directory
    try:
        test_files = [f for f in os.listdir(test_data_folder) if f.endswith('.txt')]
        if not test_files:
            print(f"Error: No .txt files found in '{test_data_folder}'")
            return
    except FileNotFoundError:
        print(f"Error: Directory not found at '{test_data_folder}'")
        return

    print(f"--- Starting Full Backtest ---")
    print(f"Found {len(test_files)} files in '{os.path.basename(test_data_folder)}'.")
    print(f"Initial Principal: {starting_principal:.2f}\n")

    # --- Main Loop ---
    for filename in sorted(test_files):
        file_path = os.path.join(test_data_folder, filename)
        print(f"--- Processing file: {filename} ---")

        # Instantiate a new processor for each file to ensure a clean state
        processor = MultiTimeframeProcessor(
            timeframes=timeframes_to_process,
            trading_timeframe=trading_timeframe,
            hdf_file_path=hdf_file_path,
            mode='test',
            plotter=None  # Disable plotter for speed
        )
        
        # Set the capital for the upcoming day's trades
        processor.trade_manager.set_capital(current_principal)
        
        on_message_callback = on_message_factory(processor)
        stream_json_file(file_path, on_message_callback)

        # Collect trades and update capital from the completed run
        day_trades = processor.trade_manager.completed_trades
        if day_trades:
            day_pnl = sum(trade['pnl'] for trade in day_trades)
            current_principal += day_pnl
            print("\n" + "="*40)
            print(f"Found {len(day_trades)} trades. Day P&L: {day_pnl:.2f}. New Principal: {current_principal:.2f}")
            print("\n" + "="*40)
            all_trades.extend(day_trades)
        else:
            print("No trades were executed for this day.")
        print("-" * 40)

    # --- Reporting ---
    if not all_trades:
        print("\n--- Full backtest complete. No trades were executed across all files. ---")
        return

    print("\n--- Full Backtest Complete. Generating Report... ---")
    
    # Create a detailed DataFrame
    journal_df = pd.DataFrame(all_trades)

    # Ensure all required columns are present
    required_cols = {
        'entry_time': 'Entry Time',
        'exit_time': 'Exit Time',
        'symbol': 'Symbol',
        'type': 'Trade Type',
        'actual_entry_price': 'Entry Price',
        'exit_price': 'Exit Price',
        'initial_sl_price': 'Stop-Loss',
        'pnl': 'P&L',
        'exit_reason': 'Exit Reason',
        'initial_lots': 'Lots'
    }
    journal_df = journal_df.rename(columns=required_cols)
    
    # Calculate running capital
    journal_df['P&L'] = journal_df['P&L'].astype(float)
    total_pnl = journal_df['P&L'].sum()
    final_capital = starting_principal + total_pnl
    journal_df['Capital'] = starting_principal + journal_df['P&L'].cumsum()

    # Reorder columns for clarity
    display_cols = [
        'Entry Time', 'Exit Time', 'Symbol', 'Trade Type', 'Lots', 'Entry Price', 
        'Exit Price', 'Stop-Loss', 'P&L', 'Capital', 'Exit Reason'
    ]
    # Add any columns that might be missing in the display list but are in the dataframe
    existing_cols = [col for col in display_cols if col in journal_df.columns]
    journal_df = journal_df[existing_cols]

    # Save the consolidated journal
    output_path = os.path.join(os.path.dirname(__file__), '..', 'all_trades_journal.csv')
    journal_df.to_csv(output_path, index=False)
    
    print(f"\nConsolidated trade journal saved to: {output_path}")
    
    # --- Final Summary ---
    print("\n" + "="*40)
    print("      FULL BACKTEST SUMMARY")
    print("="*40)
    print(f"Starting Principal: {starting_principal:15.2f}")
    print(f"Total P&L:          {total_pnl:15.2f}")
    print(f"Final Capital:        {final_capital:15.2f}")
    print("="*40)


if __name__ == "__main__":
    # The script expects the folder path as a command-line argument.
    # If no argument is given, it will use the default path from your request.
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = os.path.join(project_root, 'websocket_raw_data')
        print(f"No folder path provided. Using default: '{folder_path}'")
    
    run_full_backtest(folder_path)
