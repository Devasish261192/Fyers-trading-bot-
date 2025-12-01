import pandas as pd
import os
import datetime as dt

############## RESAMPLE BY Timeframe ###################################################################
def resample_df(df, timeframe):
    """base function to resample dataframes where index is timestamp 

    Args:
        df (dataframe): df of stock OHLCV values
        timeframe (string): 15T,30T, 75T "T will be replaced by min in future"

    Returns:
        _type_: _description_
    """
    df.index = pd.to_datetime(df.index)
    df['day'] = df.index.date

    # Filter data within the time range 09:15 to 15:30
    df = df.between_time('09:15', '15:30')

    gp = df.groupby('day')
    dflist = []

    for k, res in gp:
        resample_dataframe = res.resample(timeframe, origin='start').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'tradingVolume': 'sum'
        })
        resample_dataframe.reset_index(inplace=True)
        dflist.append(resample_dataframe)

    resample_dataframe = pd.concat(dflist, ignore_index=True)
    resample_dataframe.set_index('timestamp', inplace=True)
    return resample_dataframe

def resample_daily_to_weekly_monthly(df):
    '''
        takes dataframe in daily format resamples 
        uase: resample_daily_to_weekly_monthly(df)
        
    '''
    
    # Convert timestamp to datetime and create a 'Date' column
    df.index = pd.to_datetime(df.index)
    df['Date'] = df.index.date

    # Drop the 'timestamp' column
    # df = df.drop(columns=['timestamp'])

    # Resample data into weekly and monthly DataFrames
    df.set_index(pd.to_datetime(df['Date']), inplace=True)  # Set index for resampling

    # Resample weekly (starting from Monday)
    weekly_df = df.resample('W-MON', label='left').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'tradingVolume': 'sum'
    })

    # Resample monthly with the 1st of the month as the index
    monthly_df = df.resample('MS').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'tradingVolume': 'sum'
    })

    weekly_df.reset_index(inplace=True)
    monthly_df.reset_index(inplace=True)
    weekly_df = weekly_df.set_index('Date',drop=True)
    monthly_df = monthly_df.set_index('Date',drop=True)
    return weekly_df,monthly_df


def filter_stocks_dict(stocks_dict, watchlist):
    """filters the raw dict ciontaining all dataframes and stocks data with our oun list of stocks and data

    Args:
        stocks_dict (_type_): _description_
        watchlist (_type_): _description_

    Returns:
        _type_: _description_
    """
    filtered_dict = {}
    for key in stocks_dict.keys():
        # Extract the symbol from the key
        symbol = key.split('/')[1]
        if symbol in watchlist:
            filtered_dict[key] = stocks_dict[key]
    return filtered_dict

def filter_last_300_days(df_dict):
    """when passed with a dict it only keeps the data for last available 300 days for fast analysis

    Args:
        df_dict (dict): dict{stock: dataframe}

    Returns:
        (dict): dict{stock: dataframe}
    """
    days_300_dict = {}
    current_date = pd.to_datetime("today")
    cutoff_date = current_date - pd.Timedelta(days=200)

    for key, df in df_dict.items():
        # Filter the DataFrame to keep only rows within the last 300 days
        filtered_df = df[df.index >= cutoff_date]
        days_300_dict[key] = filtered_df

    return days_300_dict

def resampled_dict(filtered_stocks_dictionary,Timeframe):
    """used when we have a dict with keys and dataframes to resample full dict

    Args:
        filtered_stocks_dictionary (dict): dictionary for stock and dataframe
        Timeframe (string): time interval in which we want to resample eg 15T or 15min 

    Returns:
        (dict): dict{stock: dataframe}
    """
    resample_dfs = {}
    for key, test_df in filtered_stocks_dictionary.items():
        test_df = resample_df(test_df,Timeframe)
        df_copy = test_df.copy()  # To avoid SettingWithCopyWarning
        # dtosc_df = dtosc(df_copy)

        resample_dfs[key] = df_copy
    return resample_dfs


def combine_dicts(dict_5min, dict_15min, dict_30min, dict_60min):
    combined_dict = {}
    
    # Dictionary of timeframes
    timeframes = [dict_5min, dict_15min, dict_30min, dict_60min]
        
    # Process each dictionary
    for i, dictionary in enumerate(timeframes):
        for key, df in dictionary.items():
            symbol = key.split('/')[1]
            if symbol not in combined_dict:
                combined_dict[symbol] = [None] * len(timeframes)  # Initialize list for all timeframes
            combined_dict[symbol][i] = df  # Set the dataframe at the correct index
    
    return combined_dict

