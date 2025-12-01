import pandas as pd
import datetime as dt
import os
import time

class TradeManager:
    def __init__(self, processor, mode='test', fyers_model=None, real_trade=False, log_dir=None):
        self.processor = processor
        self.mode = mode
        self.fyers_model = fyers_model
        self.real_trade = real_trade
        self.log_dir = log_dir
        
        # State Management
        self.state = 'IDLE'  # IDLE, AWAITING_ENTRY, TRADE_ACTIVE
        self.in_trade = False
        self.current_trade = {}
        self.pending_entry_order_id = None
        self.active_sl_order_id = None
        
        self.completed_trades = []
        self.lot_size = 75
        self.brokerage_per_lot = 50

        # Capital and Lot Sizing
        self.capital = 30000  # Default starting capital
        self.lots = 1
        self.daily_pnl = 0.0
        self.daily_loss_limit = 0.0
        self.trading_halted = False

    def set_capital(self, capital):
        """Sets the current capital and the daily loss limit."""
        self.capital = capital
        
        # Reset daily risk management
        self.daily_pnl = 0.0
        self.daily_loss_limit = -0.05 * self.capital
        self.trading_halted = False
            
        print(f"Capital updated to: {self.capital:.2f}. Daily Loss Limit: {self.daily_loss_limit:.2f}")

    def long_trade_triggered(self, trig_time, sl_price, breakout_level, ltp):
        if self.state != 'IDLE': return
        if dt.datetime.fromtimestamp(trig_time).time() >= dt.time(15, 15):
            return
        print(f"--- LONG SIGNAL at {dt.datetime.fromtimestamp(trig_time)} ---")
        self._enter_trade("CE", trig_time, ltp)

    def short_trade_triggered(self, trig_time, sl_price, breakout_level, ltp):
        if self.state != 'IDLE': return
        if dt.datetime.fromtimestamp(trig_time).time() >= dt.time(15, 15):
            return
        print(f"--- SHORT SIGNAL at {dt.datetime.fromtimestamp(trig_time)} ---")
        self._enter_trade("PE", trig_time, ltp)

    def _enter_trade(self, option_type, signal_time, index_ltp):
        if self.trading_halted:
            print(f"--- DAILY LOSS LIMIT REACHED. NO NEW TRADES ALLOWED. ---")
            return

        # --- Lot Sizing Logic ---
        trade_date = dt.datetime.fromtimestamp(signal_time)
        day_of_week = trade_date.weekday()  # Monday is 0, Wednesday is 2

        if day_of_week == 0:  # Monday
            self.trading_halted = True
            print(f"  - Day is {trade_date.strftime('%A')}. Skipping trades for the day.")
            return
        elif day_of_week == 2:  # Wednesday
            trade_lots = 1
            print(f"  - Day is {trade_date.strftime('%A')}. Trading with 1 lot only.")
        else:  # Other days (Tuesday, Thursday, Friday)
            # Use capital-based lot sizing
            if self.capital < 50000:
                trade_lots = 1
            elif 50000 <= self.capital < 80000:
                trade_lots = 2
            else:  # capital >= 100000
                trade_lots = int((self.capital - 80000) / 30000) + 2
            print(f"  - Day is {trade_date.strftime('%A')}. Using capital-based lots: {trade_lots}")

        all_options = self._find_options(option_type)
        if not all_options:
            print(f"  - No {option_type} options found at all.")
            return

        best_option = min(all_options, key=lambda x: abs(x['price'] - 120))
        entry_price = best_option['price']
        limit_price = entry_price + 1

        # Define current_trade details before placing order
        initial_sl_price = entry_price * 0.90
        risk_per_share = entry_price - initial_sl_price
        
        # --- Generate Take-Profit Levels based on the new complex distribution logic ---
        tp_levels = []
        tp_price_2r = entry_price + (risk_per_share * 2)
        tp_price_3r = entry_price + (risk_per_share * 3)
        tp_price_4r = entry_price + (risk_per_share * 4)

        if trade_lots == 1:
            tp_levels.append(tp_price_4r)
        elif trade_lots == 2:
            tp_levels.append(tp_price_3r)
            tp_levels.append(tp_price_4r)
        elif trade_lots >= 3:
            base_lots = trade_lots // 3
            remainder = trade_lots % 3

            lots_at_2r = base_lots
            lots_at_3r = base_lots
            lots_at_4r = base_lots

            if remainder == 1:
                lots_at_3r += 1
            elif remainder == 2:
                lots_at_3r += 1
                lots_at_4r += 1
            
            tp_levels.extend([tp_price_2r] * lots_at_2r)
            tp_levels.extend([tp_price_3r] * lots_at_3r)
            tp_levels.extend([tp_price_4r] * lots_at_4r)

        self.current_trade = {
            'symbol': best_option['symbol'],
            'entry_price': entry_price,
            'entry_time': dt.datetime.fromtimestamp(signal_time),
            'type': 'long' if option_type == "CE" else 'short',
            'status': 'active',
            'initial_lots': trade_lots,
            'lots_outstanding': trade_lots,
            'initial_sl_price': initial_sl_price,
            'current_sl_price': initial_sl_price,
            'take_profit_levels': sorted(tp_levels),
            'partial_exits': []
        }

        if self.mode == 'live' and self.real_trade:
            order_data = {
                "symbol": self.current_trade['symbol'],
                "qty": self.lot_size * trade_lots,
                "type": 2,  # Limit Order
                "side": 1,  # 1 for Buy
                "productType": "MARGIN",
                "limitPrice": 0,
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0, "offlineOrder": False
            }
            print(f"--- Placing Entry Limit Order ---\n{order_data}\n--------------------------")
            order_response = self.fyers_model.place_order(data=order_data)
            print("Full entry order response:", order_response)
            if order_response.get('s') != 'ok':
                print(f"  - ENTRY ORDER PLACEMENT FAILED! Reason: {order_response.get('message', 'Unknown')}")
                self._reset_trade_state()
                return
            self.pending_entry_order_id = order_response['id']
            self.state = 'AWAITING_ENTRY'
            print(f"  - WAITING FOR EXECUTION of {self.current_trade['symbol']} at {limit_price:.2f}")
        else: # Paper trading simulation
            print("--- [PAPER MODE] Simulating Immediate Order Execution ---")
            self.pending_entry_order_id = f"paper_trade_entry_{int(time.time())}"
            self.state = 'AWAITING_ENTRY' # Set state before processing
            simulated_confirmation = {
                'id': self.pending_entry_order_id,
                'status': 2, # 2 = Filled
                'symbol': self.current_trade['symbol'],
                'tradedPrice': self.current_trade['entry_price']
            }
            self.process_order_update(simulated_confirmation)

    def process_order_update(self, message):
        if self.state == 'AWAITING_ENTRY' and message.get('id') == self.pending_entry_order_id:
            if message.get('status') == 2:  # Order is Traded/Filled
                print(f"--- ENTRY ORDER EXECUTED for {message['symbol']} ---")
                print(f"  - Entry Price: {message['tradedPrice']:.2f} | Qty: {self.current_trade['initial_lots']} lots")
                actual_entry_price = message['tradedPrice']
                self.current_trade['actual_entry_price'] = actual_entry_price

                # --- NEW: Re-calculate SL based on the actual traded price ---
                new_sl_price = actual_entry_price * 0.90
                self.current_trade['initial_sl_price'] = new_sl_price
                self.current_trade['current_sl_price'] = new_sl_price
                print(f"  - SL price re-calculated based on actual entry. New SL: {new_sl_price:.2f}")
                # --- END NEW ---

                # Immediately place the corresponding Stop-Loss Order
                sl_stop_price = new_sl_price  # Use the newly calculated SL
                sl_limit_price = sl_stop_price * 0.99

                sl_order_data = {
                    "symbol": self.current_trade['symbol'],
                    "qty": self.lot_size * self.current_trade['initial_lots'],
                    "type": 4, "side": -1, "productType": "MARGIN",
                    "limitPrice": round(sl_limit_price, 1),
                    "stopPrice": round(sl_stop_price, 1),
                    "validity": "DAY",
                }
                print(f"--- Placing Initial Stop-Loss Order ---")
                print(f"  - Stop-Loss Price: {round(sl_stop_price, 1):.2f}")
                print(f"  - Take-Profit Levels: {[round(p, 2) for p in self.current_trade['take_profit_levels']]}")
                
                if self.mode == 'live' and self.real_trade:
                    sl_response = self.fyers_model.place_order(data=sl_order_data)
                    print("Full SL order response:", sl_response)
                    if sl_response.get('s') == 'ok':
                        # SL order placed successfully, now we can consider the trade active
                        self.active_sl_order_id = sl_response['id']
                        self.in_trade = True
                        self.state = 'TRADE_ACTIVE'
                        print(f"--- Stop-Loss order placed successfully. Trade is now ACTIVE. SL Order ID: {self.active_sl_order_id} ---")
                    else:
                        # CRITICAL: SL order failed. Exit the position immediately.
                        print(f"  - STOP-LOSS ORDER PLACEMENT FAILED! EXITING POSITION. Reason: {sl_response.get('message', 'Unknown')}")
                        self._exit_trade("SL order failed", int(time.time()), self.current_trade['actual_entry_price'])
                else: # Paper trading simulation
                    self.active_sl_order_id = f"simulated_sl_{int(time.time())}"
                    self.in_trade = True
                    self.state = 'TRADE_ACTIVE'
                    print(f"--- [PAPER MODE] Stop-Loss order placed successfully. Trade is now ACTIVE. ---")

            elif message.get('status') in [1, 5, 8]: # Canceled, Rejected, etc.
                print(f"--- ENTRY ORDER FAILED (Status: {message.get('status')}). Reason: {message.get('message')} ---")
                self._reset_trade_state()

        elif self.state == 'TRADE_ACTIVE' and message.get('id') == self.active_sl_order_id:
            if message.get('status') == 2: # SL Order is Traded/Filled
                print(f"--- BROKER CONFIRMATION: STOP-LOSS EXECUTED for {message['symbol']} ---")
                
                exit_price = message.get('tradedPrice', self.current_trade['current_sl_price'])
                
                # Convert Fyers timestamp string to epoch
                try:
                    exit_dt = dt.datetime.strptime(message['orderDateTime'], '%d-%b-%Y %H:%M:%S')
                    exit_epoch = exit_dt.timestamp()
                except (ValueError, KeyError):
                    exit_epoch = int(time.time()) # Fallback to current time

                # Call the existing exit logic with the correct reason
                self._exit_trade("Stop-loss hit", exit_epoch, exit_price)

            elif message.get('status') == 1: # SL order was CANCELED
                print(f"--- BROKER CONFIRMATION: Stop-loss order ({self.active_sl_order_id}) is CANCELED. ---")
                self.active_sl_order_id = None

    def check_for_exit(self, tick):
        if not self.in_trade or self.state != 'TRADE_ACTIVE': return
        if tick.get('symbol') != self.current_trade['symbol']: return

        ltp = tick.get('ltp')
        if not ltp: return

        # Check for software-based SL hit
        sl_price = self.current_trade['current_sl_price']
        if ltp <= sl_price:
            self._exit_trade("Stop-loss hit", tick['exch_feed_time'], ltp)
            return

        # Check for TP hits
        if self.current_trade['take_profit_levels']:
            if ltp >= self.current_trade['take_profit_levels'][0]:
                # If it's the last lot, do a full exit
                if self.current_trade['lots_outstanding'] == 1:
                    self._exit_trade("Final TP hit", tick['exch_feed_time'], ltp)
                # Otherwise, do a partial exit
                else:
                    self._exit_partial("Partial TP hit", tick['exch_feed_time'], ltp)
                return

        # Check for EOD exit
        if dt.datetime.fromtimestamp(tick['exch_feed_time']).time() >= dt.time(15, 15):
            self._exit_trade("End of day exit", tick['exch_feed_time'], ltp)
            return

    def _exit_partial(self, reason, exit_time_epoch, exit_price):
        """Handles the logic for a partial exit (selling 1 lot)."""
        print(f"\n--- PARTIAL EXIT ({reason}) at {dt.datetime.fromtimestamp(exit_time_epoch)} ---")
        
        # 1. Calculate P&L for this partial exit
        pnl_per_share = exit_price - self.current_trade['actual_entry_price']
        brokerage_for_this_leg = (self.brokerage_per_lot / self.current_trade['initial_lots'])
        partial_pnl = (pnl_per_share * self.lot_size * 1) - brokerage_for_this_leg
        
        self.current_trade['partial_exits'].append({
            'exit_price': exit_price,
            'pnl': partial_pnl
        })
        print(f"  - Exited 1 lot of {self.current_trade['symbol']} at {exit_price:.2f} for P&L: {partial_pnl:.2f}")

        # 2. Update daily P&L and check limit
        self.daily_pnl += partial_pnl
        print(f"  - Cumulative Daily P&L: {self.daily_pnl:.2f}")
        self._check_daily_loss_limit()

        # 3. Update trade state
        self.current_trade['lots_outstanding'] -= 1
        self.current_trade['take_profit_levels'].pop(0)

        # 4. Update software SL
        new_sl_price = exit_price * 0.90
        self.current_trade['current_sl_price'] = new_sl_price
        print(f"  - Lots outstanding: {self.current_trade['lots_outstanding']}")
        print(f"  - Trailing SL updated to: {new_sl_price:.2f}")
        print(f"  - Remaining TP levels: {[round(p, 2) for p in self.current_trade['take_profit_levels']]}")
        print("  - NOTE: In live mode, would cancel old SL and create new SL order here.")
        print("-" * 20)


    def _exit_trade(self, reason, exit_time_epoch, exit_price):
        if not self.in_trade: return

        lots_to_exit = self.current_trade['lots_outstanding']
        print(f"\n--- FINAL EXIT ({reason}) at {dt.datetime.fromtimestamp(exit_time_epoch)} ---")

        # For TP, EOD, or other manual exits, we need to cancel the pending SL order and place a market order.
        # For a "Stop-loss hit", we assume the broker has already executed the SL order.
        if reason != "Stop-loss hit":
            if self.active_sl_order_id:
                print(f"--- Cancelling Stop-Loss Order: {self.active_sl_order_id} ---")
                if self.mode == 'live' and self.real_trade:
                    cancel_response = self.fyers_model.cancel_order(data={"id":self.active_sl_order_id})
                    print("Full cancel order response:", cancel_response)

            exit_order_data = {
                "symbol": self.current_trade['symbol'],
                "qty": self.lot_size * lots_to_exit,
                "type": 2, "side": -1, "productType": "MARGIN", "validity": "DAY"
            }
            print(f"--- Placing Final Exit Market Order ---")
            print(f"  - Exit Price (Market): {exit_price:.2f} | Qty: {lots_to_exit} lots")
            if self.mode == 'live' and self.real_trade:
                exit_response = self.fyers_model.place_order(data=exit_order_data)
                print("Full exit order response:", exit_response)
        else:
            # If SL is hit, we just log it. The actual order execution confirmation will come via websocket.
            print(f"  - Stop-Loss triggered at price: {exit_price:.2f}. Assuming broker execution.")

        # Calculate P&L for the final leg
        pnl_per_share = exit_price - self.current_trade['actual_entry_price']
        brokerage_for_final_leg = (self.brokerage_per_lot / self.current_trade['initial_lots']) * lots_to_exit
        final_leg_pnl = (pnl_per_share * self.lot_size * lots_to_exit) - brokerage_for_final_leg

        # Update daily P&L with the final leg's result
        self.daily_pnl += final_leg_pnl
        print(f"  - P&L for final {lots_to_exit} lot(s): {final_leg_pnl:.2f}")
        print(f"  - Cumulative Daily P&L: {self.daily_pnl:.2f}")

        # Sum up total P&L for the entire trade
        total_pnl = sum(p['pnl'] for p in self.current_trade['partial_exits']) + final_leg_pnl
        
        trade_summary = self.current_trade.copy()
        trade_summary.update({
            'exit_price': exit_price,
            'exit_time': dt.datetime.fromtimestamp(exit_time_epoch),
            'pnl': total_pnl,
            'status': 'exited',
            'exit_reason': reason
        })
        
        self.completed_trades.append(trade_summary)
        print(f"  - Total P&L for the trade: {total_pnl:.2f}")
        
        self._check_daily_loss_limit()
        self._save_live_tradebook()
        self._reset_trade_state()

    def _check_daily_loss_limit(self):
        if not self.trading_halted and self.daily_pnl <= self.daily_loss_limit:
            self.trading_halted = True
            print("\n" + "="*50)
            print("!!! DAILY LOSS LIMIT REACHED !!!")
            print(f"  - Daily P&L: {self.daily_pnl:.2f}")
            print(f"  - Limit:     {self.daily_loss_limit:.2f}")
            print("  - Halting all new trading for the rest of the day.")
            print("="*50 + "\n")

    def _save_live_tradebook(self):
        if not self.log_dir or not self.completed_trades:
            return

        tradebook_path = os.path.join(self.log_dir, 'tradebook.txt')
        trade = self.completed_trades[-1]

        trade_str = (
            f"--- Trade #{len(self.completed_trades)} ---\n"
            f"  Symbol:         {trade['symbol']}\n"
            f"  Trade Type:     {trade['type']}\n"
            f"  Entry Time:     {trade['entry_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  Entry Price:    {trade.get('actual_entry_price', trade['entry_price']):.2f}\n"
            f"  Exit Time:      {trade['exit_time'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"  Exit Price:     {trade['exit_price']:.2f}\n"
            f"  Exit Reason:    {trade['exit_reason']}\n"
            f"  Lots:           {trade['initial_lots']}\n"
            f"  P&L:            {trade['pnl']:.2f}\n"
            f"--------------------------------\n\n"
        )

        try:
            with open(tradebook_path, 'a') as f:
                f.write(trade_str)
            print(f"--- Trade record saved to {tradebook_path} ---")
        except Exception as e:
            print(f"Error saving trade record: {e}")

    def _reset_trade_state(self):
        self.in_trade = False
        self.state = 'IDLE'
        self.current_trade = {}
        self.pending_entry_order_id = None
        self.active_sl_order_id = None

    def _find_options(self, option_type):
        all_options = []
        candle_manager = self.processor.candle_manager
        if 1 in candle_manager.tick_candles:
            for symbol, candle_data in candle_manager.tick_candles[1].items():
                if option_type in symbol and candle_data.get('close', 0) > 0:
                    all_options.append({'symbol': symbol, 'price': candle_data['close']})
        return all_options

    def print_statistics(self):
        if not self.completed_trades:
            print("No trades were executed.")
            return
        total_pnl = sum(trade['pnl'] for trade in self.completed_trades)
        print("\n" + "="*80)
        print("TRADE STATISTICS")
        print("="*80)
        for i, trade in enumerate(self.completed_trades):
            print(f"\n--- Trade #{i+1} ---")
            print(f"  Symbol: {trade['symbol']}")
            print(f"  Type: {trade['type']}")
            print(f"  Entry: {trade['entry_time']} at {trade.get('actual_entry_price', trade['entry_price']):.2f}")
            print(f"  Exit:  {trade['exit_time']} at {trade['exit_price']:.2f} ({trade['exit_reason']})")
            print(f"  P&L: {trade['pnl']:.2f}")
        
        print("\n" + "-"*40)
        print(f"Total Trades: {len(self.completed_trades)}")
        print(f"Total Net P&L: {total_pnl:.2f}")
        print("="*80)

    def save_trades_to_journal(self, raw_file_name, journal_path='trade_journal.csv'):
        if not self.completed_trades: return
        try:
            date_str = os.path.basename(raw_file_name).split('_')[1]
            trade_date = dt.datetime.strptime(date_str, '%m%d%y').strftime('%m-%d-%Y')
        except (IndexError, ValueError):
            trade_date = 'unknown'

        trades_df = pd.DataFrame(self.completed_trades)
        trades_df['trade_date'] = trade_date
        
        cols = ['trade_date'] + [col for col in trades_df.columns if col != 'trade_date']
        trades_df = trades_df[cols]

        file_exists = os.path.isfile(journal_path)
        trades_df.to_csv(journal_path, mode='a', header=not file_exists, index=False)
        print(f"--- Saved {len(self.completed_trades)} trade records to {journal_path} for date {trade_date} ---")
        
        self.completed_trades = []
