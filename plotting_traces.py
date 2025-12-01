import plotly.graph_objs as go
import pandas as pd
def create_fractal_traces(df):
    """
    Generates fractal point traces based on the provided fractal orders.

    Args:
        df (pd.DataFrame): DataFrame containing OHLC data and fractal columns.
        fractal_orders (dict): Dictionary defining fractal orders with their properties (color, high_factor, low_factor).

    Returns:
        list: A list of Plotly scatter traces for fractals.
    """
    
    fractal_traces = []
    
    if 'upfractal' in df.columns:
        upfractal_df = df[df['upfractal'] == 1]
        trace_upfractal = go.Scatter(
            x=upfractal_df.index,
            y=upfractal_df['High'] * 1.001,  # Slightly above high for visibility
            mode='markers',
            name='Up Fractal',
            marker=dict(
                symbol='triangle-up',
                size=10,
                color='green'
            )
        )
        fractal_traces.append(trace_upfractal)

    # Downfractal trace (place marker at Low of candle)
    if 'downfractal' in df.columns:
        downfractal_df = df[df['downfractal'] == -1]
        trace_downfractal = go.Scatter(
            x=downfractal_df.index,
            y=downfractal_df['Low'] * 0.999,  # Slightly below low for visibility
            mode='markers',
            name='Down Fractal',
            marker=dict(
                symbol='triangle-down',
                size=10,
                color='red'
            )
        )
        fractal_traces.append(trace_downfractal)

        

    return fractal_traces


import plotly.graph_objects as go
import pandas as pd
import numpy as np

def plot_ohlcv(df, additional_traces=None):
    """
    Creates a Plotly OHLC chart with continuous candlesticks for daily/weekly data
    and appropriate gaps for intraday data. Handles missing dates (e.g., holidays) by
    plotting continuous candlesticks.

    Args:
        df (pd.DataFrame): DataFrame containing OHLC data with 'Open', 'High', 'Low', 'Close'
                           columns, indexed by timestamp.
        additional_traces (list, optional): List of additional Plotly traces to add to the chart.

    Returns:
        go.Figure: The Plotly figure object representing the chart.
    """
    # Validate input DataFrame
    required_columns = ['Open', 'High', 'Low', 'Close']
    if not all(col in df.columns for col in required_columns):
        raise ValueError(f"DataFrame must contain columns: {required_columns}")

    # Ensure index is datetime
    df = df.copy()
    df.index = pd.to_datetime(df.index)

    # Check for valid OHLC data
    if df[required_columns].isna().any().any():
        raise ValueError("OHLC columns contain NaN values")

    # Detect data frequency
    time_diffs = df.index.to_series().diff().dropna()
    if len(time_diffs) > 0:
        median_diff = time_diffs.median()
        if median_diff <= pd.Timedelta(hours=1):
            freq = 'intraday'
        elif median_diff >= pd.Timedelta(days=6):
            freq = 'weekly'
        else:
            freq = 'daily'
    else:
        freq = 'daily'  # Default to daily if insufficient data to determine

    # Create OHLC trace
    trace_ohlc = go.Ohlc(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='OHLC'
    )

    # Combine traces
    traces = [trace_ohlc]
    if additional_traces and isinstance(additional_traces, list):
        traces.extend(additional_traces)

    # Configure rangebreaks based on frequency
    rangebreaks = []
    if freq == 'intraday':
        # Exclude non-trading hours (15:30 to 9:15 next day)
        rangebreaks.append(dict(bounds=[15.5, 9.25], pattern="hour"))
        # Exclude weekends
        rangebreaks.append(dict(bounds=["sat", "mon"]))
    # For daily/weekly, no rangebreaks to ensure continuous candlesticks (no gaps for holidays/weekends)

    # Create layout
    layout = go.Layout(
        title=f'{freq.capitalize()} OHLC Chart',
        xaxis_title='Timestamp',
        yaxis_title='Price',
        height=1000,
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        xaxis=dict(
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            showline=True,
            spikethickness=1,
            spikecolor='blue',
            rangebreaks=rangebreaks
        ),
        yaxis=dict(
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            spikethickness=1,
            spikecolor='blue'
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Rockwell"
        )
    )

    # Create figure
    fig = go.Figure(data=traces, layout=layout)
    fig.update_layout(
        xaxis=dict(title="Date"),
        yaxis=dict(title="Price"),
        title=f"{freq.capitalize()} Candlestick Chart Without Gaps",
        xaxis_rangeslider_visible=False
    )

    return fig

# Example Usage:
# Assume `df` is your DataFrame with OHLC and fractal data
# fractal_traces = create_fractal_traces(df)
# plot_ohlcv(df, additional_traces=fractal_traces)



def create_filtered_wave_traces(daily_df, wave_data):
    """
    Generates Plotly traces based on impulse wave data extracted from different wave types.

    Args:
        daily_df (pd.DataFrame): DataFrame containing daily OHLC data.
        impulse_data (list): List of dictionaries containing impulse points.

    Returns:
        list: List of Plotly traces for visualization.
    """
    traces = []

    color_map = {
        'up_imp_points': "green",
        'dn_imp_points': "red",
        'up_ABC_points': "blue",
        'dn_ABC_points': "yellow"
    }

    for i, wave_dict in enumerate(wave_data):
        for wave_type, values in wave_dict.items():
            start_timestamp = values[0]
            end_timestamp = values[-1]

            # Slice DataFrame for relevant range
            sliced_df = daily_df.loc[start_timestamp:end_timestamp]

            # Identify fractal highs and lows
            fractal_points = sliced_df[(sliced_df['upfractal'] == 1) | (sliced_df['downfractal'] == -1)]
            
            # Filter consecutive same-type fractals, keeping highest/lower
            filtered_points = []
            last_fractal_type = None
            for idx, row in fractal_points.iterrows():
                fractal_type = 'high' if row['upfractal'] == 1 else 'low'

                if last_fractal_type == fractal_type:
                    if fractal_type == 'high' and row['High'] > filtered_points[-1][1]:
                        filtered_points[-1] = (idx, row['High'])
                    elif fractal_type == 'low' and row['Low'] < filtered_points[-1][1]:
                        filtered_points[-1] = (idx, row['Low'])
                else:
                    filtered_points.append((idx, row['High'] if fractal_type == 'high' else row['Low']))

                last_fractal_type = fractal_type

            # Extract timestamps and prices
            timestamps, prices = zip(*filtered_points) if filtered_points else ([], [])

            # Set color dynamically based on wave type
            color = color_map.get(wave_type, "gray")

            # Create trace
            if timestamps:
                trace = go.Scatter(
                    x=timestamps,
                    y=prices,
                    mode='lines+markers',
                    marker=dict(size=8, color=color),
                    line=dict(width=2, color=color),
                    name=f"{wave_type.replace('_', ' ').title()} - Wave {i+1}"
                )
                traces.append(trace)

    return traces



def plot_ohlcv_DWM(df, timeframe='daily', additional_traces=None):
    """
    Plots OHLCV data for daily, weekly, or monthly timeframes using Plotly.

    Args:
        daily_df (pd.DataFrame): Daily OHLCV DataFrame.
        weekly_df (pd.DataFrame): Weekly OHLCV DataFrame.
        monthly_df (pd.DataFrame): Monthly OHLCV DataFrame.
        timeframe (str): Timeframe to plot ('daily', 'weekly', 'monthly').
        additional_traces (list): List of additional Plotly traces.

    Returns:
        go.Figure: The generated Plotly figure.
    """
    # Select the correct DataFrame
    if timeframe == 'daily':
        df = df.copy()
        title = "Daily OHLC Chart"
    elif timeframe == 'weekly':
        df = df.copy()
        title = "Weekly OHLC Chart"
    elif timeframe == 'monthly':
        df = df.copy()
        title = "Monthly OHLC Chart"
    else:
        raise ValueError("Invalid timeframe. Choose 'daily', 'weekly', or 'monthly'.")

    # Ensure datetime index
    df.index = pd.to_datetime(df.index)

    # Create the OHLC trace
    trace_ohlc = go.Ohlc(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name=f"{timeframe.capitalize()} OHLC"
    )

    # Collect traces
    traces = [trace_ohlc]
    if additional_traces and isinstance(additional_traces, list):
        traces.extend(additional_traces)

    # Layout
    layout = go.Layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price",
        height=800,
        xaxis_rangeslider_visible=False,
        hovermode='x unified',
        xaxis=dict(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikecolor="blue",
        ),
        yaxis=dict(
            showspikes=True,
            spikemode="across",
            spikesnap="cursor",
            spikethickness=1,
            spikecolor="blue",
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=12,
            font_family="Rockwell"
        )
    )

    # Create and display figure
    fig = go.Figure(data=traces, layout=layout)
    fig.show()

    # return fig