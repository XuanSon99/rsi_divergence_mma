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
    job = context.job
    flag_bullish = True
    flag_bearish = True
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
                flag_bearish = False
                message = (
                    f"🔴 Tín hiệu short cho {symbol} \n RSI phân kỳ giảm trên M5 và M15"
                )
                await context.bot.send_message(CHAT_ID, text=message)

            if bullish_divergence:
                flag_bullish = False
                message = (
                    f"🟢 Tín hiệu long cho {symbol} \n RSI phân kỳ tăng trên M5 và M15"
                )
                await context.bot.send_message(CHAT_ID, text=message)
    except Exception as e:
        print(e)

    # if flag_bullish and flag_bearish:
    #     message = f"Không có tín hiệu nào được tìm thấy!"
    #     await context.bot.send_message(CHAT_ID, text=message)


async def start_checking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Starting bot...")
    # chat_id = update.effective_message.chat_id
    chat_id = CHAT_ID

    if update.effective_message.chat_id != 5333185120: return

    try:
        job_removed = remove_job_if_exists(str(chat_id), context)
        if job_removed:
            text = "Previous checking is stopped!"
            await update.effective_message.reply_text(text)
        time_to_wait = time_to_next_15_minutes()
        if time_to_wait < 0:
            time_to_wait += 3600
        context.job_queue.run_repeating(
            check_conditions_and_send_message,
            interval=900,
            first=time_to_wait,
            chat_id=chat_id,
            name=str(chat_id),
        )

        text = "Checking conditions every 15 minutes..."
        await update.effective_message.reply_text(
            f"{text} Time to wait: {time_to_wait} seconds"
        )
    except (IndexError, ValueError):
        await update.effective_message.reply_text("Checking failed!")


def remove_job_if_exists(name: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


def time_to_next_15_minutes(current_time=None):
    if current_time is None:
        current_time = datetime.datetime.now()

    # Calculate the next 15-minute mark
    next_15_minute = current_time.replace(second=0, microsecond=0) + datetime.timedelta(
        minutes=(15 - current_time.minute % 15)
    )

    # If the current time is already past the next 15-minute mark, add 15 minutes
    if current_time >= next_15_minute:
        next_15_minute += datetime.timedelta(minutes=15)

    time_to_wait = (next_15_minute - current_time).total_seconds()
    return round(time_to_wait)


async def stop_checking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.chat_id != 5333185120: return
    print("Stopping bot...")
    chat_id = update.effective_message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = "Checking stopped!" if job_removed else "You have no active checking."
    await update.effective_message.reply_text(text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    if update.effective_message.chat_id != 5333185120: return

    await update.message.reply_text(
        "Hi! Use /start_checking to start checking conditions every 15 minute."
    )


def main() -> None:
    """Run bot."""
    # Create the Application and pass it your bot's token.
    application = Application.builder().token(TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler(["start", "help"], start))
    application.add_handler(CommandHandler("start_checking", start_checking))
    application.add_handler(CommandHandler("stop_checking", stop_checking))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
