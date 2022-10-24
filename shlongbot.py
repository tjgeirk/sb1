import pandas as pd
import numpy as np
import ccxt
import time
import datetime
import ta
import sys
import logging

####################### Information ####################

KUCOIN_FUTURES_API_KEY = ''
KUCOIN_FUTURES_SECRET_KEY = ''
KUCOIN_FUTURES_PASSWORD = ''

coin_name = "FIL"  # coin name
timeframe = "15m"   # timeframe  --> 5m , 15m, 30m, 1h, 4h, 1d
leverage = 5
direction = "long" # long , short
trade_risk_pcnt = 0.25 # 25% risk

jawLength = 4
teethLength = 3
lipsLength = 2
smoothinput = 1

exchange=ccxt.kucoinfutures({
    'adjustForTimeDifference': True,
    "apiKey": KUCOIN_FUTURES_API_KEY,
    "secret": KUCOIN_FUTURES_SECRET_KEY,
    "password": KUCOIN_FUTURES_PASSWORD,
    })

coin=coin_name+"/USDT:USDT"
# balance = exchange.fetch_balance({'currency': 'USDT'})
balance = float(exchange.fetch_balance({'currency': 'USDT'})['free']['USDT'])
print(balance)

def heikin_ashi(df):
    heikin_ashi_df = pd.DataFrame(index=df.index.values, columns=['open', 'high', 'low', 'close'])
    heikin_ashi_df['date']=df['date']
    heikin_ashi_df['close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    for i in range(len(df)):
        if i == 0:
            heikin_ashi_df.iat[0, 0] = df['open'].iloc[0]
        else:
            heikin_ashi_df.iat[i, 0] = (heikin_ashi_df.iat[i-1, 0] + heikin_ashi_df.iat[i-1, 3]) / 2
    heikin_ashi_df['high'] = heikin_ashi_df.loc[:, ['open', 'close']].join(df['high']).max(axis=1)
    heikin_ashi_df['low'] = heikin_ashi_df.loc[:, ['open', 'close']].join(df['low']).min(axis=1)
    return heikin_ashi_df
def get_data(coin,tf):
    data = exchange.fetch_ohlcv(coin, timeframe=tf,limit=500)
    df = {}
    for i, col in enumerate(['date','open','high','low','close','volume']):
        df[col] = []
        for row in data:
            if col == 'date':
                df[col].append(datetime.datetime.fromtimestamp(row[i]/1000))
            else:
                df[col].append(row[i])
    DF = pd.DataFrame(df)
    return DF

def calc_ma(src,l):
    if smoothinput == 1:
        return ta.trend.sma_indicator(src,l)
    elif smoothinput == 2:
        return ta.trend.ema_indicator(src,l)
    elif smoothinput ==3:
        return ta.trend.wma_indicator(src,l)
    elif smoothinput == 4:
        return None
    elif smoothinput ==5:
        return None

def market_trade(exchange, symbol, side, tradeSize, reduceOnly, leverage):
    order=exchange.create_order(symbol, 'market', side=side, amount=tradeSize, params={'reduceOnly':reduceOnly, 'leverage':leverage})
    print(order)

logging.getLogger("requests").setLevel(logging.ERROR)
logging.getLogger("pandas").setLevel(logging.ERROR)
logging.getLogger("numpy").setLevel(logging.ERROR)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)
file_handler = logging.FileHandler('report.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stdout_handler)
sys.tracebacklimit = 0



# # # # #  L O N G  # # # # #
if direction == str("long"):
    print("RUNNING LONG PROGRAM")
    r = open("db.txt", "r")
    in_position,qty = r.read().split(",")
    r.close()
    if in_position=='False':
        in_position=False
        qty=0
    else:
        in_position=True
        qty=float(qty)
    while True:
        try:
            candles = heikin_ashi(get_data(coin=coin,tf=timeframe))
        except:
            time.sleep(25)
        candles = candles.iloc[1:len(candles)-1].copy().reset_index(drop=True)
        close = candles['close'].iloc[-1]
        Open = candles['open'].iloc[-1]
        closee = candles['close'].iloc[-2]
        Openn = candles['open'].iloc[-2]
        if (close > Open) and (closee > Openn):
            direzione = 1
        elif (close < Open) and (closee < Openn):
            direzione = -1
        else:
            direzione = 0
        jaw = calc_ma((candles['high']+candles['low'])/2, jawLength).iloc[-1]
        teeth = calc_ma((candles['high']+candles['low'])/2, teethLength).iloc[-1]
        lips = calc_ma((candles['high']+candles['low'])/2, lipsLength).iloc[-1]
        buy = direzione==1 and jaw < teeth and jaw < lips and teeth < lips
        sell = jaw > teeth or jaw > lips or teeth > lips
        if in_position:
            logger.info("Waiting for Sell Signal")
        else:
            logger.info("Waiting for Buy Signal")
        if buy and not in_position:
            logger.info(f"Received Buy Signal for {coin_name} ... Trying to Buy it")
            if balance > 0:
                markets = exchange.load_markets()
                market = exchange.market(coin)
                lotSize = market['contractSize']
                available_balance = trade_risk_pcnt * balance
                prev_close = float(exchange.fetch_ticker(coin)['close'])
                qty = available_balance / prev_close
                if qty > lotSize:
                    qty = int(qty / lotSize * leverage)
                elif qty < lotSize:
                    qty = int(lotSize / qty * leverage)
                try:
                    market_trade(exchange, coin, 'buy', qty, False, leverage)
                    logger.info(f"{coin_name} is bought!")
                    in_position=True
                    f = open("db.txt", "w")
                    msg = "True,"+str(qty)
                    f.write(msg)
                    f.close()
                except Exception as e:
                    logger.info(f"Could not Place order due to ",e)
            else:
                logger.info(f"Can't Buy.... Balance = {balance}")
        if sell and in_position:
            logger.info(f"Received Sell Signal for {coin_name}... Trying to Sell")
            try:
                market_trade(exchange, coin, 'sell', qty, True, leverage)
                in_position = False
                qty =0
                f = open("db.txt", "w")
                msg = "False,0"
                f.write(msg)
                f.close()
            except Exception as e:
                logger.info(f"Could not place sell order due to ",e)
        time.sleep(10)


        
# # # # # S H O R T # # # # #

elif direction == str("short"):
    print("RUNNING SHORT PROGRAM")
    r = open("db.txt", "r")
    in_position,qty = r.read().split(",")
    r.close()
    if in_position=='False':
        in_position=False
        qty=0
    else:
        in_position=True
        qty=float(qty)
    while True:
        try:
            candles = heikin_ashi(get_data(coin=coin,tf=timeframe))
        except:
            time.sleep(25)
        candles = candles.iloc[1:len(candles)-1].copy().reset_index(drop=True)
        close = candles['close'].iloc[-1]
        Open = candles['open'].iloc[-1]
        closee = candles['close'].iloc[-2]
        Openn = candles['open'].iloc[-2]
        if (close > Open) and (closee >Openn):
            direzione = 1
        elif (close < Open) and (closee < Openn):
            direzione = -1
        else:
            direzione = 0
        jaw = calc_ma((candles['high']+candles['low'])/2, jawLength).iloc[-1]
        teeth = calc_ma((candles['high']+candles['low'])/2, teethLength).iloc[-1]
        lips = calc_ma((candles['high']+candles['low'])/2, lipsLength).iloc[-1]
        buy = direzione==1 and jaw < teeth and jaw < lips and teeth < lips
        sell = jaw > teeth or jaw > lips or teeth > lips
        if in_position:
            logger.info("Waiting for Close Signal")
        else:
            logger.info("Waiting for Short Signal")
        if sell and not in_position:
            logger.info(f"Received Short Signal for {coin_name}... Trying to Short it")
            if balance > 0:
                markets = exchange.load_markets()
                market = exchange.market(coin)
                lotSize = market['contractSize']
                available_balance = trade_risk_pcnt * balance
                prev_close = float(exchange.fetch_ticker(coin)['close'])
                qty = available_balance / prev_close
                if qty > lotSize:
                    qty = int(qty / lotSize * leverage)
                elif qty < lotSize:
                    qty = int(lotSize / qty * leverage)
                try:
                    market_trade(exchange, coin, 'sell', qty, False, leverage)
                    logger.info(f"{coin_name} is Shorted!")
                    in_position=True
                    f = open("db.txt", "w")
                    msg = "True,"+str(qty)
                    f.write(msg)
                    f.close()
                except Exception as e:
                    logger.info(f"Could not Place order due to ",e)
            else:
                logger.info(f"Can't Short.... Balance = {balance}")
        if buy and in_position:
            logger.info(f"Received Close Short Signal for {coin_name}... Trying to Close")
            try:
                market_trade(exchange, coin, 'buy', qty, True, leverage)
                in_position = False
                qty =0
                f = open("db.txt", "w")
                msg = "False,0"
                f.write(msg)
                f.close()
            except Exception as e:
                logger.info(f"Could not Close Short Position due to ",e)
        time.sleep(10)
