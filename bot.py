import requests
import datetime
import time
import io
import pandas as pd
import threading
from telegram import __version__ as TG_VER
from pytz import timezone
import talib
import asyncio

try:
    from telegram import __version_info__
except ImportError:
    __version_info__ = (0, 0, 0, 0, 0)  # type: ignore[assignment]

if __version_info__ < (20, 0, 0, "alpha", 1):
    raise RuntimeError(
        f"This example is not compatible with your current PTB version {TG_VER}. To view the "
        f"{TG_VER} version of this example, "
        f"visit https://docs.python-telegram-bot.org/en/v{TG_VER}/examples.html"
    )
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Define key
TOKEN = "6473609170:AAGdrtjuCmrxYrJBN1B1jLYJFq_1gxMdpHI"

# TOKEN = "6217705988:AAEOYp5g31rkl-iWrXAGE_mo7t0f0Oz3qIo"

BASE_URL = "https://contract.mexc.com/api/v1"
CHAT_ID = "-1001962645473"

# Define main code


def get_all_future_pairs():
    url = f"{BASE_URL}/contract/detail"
    response = requests.get(url)
    data = response.json()

    if data.get("success", False):
        data = data["data"]
        symbols = [symbol["symbol"] for symbol in data]
        return symbols
    else:
        print("Error: Data retrieval unsuccessful.")
        return None


def get_symbol_data(symbol, interval="Min15"):
    url = f"{BASE_URL}/contract/kline/{symbol}?interval={interval}"
    response = requests.get(url)
    data = response.json()

    if data.get("success", False):
        data = data["data"]
        data_dict = {
            "time": data["time"],
            "open": data["open"],
            "close": data["close"],
            "high": data["high"],
            "low": data["low"],
            "vol": data["vol"],
        }
        df = pd.DataFrame(data_dict)
        df["close"] = df["close"].astype(float)
        return df
    else:
        print("Error: Data retrieval unsuccessful.")
        return None


def find_latest_rsi_bullish_divergence(df, threshold=25, lookback_period=20):
    period = 14  # RSI period
    df["RSI"] = talib.RSI(df["close"].values, timeperiod=period)
    df["RSI"] = df["RSI"].round(2)
    bullish_divergence_detected = False
    latest_close = df["close"].iloc[-2]
    latest_rsi = df["RSI"].iloc[-2]
    detected_index = None

    if latest_rsi <= threshold:
        # Find RSI value 20 bars ago
        if len(df) >= lookback_period:
            rsi_20_bars_ago = df["RSI"].iloc[-lookback_period - 1 :]
            close_20_bars_ago = df["close"].iloc[-lookback_period - 1 :]
        else:
            rsi_20_bars_ago = df["RSI"].iloc[0]
            close_20_bars_ago = df["close"].iloc[0]

        for i in range(len(rsi_20_bars_ago) - 1, 1, -1):
            if latest_close < close_20_bars_ago.iloc[i]:
                if latest_rsi > rsi_20_bars_ago.iloc[i]:
                    bullish_divergence_detected = True
                    detected_index = i
                    break
    return bullish_divergence_detected


def find_latest_rsi_bearish_divergence(df, threshold=75, lookback_period=20):
    period = 14  # RSI period
    df["RSI"] = talib.RSI(df["close"].values, timeperiod=period)
    df["RSI"] = df["RSI"].round(2)
    bearish_divergence_detected = False
    latest_close = df["close"].iloc[-2]
    latest_rsi = df["RSI"].iloc[-2]
    detected_index = None

    if latest_rsi >= threshold:
        # Find RSI value 20 bars ago
        if len(df) >= lookback_period:
            rsi_20_bars_ago = df["RSI"].iloc[-lookback_period - 1 :]
            close_20_bars_ago = df["close"].iloc[-lookback_period - 1 :]
        else:
            rsi_20_bars_ago = df["RSI"].iloc[0]
            close_20_bars_ago = df["close"].iloc[0]

        for i in range(len(rsi_20_bars_ago) - 1, 1, -1):
            if latest_close > close_20_bars_ago.iloc[i]:
                if latest_rsi < rsi_20_bars_ago.iloc[i]:
                    bearish_divergence_detected = True
                    detected_index = i
                    break

    return bearish_divergence_detected


async def check_conditions_and_send_message(context: ContextTypes.DEFAULT_TYPE):
    print("Checking conditions...")

    try:
        tokens_to_check = get_all_future_pairs()
        
        for symbol in tokens_to_check:
            df_m15 = get_symbol_data(symbol)
            df_m5 = get_symbol_data(symbol, interval="Min5")

            bearish_divergence = find_latest_rsi_bearish_divergence(
                df_m15
            ) and find_latest_rsi_bearish_divergence(df_m5)
            bullish_divergence = find_latest_rsi_bullish_divergence(
                df_m15
            ) and find_latest_rsi_bullish_divergence(df_m5)

            if bearish_divergence:
                message = f"🔴 Tín hiệu short cho {symbol} \n RSI phân kỳ giảm trên M5 và M15"
                await context.bot.send_message(CHAT_ID, text=message)

            if bullish_divergence:
                message = f"🟢 Tín hiệu long cho {symbol} \n RSI phân kỳ tăng trên M5 và M15"
                await context.bot.send_message(CHAT_ID, text=message)

    except Exception as e:
        print(e)

    # if flag_bullish and flag_bearish:
    #     message = f"Không có tín hiệu nào được tìm thấy!"
    #     await context.bot.send_message(CHAT_ID, text=message)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    if update.effective_message.chat_id != 5333185120: return

    await update.message.reply_text("Hi")


def main() -> None:
    """Run bot."""
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler(["start", "help"], start))

    job_queue = application.job_queue
    job_queue.run_repeating(check_conditions_and_send_message, interval=300, first=10)

    application.run_polling()


if __name__ == "__main__":
    main()
