import sys
import os
from collections import deque
import numpy as np
import json
import pandas as pd
import pandas_ta as ta
import datetime as dt
from final_scripts.historical import HisData_bydate

class SignalGenerator:
    def __init__(self, candle_manager, trade_manager, timeframes, trading_timeframe, hdf_file_path, mode='test', fyers_model=None, plotter=None):
        self.candle_manager = candle_manager
        self.trade_manager = trade_manager
        self.timeframes = timeframes
        self.trading_timeframe = 3  # Strategy is fixed to 3-minute timeframe
        self.mode = mode
        self.fyers_model = fyers_model
        self.plotter = plotter

        # Indicator settings
        self.fractal_length = 5
        self.willr_length = 20 
        self.supertrend_length = 10
        self.supertrend_multiplier = 3.0
        self.sma_length = 50
        self.down_rejection_level = -70
        self.up_rejection_level = -30

        self.hdf_file_path = hdf_file_path

        self.dataframes = {tf: pd.DataFrame() for tf in self.timeframes}
        self.fractals = {tf: {'up': deque(maxlen=20), 'down': deque(maxlen=20)} for tf in self.timeframes}
        
        self.live_1min_candles = []
        self.historical_data_fetched = False
        self.awaiting_breakout = None
        self.breakout_level = None
        self.stop_loss_level = None

    def load_pre_fetched_data(self, df_1m):
        """Loads pre-fetched historical data and prepares the strategy."""
        if df_1m is None or df_1m.empty:
            print("Pre-fetched data is empty, will fetch on-the-fly.")
            return

        print("--- Loading pre-fetched historical data... ---")
        self.dataframes[1] = df_1m

        print("--- Building initial 3-min dataframe and indicators from pre-fetched data... ---")
        tf = self.trading_timeframe
        self.dataframes[tf] = (df_1m.resample(f'{tf}min', origin='09:15')
                                   .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
                                   .dropna())
        
        self._calculate_historical_indicators()
        self._calculate_historical_fractals()
        
        self.historical_data_fetched = True
        print(f"--- Pre-fetched data loaded. Strategy is active and ready for market open. ---")

        self._update_plotter()

    def add_1min_candle(self, candle):
        """
        Appends a new 1-minute candle and triggers the creation of a new trading timeframe candle
        if the timing is right. It no longer fetches historical data.
        """
        if not self.historical_data_fetched:
            # This block can be used for a live scenario where data isn't pre-fetched.
            # For the test runner, this should ideally not be hit.
            print("Warning: `add_1min_candle` called before historical data was loaded.")
            self.live_1min_candles.append(candle)
            if len(self.live_1min_candles) >= 2:
                # Fallback to old method if not pre-loaded
                self.fetch_and_prepare_data_live(candle['timestamp'])
            return

        # Append the new 1-min candle to the existing dataframe
        self._append_candle_to_df(1, candle)
        df_1m = self.dataframes[1]
        last_timestamp = df_1m.index[-1]
        
        # Check if it's time to create a new 3-minute candle
        if (last_timestamp.minute + 1) % self.trading_timeframe == 0:
            origin = '09:15'
            # Resample the last few minutes to get the latest full 3-min candle
            resampled = (df_1m.resample(f'{self.trading_timeframe}min', origin=origin)
                              .agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'})
                              .dropna())
            
            if not resampled.empty:
                latest_3m_candle_row = resampled.iloc[-1]
                latest_3m_candle = latest_3m_candle_row.to_dict()
                latest_3m_candle['timestamp'] = latest_3m_candle_row.name
                
                # This append will trigger indicator calculation and signal checks
                self._append_candle_to_df(self.trading_timeframe, latest_3m_candle)

    def add_higher_tf_candle(self, timeframe, candle):
        if self.historical_data_fetched and timeframe == self.trading_timeframe:
            self._append_candle_to_df(timeframe, candle)

    def _append_candle_to_df(self, timeframe, candle):
        if timeframe != 1 and timeframe != self.trading_timeframe:
            return

        new_row = pd.DataFrame([candle])
        new_row.set_index(pd.to_datetime(new_row['timestamp']), inplace=True)
        if 'symbol' in new_row.columns: new_row.drop(columns=['symbol', 'timestamp'], inplace=True, errors='ignore')
        
        df = self.dataframes[timeframe]
        if not new_row.index.isin(df.index).any():
            self.dataframes[timeframe] = pd.concat([df, new_row]).sort_index()
            
            if timeframe == self.trading_timeframe:
                self._calculate_live_indicators()
                self._check_live_fractal()
                self.check_signal()
                self._update_plotter()
    
    def _update_plotter(self):
        if not self.plotter:
            return

        plot_df = self.dataframes[self.trading_timeframe].copy().tail(120)
        plot_df['up_fractal'] = np.nan
        plot_df['down_fractal'] = np.nan

        up_fractals = {ts: val for ts, val in self.fractals[self.trading_timeframe]['up']}
        down_fractals = {ts: val for ts, val in self.fractals[self.trading_timeframe]['down']}

        plot_df['up_fractal'] = plot_df.index.map(up_fractals)
        plot_df['down_fractal'] = plot_df.index.map(down_fractals)

        option_chain = self._get_option_chain()
        self.plotter.update_data(plot_df, self.trading_timeframe, option_chain)

    def _get_option_chain(self):
        option_chain = []
        if 1 in self.candle_manager.tick_candles:
            for symbol, candle_data in self.candle_manager.tick_candles[1].items():
                if 'CE' in symbol or 'PE' in symbol:
                    option_chain.append({'Symbol': symbol, 'Price': candle_data.get('close', 0)})
        return pd.DataFrame(option_chain)

    def check_signal(self):
        if self.awaiting_breakout is not None or self.trade_manager.in_trade: return

        tf = self.trading_timeframe
        df = self.dataframes[tf]
        
        if len(df) < self.sma_length: return

        willr_col = f'WILLR_{self.willr_length}'
        sma_col = f'SMA_{self.sma_length}'

        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        trend = None
        if last_row['close'] > last_row[sma_col]:
            trend = 'UP'
        elif last_row['close'] < last_row[sma_col]:
            trend = 'DOWN'

        if trend is None: return
        
        if trend == 'UP' and prev_row[willr_col] <= self.up_rejection_level and last_row[willr_col] > self.up_rejection_level:
            self._prepare_breakout('long')

        elif trend == 'DOWN' and prev_row[willr_col] >= self.down_rejection_level and last_row[willr_col] < self.down_rejection_level:
            self._prepare_breakout('short')

    def _prepare_breakout(self, direction):
        tf = self.trading_timeframe
        df = self.dataframes[tf]
        up_fractals, down_fractals = self.fractals[tf]['up'], self.fractals[tf]['down']
        if not up_fractals or not down_fractals: return

        last_close = df.iloc[-1]['close']

        if direction == 'long':
            self.awaiting_breakout = 'long'
            self.breakout_level = up_fractals[-1][1]
            self.stop_loss_level = down_fractals[-1][1]
            
            sl_points = abs(self.stop_loss_level - self.breakout_level)
            if sl_points > 50:
                print(f"\n*** LONG SIGNAL REJECTED: SL points ({sl_points:.2f}) exceed 50. ***")
                self.awaiting_breakout = None
                return

            print(f"\n*** LONG SIGNAL PENDING on {df.index[-1]} ***")
            print(f"  - Trend is UP. Current LTP (close): {last_close}")
            print(f"  - Awaiting breakout of Trigger Price: {self.breakout_level}")
            print(f"  - Initial Stop-Loss will be: {self.stop_loss_level}")

        elif direction == 'short':
            self.awaiting_breakout = 'short'
            self.breakout_level = down_fractals[-1][1]
            self.stop_loss_level = up_fractals[-1][1]

            sl_points = abs(self.stop_loss_level - self.breakout_level)
            if sl_points > 50:
                print(f"\n*** SHORT SIGNAL REJECTED: SL points ({sl_points:.2f}) exceed 50. ***")
                self.awaiting_breakout = None
                return
            
            print(f"\n*** SHORT SIGNAL PENDING on {df.index[-1]} ***")
            print(f"  - Trend is DOWN. Current LTP (close): {last_close}")
            print(f"  - Awaiting breakout of Trigger Price: {self.breakout_level}")
            print(f"  - Initial Stop-Loss will be: {self.stop_loss_level}")

    def run_live_strategy(self, tick):
        if self.awaiting_breakout is None or self.trade_manager.in_trade or tick.get("symbol") != 'NSE:NIFTY50-INDEX':
            return
        
        ltp = tick.get('ltp')
        if not ltp: return

        # WILLR based cancellation
        tf = self.trading_timeframe
        df = self.dataframes[tf]
        if not df.empty:
            willr_col = f'WILLR_{self.willr_length}'
            if willr_col in df.columns:
                latest_willr = df.iloc[-1][willr_col]
                if self.awaiting_breakout == 'long' and latest_willr < -50:
                    print(f"*** LONG TRADE CANCELLED on {dt.datetime.fromtimestamp(tick['exch_feed_time'])}. WILLR crossed below -50. ***")
                    self.awaiting_breakout = None
                    return
                elif self.awaiting_breakout == 'short' and latest_willr > -50:
                    print(f"*** SHORT TRADE CANCELLED on {dt.datetime.fromtimestamp(tick['exch_feed_time'])}. WILLR crossed above -50. ***")
                    self.awaiting_breakout = None
                    return

        # Price based cancellation
        if self.awaiting_breakout == 'long' and ltp < self.stop_loss_level:
            print(f"*** LONG TRADE CANCELLED on {dt.datetime.fromtimestamp(tick['exch_feed_time'])}. Price broke below SL level before entry. ***")
            self.awaiting_breakout = None
            return
        elif self.awaiting_breakout == 'short' and ltp > self.stop_loss_level:
            print(f"*** SHORT TRADE CANCELLED on {dt.datetime.fromtimestamp(tick['exch_feed_time'])}. Price broke above SL level before entry. ***")
            self.awaiting_breakout = None
            return

        # Breakout Execution
        if self.awaiting_breakout == 'long' and ltp > self.breakout_level:
            print(f"*** LONG BREAKOUT! *** at {dt.datetime.fromtimestamp(tick['exch_feed_time'])}")
            self.trade_manager.long_trade_triggered(tick['exch_feed_time'], self.stop_loss_level, self.breakout_level, ltp)
            self.awaiting_breakout = None
        elif self.awaiting_breakout == 'short' and ltp < self.breakout_level:
            print(f"*** SHORT BREAKOUT! *** at {dt.datetime.fromtimestamp(tick['exch_feed_time'])}")
            self.trade_manager.short_trade_triggered(tick['exch_feed_time'], self.stop_loss_level, self.breakout_level, ltp)
            self.awaiting_breakout = None

    def fetch_and_prepare_data_live(self, end_datetime):
        """Fallback for live mode where data isn't pre-fetched."""
        print(f"--- Point-in-time fetch triggered at {end_datetime}. ---")
        df_1m = self.fetch_historical_data('NSE:NIFTY50-INDEX', end_datetime - dt.timedelta(days=30), end_datetime)
        if df_1m is None or df_1m.empty: return

        live_df = pd.DataFrame(self.live_1min_candles)
        if not live_df.empty:
            live_df.set_index(pd.to_datetime(live_df['timestamp']), inplace=True)
            if 'symbol' in live_df.columns: live_df.drop(columns=['timestamp', 'symbol'], inplace=True)
            df_1m = pd.concat([df_1m, live_df])
            df_1m = df_1m[~df_1m.index.duplicated(keep='last')].sort_index()
        
        self.load_pre_fetched_data(df_1m)


    def _calculate_historical_indicators(self):
        df = self.dataframes[self.trading_timeframe]
        if df.empty: return
        
        df[f'WILLR_{self.willr_length}'] = ta.willr(df['high'], df['low'], df['close'], length=self.willr_length)
        df[f'SMA_{self.sma_length}'] = ta.sma(df['close'], length=self.sma_length)
        
        st = ta.supertrend(df['high'], df['low'], df['close'], length=self.supertrend_length, multiplier=self.supertrend_multiplier)
        if st is not None and not st.empty:
            df[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}'] = st[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}']

    def _calculate_live_indicators(self):
        df = self.dataframes[self.trading_timeframe]
        if df.empty: return
            
        willr_series = ta.willr(df['high'], df['low'], df['close'], length=self.willr_length)
        if willr_series is not None: df[f'WILLR_{self.willr_length}'] = willr_series

        sma_series = ta.sma(df['close'], length=self.sma_length)
        if sma_series is not None: df[f'SMA_{self.sma_length}'] = sma_series

        st = ta.supertrend(df['high'], df['low'], df['close'], length=self.supertrend_length, multiplier=self.supertrend_multiplier)
        if st is not None: df[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}'] = st[f'SUPERT_{self.supertrend_length}_{self.supertrend_multiplier}']

    def _check_live_fractal(self):
        df = self.dataframes[self.trading_timeframe]
        n = self.fractal_length
        if len(df) < n: return
        
        window = df.iloc[-n:]
        candle_to_check = window.iloc[n//2]
        ts = window.index[n//2]

        if any(ts == item[0] for item in self.fractals[self.trading_timeframe]['up']) or \
           any(ts == item[0] for item in self.fractals[self.trading_timeframe]['down']):
            return

        if candle_to_check['high'] == window['high'].max():
            self.fractals[self.trading_timeframe]['up'].append((ts, candle_to_check['high']))
        if candle_to_check['low'] == window['low'].min():
            self.fractals[self.trading_timeframe]['down'].append((ts, candle_to_check['low']))

    def _calculate_historical_fractals(self):
        tf = self.trading_timeframe
        df = self.dataframes[tf]
        if df.empty: return
        
        self.fractals[tf]['up'].clear()
        self.fractals[tf]['down'].clear()
        n = self.fractal_length
        m = n // 2
        for i in range(m, len(df) - m):
            window = df.iloc[i-m : i+m+1]
            candle = window.iloc[m]
            
            if candle['high'] == window['high'].max():
                self.fractals[tf]['up'].append((window.index[m], candle['high']))
            if candle['low'] == window['low'].min():
                self.fractals[tf]['down'].append((window.index[m], candle['low']))
    
    def fetch_historical_data(self, symbol, start_date, end_date):
        if self.mode == 'live':
            print(f"--- Fetching live historical data for {symbol} from Fyers API ---")
            try:
                df = HisData_bydate(symbol, '1', start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), self.fyers_model)
                if df is not None and not df.empty:
                    df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'tradingVolume': 'volume'}, inplace=True, errors='ignore')
                    return df
                else:
                    print("Failed to fetch live historical data from Fyers API.")
                    return None
            except Exception as e:
                print(f"Error fetching live historical data: {e}")
                return None
        else: # test mode
            print(f"--- Fetching test historical data for {symbol} from HDF file ---")
            try:
                key = f"/{symbol}/historical_data"
                df = pd.read_hdf(self.hdf_file_path, key=key)
                df = df.loc[start_date:end_date].copy()
                df.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'tradingVolume': 'volume'}, inplace=True, errors='ignore')
                df.index = pd.to_datetime(df.index)
                return df
            except Exception as e:
                print(f"Test hist error: {e}")
                return None
