def get_profile(fyers):
        response = fyers.get_profile()
        print(response)

def funds(fyers):
        response = fyers.funds()
        print(response)

def holdings(fyers):
        response = fyers.holdings()
        print(response)

def logout(fyers):
        response = fyers.logout()

def orders(fyers):
        response = fyers.orderbook()
        print(response)

def filter_orders_Id(fyers,orderId):
        
        #orderId = "23080444447604" #filter by order id
        data = {"id":orderId}
        response = fyers.orderbook(data=data)
        print(response)

def postions(fyers):
        response = fyers.positions()
        print(response)

def trades(fyers):
        response = fyers.tradebook()
        print(response)     

def get_data_dict_for_order_placement(symbol,qty):
        data = {
            "symbol":symbol,
            "qty":qty,
            "type":2,
            "side":1,
            "productType":"INTRADAY",
            "limitPrice":0,
            "stopPrice":0,
            "validity":"DAY",
            "disclosedQty":0,
            "offlineOrder":False,
            "orderTag":"tag1"}
        
        return data

def place_order(fyers,data):
        
    
        response = fyers.place_order(data=data)
        print(response)


def load_credentials(filepath):
        creds = {}
        with open(filepath, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    creds[key.strip()] = value.strip().strip('"')
        return creds

def get_all_stocks_symbols(stocks_symbols_path):
    import ast
    try:
        with open(stocks_symbols_path, "r") as file:
            file_content = file.read()
            my_list = ast.literal_eval(file_content)
            return my_list
    except FileNotFoundError:
        print(f"Error: The file '{stocks_symbols_path}' was not found.")