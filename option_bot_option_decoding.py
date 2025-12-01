from datetime import datetime, timedelta
from dateutil import relativedelta
import re
from typing import Dict, Tuple

def get_last_thursday(year: int, month_str: str) -> str:
    """
    Calculate the last Thursday of the given year and month.
    
    Args:
        year (int): Year (e.g., 2025)
        month_str (str): Month abbreviation (e.g., 'AUG')
    
    Returns:
        str: Date in YYYY-MM-DD format for the last Thursday
    """
    month_map = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }
    month = month_map[month_str.upper()]
    
    # Get the last day of the month
    last_day = datetime(year, month, 1) + relativedelta.relativedelta(months=1) - timedelta(days=1)
    
    # Find the last Thursday
    while last_day.weekday() != 3:  # Thursday is 3 in datetime.weekday()
        last_day -= timedelta(days=1)
    
    return last_day.strftime("%Y-%m-%d")

def decode_filename(filename: str) -> Dict[str, str]:
    """
    Decode a NIFTY option filename into its components.
    
    Args:
        filename (str): Filename like 'NIFTY2561223750PE.csv' or 'NIFTY25AUG25150PE.csv'
    
    Returns:
        Dict[str, str]: Dictionary with decoded components
    """
    # Remove .csv extension
    name = filename.replace('.csv', '')
    
    # Initialize components
    instrument = "NIFTY"
    expiry_date = ""
    strike_price = ""
    option_type = ""
    
    # Regex patterns for the two formats
    specific_date_pattern = r"NIFTY(\d{2})(\d{1})(\d{2})(\d+)(CE|PE)"
    monthly_date_pattern = r"NIFTY(\d{2})([A-Z]{3})(\d+)(CE|PE)"
    
    # Check for specific date format (e.g., NIFTY2561223750PE)
    specific_match = re.match(specific_date_pattern, name)
    if specific_match:
        year, month, day, strike, opt_type = specific_match.groups()
        year = f"20{year}"  # Convert YY to YYYY
        expiry_date = f"{year}-{month}-{day}"
        strike_price = strike
        option_type = opt_type
    else:
        # Check for monthly date format (e.g., NIFTY25AUG25150PE)
        monthly_match = re.match(monthly_date_pattern, name)
        if monthly_match:
            year, month_str, strike, opt_type = monthly_match.groups()
            year = f"20{year}"  # Convert YY to YYYY
            expiry_date = get_last_thursday(int(year), month_str)
            strike_price = strike
            option_type = opt_type
    
    return {
        "instrument": instrument,
        "expiry_date": expiry_date,
        "strike_price": strike_price,
        "option_type": option_type
    }