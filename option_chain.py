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



def options_chain_for_trade(symbol,number_of_strikes,fyers):
    expiry_dfs = {}
    data = {
        "symbol":symbol,
        "strikecount":number_of_strikes,
        "timestamp": ""
    }
    response = fyers.optionchain(data=data)
    oi_data = pd.DataFrame.from_dict(response['data']['optionsChain'])
    current_expiry = response['data']['expiryData'][1]['date']
    expiry_timestamps = response['data']['expiryData']
    oi_data_1 = oi_data[['strike_price','symbol','option_type','ltp','oi','volume']].copy()
    expiry_dfs[current_expiry] = oi_data_1
    print(current_expiry)
    for i in range(1,len(expiry_timestamps)):
        exp_time_stamp = expiry_timestamps[i]['expiry'] 
        exp_date = expiry_timestamps[i]['date']
        data_2 = {
            "symbol":symbol,
            "strikecount":number_of_strikes,
            "timestamp": exp_time_stamp
            }
        response_2 = fyers.optionchain(data=data_2)
        oi_data_2 = pd.DataFrame.from_dict(response_2['data']['optionsChain'])
        oi_data_2 = oi_data_2[['strike_price','symbol','option_type','ltp','oi','volume']].copy()
        expiry_dfs[exp_date] = oi_data_2
    return expiry_dfs


def current_expiry_option(symbol,number_of_strikes,fyers):
    expiry_dfs = {}
    data = {
        "symbol":symbol,
        "strikecount":number_of_strikes,
        "timestamp": ""
    }
    response = fyers.optionchain(data=data)
    oi_data = pd.DataFrame.from_dict(response['data']['optionsChain'])
    current_expiry = response['data']['expiryData'][1]['date']
    expiry_timestamps = response['data']['expiryData']
    oi_data_1 = oi_data[['strike_price','symbol','option_type','ltp','oi','volume']].copy()
    return [current_expiry,oi_data_1,expiry_timestamps]