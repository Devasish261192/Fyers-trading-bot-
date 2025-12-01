'''HisData_bydate (symbol, tf,sd,ed,fyers)'''
import os
from fyers_apiv3 import fyersModel
import pandas as pd
import numpy as np
import datetime as dt



# Get the current date in the format 'YYYY-MM-DD'
current_date = dt.datetime.now().strftime('%Y-%m-%d') # Define the folder and file paths
folder_path = os.path.join(r'D:\00_ml_trading\api_logs', current_date)
file_path = os.path.join(folder_path, 'symbols.txt')


def HisData_bydate (symbol, tf,sd,ed,fyers):
    """ 
    example_usage = HisData_bydate ('NSE:BAJAJ-AUTO-EQ', '1','2023-10-14','2023-12-10',fyers)
    """
    data = {"symbol":symbol,"resolution":str(tf),
    "date_format":"1",
    "range_from":str(sd),
    "range_to":str(ed),
    "cont_flag":"1"}
    response = fyers.history(data=data)  
    # print(response)                                                           #fetching the data from historical API
    try:
        raw_df= pd.DataFrame(response['candles'])                                                       #creating raw data frame
        raw_df.columns=['timestamp','Open','High','Low','Close','tradingVolume']     # appending the collumns of data frame
        raw_df['timestamp'] = pd.to_datetime(raw_df['timestamp'],unit='s')                                # converting date time from string to date time format
        raw_df.timestamp = (raw_df.timestamp.dt.tz_localize('UTC').dt.tz_convert('Asia/Kolkata'))         #converting timeframe to IST
        raw_df['timestamp'] = raw_df['timestamp'].dt.tz_localize(None)                                    # localizing
        raw_df = raw_df.set_index('timestamp')
        return raw_df
    except:
        print(response)
        
def full_df_generator(symbol, yrs, tf, fyers, start_date=None, end_date=None):
    """ 
    takes the number of years for the data pull
    example usage : sample_df = full_df_generator ('NSE:BAJAJ-AUTO-EQ', fyers,3)
    
    Parameters:
    - symbol (str): The symbol for which the data is to be fetched.
    - fyers (object): The fyers model object.
    - start_date (datetime.date, optional): The start date for data fetching.
    - end_date (datetime.date, optional): The end date for data fetching.
    
    Returns:
    - pd.DataFrame: A dataframe with the historical data sorted by index.
    """
    
    # Set default end date to current date if not provided
    if end_date is None:
        end_date = dt.datetime.now().date()
    
    # Set default start date to 5-1-2017 if not provided
    if start_date is None:
        start_date = end_date - dt.timedelta(weeks=yrs*53)
    
    df = pd.DataFrame()
    ed = end_date
    
    while True:
        sd = (ed - dt.timedelta(days=99))
        
        # Stop if start date is reached
        if sd < start_date:
            sd = start_date
        
        # print(symbol)
        # print(sd)
        # print(ed)
        
    
        try:
            dx = HisData_bydate(symbol, tf, sd, ed, fyers)
            df = df._append(dx)
        except Exception as e:
            print(f"Error or is done: {e}")
            break
        
        ed = sd
        
        # Break the loop if the start date is reached
        if ed <= start_date:
            break
    
    df_sorted = df.sort_index()
    return df_sorted

