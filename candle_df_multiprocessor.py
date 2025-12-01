import datetime as dt
from enhanced_candle_manager import CandleManager
from trade_manager import TradeManager
from signal_generator import SignalGenerator

class MultiTimeframeProcessor:
    def __init__(self, timeframes, trading_timeframe, hdf_file_path, mode='test', fyers_model=None, plotter=None, real_trade=False):
        self.timeframes = set(timeframes)
        self.trading_timeframe = trading_timeframe
        
        self.candle_manager = CandleManager(self.timeframes)
        self.trade_manager = TradeManager(self, mode=mode, fyers_model=fyers_model, real_trade=real_trade)
        self.signal_generator = SignalGenerator(
            candle_manager=self.candle_manager,
            trade_manager=self.trade_manager,
            timeframes=self.timeframes,
            trading_timeframe=self.trading_timeframe,
            mode=mode,
            fyers_model=fyers_model,
            plotter=plotter,
            hdf_file_path=hdf_file_path
        )

    def process_tick(self, message):
        symbol = message.get("symbol")
        if not symbol:
            return

        # Pass all ticks to the trade manager for exit condition checks
        if self.trade_manager.in_trade:
            self.trade_manager.check_for_exit(message)

        if symbol == 'NSE:NIFTY50-INDEX':
            self.signal_generator.run_live_strategy(message)

        self.candle_manager.update_partial_candle_from_tick(message)

        ltp = message.get("ltp")
        volume = message.get("vol_traded_today", 0)
        timestamp = dt.datetime.fromtimestamp(message.get('exch_feed_time'))
        
        candle_time = self.candle_manager.get_candle_time(timestamp, 1)

        if symbol not in self.candle_manager.tick_candles[1]:
            self.candle_manager.initialize_tick_candle(symbol, ltp, volume, candle_time)
            return

        data = self.candle_manager.tick_candles[1][symbol]

        if candle_time > data["current_candle_time"]:
            c_1m = self.candle_manager.get_completed_tick_candle(symbol)
            completed_higher_tf_candles = self.candle_manager.process_1min_candle(c_1m)

            if symbol == 'NSE:NIFTY50-INDEX':
                self.signal_generator.add_1min_candle(c_1m)

            if completed_higher_tf_candles:
                for tf, candle in completed_higher_tf_candles.items():
                    if candle['symbol'] == 'NSE:NIFTY50-INDEX':
                        self.signal_generator.add_higher_tf_candle(tf, candle)

            self.candle_manager.initialize_tick_candle(symbol, ltp, volume, candle_time)
        else:
            self.candle_manager.update_tick_candle(symbol, ltp, volume)

    def process_order_update(self, message):
        self.trade_manager.process_order_update(message)