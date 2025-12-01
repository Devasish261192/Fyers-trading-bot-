import datetime as dt
import pandas as pd

class CandleManager:
    def __init__(self, timeframes):
        self.timeframes = set(timeframes)
        if 1 not in self.timeframes:
            self.timeframes.add(1)

        self.tick_candles = {tf: {} for tf in self.timeframes}

        higher_tfs = {tf for tf in self.timeframes if tf > 1}
        self.resampled_dfs = {tf: {} for tf in higher_tfs}
        self.live_resampled_candles = {tf: {} for tf in higher_tfs}

    def get_candle_time(self, timestamp, minutes):
        market_open = dt.time(9, 15)
        dt_date = timestamp.date()
        market_open_dt = dt.datetime.combine(dt_date, market_open)

        if timestamp < market_open_dt:
            # For pre-market data, align to the market open
            return market_open_dt

        # Calculate minutes past market open
        minutes_since_open = (timestamp - market_open_dt).total_seconds() / 60
        
        # Determine how many `minutes`-long intervals have passed
        intervals_passed = int(minutes_since_open // minutes)
        
        # Calculate the start minute of the current interval
        current_interval_start_minute = intervals_passed * minutes
        
        # Return the precise candle timestamp
        return market_open_dt + pd.to_timedelta(current_interval_start_minute, unit='m')

    def initialize_tick_candle(self, symbol, ltp, volume, candle_time):
        self.tick_candles[1][symbol] = {
            "current_candle_time": candle_time,
            "open": ltp, "high": ltp, "low": ltp, "close": ltp,
            "starting_volume": volume, "current_volume": volume,
        }

    def update_tick_candle(self, symbol, ltp, volume):
        data = self.tick_candles[1][symbol]
        if ltp > data["high"]: data["high"] = ltp
        elif ltp < data["low"]: data["low"] = ltp
        data["close"] = ltp
        data["current_volume"] = volume

    def get_completed_tick_candle(self, symbol):
        data = self.tick_candles[1][symbol]
        return {
            'symbol': symbol, 'timestamp': data["current_candle_time"],
            'open': data["open"], 'high': data["high"], 'low': data["low"], 'close': data["close"],
            'volume': data["current_volume"] - data["starting_volume"],
        }

    def process_1min_candle(self, c_1m):
        completed_candles = {}
        symbol = c_1m['symbol']

        for tf in self.live_resampled_candles.keys():
            candle_time = self.get_candle_time(c_1m['timestamp'], tf)

            if symbol not in self.live_resampled_candles[tf]:
                self._initialize_resampled_candle(symbol, tf, candle_time, c_1m)
                continue

            live_candle = self.live_resampled_candles[tf][symbol]

            if candle_time > live_candle['timestamp']:
                completed_candles[tf] = live_candle.copy()
                
                if symbol not in self.resampled_dfs[tf]:
                    self.resampled_dfs[tf][symbol] = pd.DataFrame([live_candle])
                else:
                    new_row = pd.DataFrame([live_candle])
                    self.resampled_dfs[tf][symbol] = pd.concat(
                        [self.resampled_dfs[tf][symbol], new_row], ignore_index=True
                    )
                
                self._initialize_resampled_candle(symbol, tf, candle_time, c_1m)
            else:
                live_candle['high'] = max(live_candle['high'], c_1m['high'])
                live_candle['low'] = min(live_candle['low'], c_1m['low'])
                live_candle['close'] = c_1m['close']
                live_candle['volume'] += c_1m['volume']
        
        return completed_candles

    def _initialize_resampled_candle(self, symbol, tf, candle_time, c_1m):
        self.live_resampled_candles[tf][symbol] = {
            'symbol': symbol, 'timestamp': candle_time,
            'open': c_1m['open'], 'high': c_1m['high'], 'low': c_1m['low'],
            'close': c_1m['close'], 'volume': c_1m['volume']
        }

    def update_partial_candle_from_tick(self, tick):
        symbol = tick.get("symbol")
        ltp = tick.get("ltp")
        if not symbol or not ltp:
            return

        if symbol in self.tick_candles[1]:
            live_1m_candle = self.tick_candles[1][symbol]
            if ltp > live_1m_candle["high"]: live_1m_candle["high"] = ltp
            elif ltp < live_1m_candle["low"]: live_1m_candle["low"] = ltp
            live_1m_candle["close"] = ltp

        for tf in self.live_resampled_candles.keys():
            if symbol in self.live_resampled_candles[tf]:
                live_candle = self.live_resampled_candles[tf][symbol]
                
                live_candle['high'] = max(live_candle['high'], ltp)
                live_candle['low'] = min(live_candle['low'], ltp)
                live_candle['close'] = ltp

    def get_partial_candle(self, symbol, timeframe):
        if timeframe == 1:
            if symbol in self.tick_candles[1]:
                c = self.tick_candles[1][symbol]
                return {
                    'symbol': symbol, 'timestamp': c["current_candle_time"],
                    'open': c["open"], 'high': c["high"], 'low': c["low"], 'close': c["close"],
                    'volume': c["current_volume"] - c["starting_volume"]
                }
        elif timeframe in self.live_resampled_candles:
            if symbol in self.live_resampled_candles[timeframe]:
                return self.live_resampled_candles[timeframe][symbol].copy()
        return None