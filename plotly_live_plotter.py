import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from threading import Thread, Lock
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class DashPlotter:
    def __init__(self):
        self.df = pd.DataFrame()
        self.option_chain = pd.DataFrame()
        self.lock = Lock()
        self.app = dash.Dash(__name__)
        self.trading_timeframe = 3

        # Layout with fixed height: 1200px total → 900px main + 300px subplot
        self.app.layout = html.Div([
            html.H1("Live Nifty Multi-Timeframe Chart", style={'textAlign': 'center'}),
            dcc.Graph(id='live-update-graph', style={'height': '1200px', 'width': '100%'}),
            dcc.Interval(id='interval-component', interval=2*1000, n_intervals=0),
            html.H2("Option Chain", style={'textAlign': 'center'}),
            dash_table.DataTable(
                id='option-chain-table',
                columns=[
                    {"name": "CE Option", "id": "CE Option"},
                    {"name": "CE LTP", "id": "CE LTP"},
                    {"name": "PE Option", "id": "PE Option"},
                    {"name": "PE LTP", "id": "PE LTP"},
                ],
                data=[],
            )
        ])

        self.app.callback(
            [Output('live-update-graph', 'figure'),
             Output('option-chain-table', 'data')],
            [Input('interval-component', 'n_intervals')])(self.update_graph_and_table)

        self.server_thread = Thread(target=self.run_app)
        self.server_thread.daemon = True
        self.server_thread.start()
        print("\n--- Live Plot Initialized ---")
        print("Open http://127.0.0.1:8050")
        print("Main Chart: 900px | WILLR Subplot: 300px")
        print("Fractals marked ±5 units on WILLR subplot")
        print("-----------------------------\n")

    def run_app(self):
        self.app.run(debug=False, port=8050)

    def update_data(self, new_df, trading_timeframe=None, option_chain=None):
        with self.lock:
            self.df = new_df
            if trading_timeframe:
                self.trading_timeframe = trading_timeframe
            if option_chain is not None:
                self.option_chain = option_chain

    def update_graph_and_table(self, n):
        with self.lock:
            df = self.df.copy()
            option_chain = self.option_chain.copy()
            title = f'Live Nifty {self.trading_timeframe}-Min Chart'

        if df.empty:
            empty_fig = go.Figure()
            empty_fig.update_layout(title_text='Waiting for data...', height=1200)
            return empty_fig, []

        # === CREATE SUBPLOTS: 2 rows ===
        # Row 1: Candles + Fractals (900px)
        # Row 2: Williams %R (300px)
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,
            row_heights=[0.75, 0.25],  # 75% + 25% → 900px + 300px
            subplot_titles=(f'Nifty {self.trading_timeframe}-Min', 'Williams %R (20)')
        )

        # === ROW 1: PRICE CHART ===
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df['open'],
            high=df['high'],
            low=df['low'],
            close=df['close'],
            name='Candles'
        ), row=1, col=1)

        # SMA Line
        if 'SMA_50' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df['SMA_50'],
                mode='lines', name='SMA 50',
                line=dict(color='blue', width=2)
            ), row=1, col=1)

        # Up Fractals (on price chart)
        if 'up_fractal' in df.columns:
            up = df['up_fractal'].dropna()
            if not up.empty:
                fig.add_trace(go.Scatter(
                    x=up.index, y=up.values,
                    mode='markers', name='Up Fractal',
                    marker=dict(symbol='triangle-up', color='lime', size=14,
                                line=dict(width=2, color='darkgreen'))
                ), row=1, col=1)

        # Down Fractals (on price chart)
        if 'down_fractal' in df.columns:
            down = df['down_fractal'].dropna()
            if not down.empty:
                fig.add_trace(go.Scatter(
                    x=down.index, y=down.values,
                    mode='markers', name='Down Fractal',
                    marker=dict(symbol='triangle-down', color='red', size=14,
                                line=dict(width=2, color='darkred'))
                ), row=1, col=1)

        # === ROW 2: WILLIAMS %R SUBPLOT ===
        # WILLR_14 (current TF)
        if 'WILLR_20' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df['WILLR_20'],
                mode='lines', name='WILLR 20',
                line=dict(color='purple', width=2)
            ), row=2, col=1)

        # WILLR_15 (projected)
        if 'WILLR_15' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df['WILLR_15'],
                mode='lines', name='WILLR 15-min',
                line=dict(color='sienna', width=2, dash='dot')
            ), row=2, col=1)

        # WILLR_45 (projected)
        if 'WILLR_45' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df['WILLR_45'],
                mode='lines', name='WILLR 45-min',
                line=dict(color='darkviolet', width=2, dash='dashdot')
            ), row=2, col=1)

        # Overbought / Oversold lines
        fig.add_hline(y=-80, line_dash="dash", line_color="red",
                      annotation_text="Overbought", row=2, col=1)
        fig.add_hline(y=-20, line_dash="dash", line_color="green",
                      annotation_text="Oversold", row=2, col=1)

        # Rejection lines
        fig.add_hline(y=-30, line_dash="dot", line_color="orange",
                      annotation_text="Bullish Rejection", row=2, col=1)
        fig.add_hline(y=-70, line_dash="dot", line_color="blue",
                      annotation_text="Bearish Rejection", row=2, col=1)

        # === FRACTALS ON WILLR SUBPLOT (±5 units) ===
        if 'WILLR_20' in df.columns:
            willr_val = df['WILLR_20']

            # Up Fractal: +5 above current WILLR
            if 'up_fractal' in df.columns:
                up_idx = df['up_fractal'].dropna().index
                up_willr = willr_val.loc[up_idx]
                fig.add_trace(go.Scatter(
                    x=up_idx, y=up_willr + 5,
                    mode='markers', name='Up Fractal (WILLR)',
                    marker=dict(symbol='triangle-up', color='lime', size=10)
                ), row=2, col=1)

            # Down Fractal: -5 below current WILLR
            if 'down_fractal' in df.columns:
                down_idx = df['down_fractal'].dropna().index
                down_willr = willr_val.loc[down_idx]
                fig.add_trace(go.Scatter(
                    x=down_idx, y=down_willr - 5,
                    mode='markers', name='Down Fractal (WILLR)',
                    marker=dict(symbol='triangle-down', color='red', size=10)
                ), row=2, col=1)

        # === LAYOUT & STYLING ===
        fig.update_layout(
            title_text=title,
            height=1200,
            hovermode='x unified',
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=80, b=50)
        )

        # Y-axis for price
        price_min = df['low'].min() - 25
        price_max = df['high'].max() + 25
        fig.update_yaxes(title_text="Price", range=[price_min, price_max], row=1, col=1)

        # Y-axis for WILLR
        fig.update_yaxes(title_text="Williams %R", range=[-100, 0], row=2, col=1)

        # Hide non-trading periods
        fig.update_xaxes(
            rangebreaks=[
                dict(bounds=["sat", "mon"]), # Hide weekends
                dict(bounds=[15.5, 9.25], pattern="hour"), # Hide overnight gaps
            ]
        )

        # Prepare option chain data for the table
        ce_options = option_chain[option_chain['Symbol'].str.contains('CE')].copy()
        pe_options = option_chain[option_chain['Symbol'].str.contains('PE')].copy()

        # Sort by strike price (assuming strike is part of the symbol and can be extracted)
        ce_options['Strike'] = ce_options['Symbol'].apply(lambda x: int(''.join(filter(str.isdigit, x.split('CE')[0].split(':')[-1]))))
        pe_options['Strike'] = pe_options['Symbol'].apply(lambda x: int(''.join(filter(str.isdigit, x.split('PE')[0].split(':')[-1]))))

        ce_options = ce_options.sort_values(by='Strike').drop(columns=['Strike'])
        pe_options = pe_options.sort_values(by='Strike').drop(columns=['Strike'])

        # Pad with empty rows if one side has fewer options
        max_len = max(len(ce_options), len(pe_options))
        if len(ce_options) < max_len:
            ce_options = pd.concat([ce_options, pd.DataFrame([{"Symbol": "", "Price": ""}] * (max_len - len(ce_options)))])
        if len(pe_options) < max_len:
            pe_options = pd.concat([pe_options, pd.DataFrame([{"Symbol": "", "Price": ""}] * (max_len - len(pe_options)))])

        # Combine into a single DataFrame for display
        combined_option_chain = pd.DataFrame({
            "CE Option": ce_options['Symbol'].reset_index(drop=True),
            "CE LTP": ce_options['Price'].reset_index(drop=True),
            "PE Option": pe_options['Symbol'].reset_index(drop=True),
            "PE LTP": pe_options['Price'].reset_index(drop=True),
        })

        return fig, combined_option_chain.to_dict('records')