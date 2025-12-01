# Fyers Websocket Trend Bot

## Overview

This is a Python-based trading bot that connects to the Fyers websocket to receive live market data for the NIFTY50 index and its options. It implements a multi-timeframe trading strategy to generate signals and can execute trades in both paper and live modes. The bot also includes features for backtesting and live visualization of market data.

## Features

- **Live Data Processing**: Connects to the Fyers websocket for real-time tick data.
- **Multi-Timeframe Analysis**: Processes data into multiple timeframes (1-minute and 3-minute candles).
- **Strategy-Based Trading**: Generates trading signals based on a combination of indicators on the 3-minute timeframe.
- **Live & Paper Trading**: Can be run in a paper trading mode for testing or a live trading mode to execute real trades.
- **Live Plotting**: Includes a web-based live plotter (using Dash and Plotly) to visualize candles, indicators, and fractals.
- **Backtesting**: Can run backtests on historical data to evaluate the strategy's performance.
- **Trade Journaling**: Records all trades in a CSV file for later analysis.

## Trading Strategy

The bot's trading strategy is based on the 3-minute timeframe and uses a combination of trend-following and momentum indicators.

- **Trend Identification**: A 50-period Simple Moving Average (SMA) on the 3-minute chart is used to determine the market trend.
  - If the price is above the 50 SMA, the trend is considered UP.
  - If the price is below the 50 SMA, the trend is considered DOWN.

- **Entry Signal**: A 20-period Williams %R (WILLR) indicator is used to identify potential entry points based on momentum.
  - **Long Signal**: In an UP trend, a bullish rejection is signaled if the WILLR crosses above the -30 level.
  - **Short Signal**: In a DOWN trend, a bearish rejection is signaled if the WILLR crosses below the -70 level.

- **Entry Trigger**: The final entry is triggered by a breakout of the most recent fractal level after a signal has been identified.
  - **Long Entry**: The bot enters a long (Call) position if the price breaks above the last up-fractal.
  - **Short Entry**: The bot enters a short (Put) position if the price breaks below the last down-fractal.

- **Trade Management**:
  - **Option Selection**: The bot selects an option with a premium closest to 120.
  - **Stop-Loss**: The initial stop-loss is set at the price of the opposite fractal. A software-based stop-loss of 10% of the entry price is also used.
  - **Take-Profit**: Take-profit levels are set at 2R, 3R, and 4R, with a complex lot distribution logic for scaling out of the position.

## Components

The bot is structured into several modules, each with a specific responsibility:

- **`live_runner.py`**: The main entry point for running the bot in live trading mode.
- **`full_backtest_runner.py`**: The main entry point for running a full backtest on a folder of historical data.
- **`test_run.py`**: A script for running a test on a single historical data file.
- **`candle_df_multiprocessor.py`**: The central processor that orchestrates the flow of data between the candle manager, signal generator, and trade manager.
- **`enhanced_candle_manager.py`**: Manages the creation of candles from tick data and resamples them into higher timeframes.
- **`signal_generator.py`**: Implements the trading strategy, calculates indicators, and generates buy/sell signals.
- **`trade_manager.py`**: Manages the execution of trades, including entering positions, handling stop-losses, and taking profits. It supports both live and paper trading.
- **`plotly_live_plotter.py`**: A Dash-based web application that provides a live plot of the NIFTY chart with indicators and fractals.

## Configuration

The bot's configuration is managed through files in the `01_bot_configuration` directory:

- **`credentials.txt`**: This file should contain your Fyers API credentials (client_id, secret_key, etc.).
- **`file_folder_configuration.txt`**: This file contains the paths for log files, historical data, and other necessary files.

## Usage

### Live Trading

To run the bot in live mode, execute the `live_runner.py` script:

```bash
python 00Fyers_websocket_bot/live_runner.py
```

Before running in live mode, ensure that:
- Your credentials are set up correctly.
- The `real_trade` flag in `live_runner.py` is set to `True` if you want to execute real trades.

### Backtesting

To backtest the strategy on a collection of historical data files, use the `full_backtest_runner.py` script. You need to provide the path to the folder containing the historical data.

```bash
python 00Fyers_websocket_bot/full_backtest_runner.py <path_to_your_data_folder>
```

A consolidated trade journal will be created in the root directory as `all_trades_journal.csv`.

## Dependencies

The bot relies on the following Python libraries:

- `fyers-apiv3`
- `pandas`
- `pandas-ta`
- `numpy`
- `dash`
- `plotly`

You can install these dependencies using pip:

```bash
pip install fyers-apiv3 pandas pandas-ta numpy dash plotly
```
