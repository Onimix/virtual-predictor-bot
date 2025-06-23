import json
import logging
import threading
import websocket
from telegram import Update
from telegram.ext import CommandHandler, Updater
from apscheduler.schedulers.background import BackgroundScheduler

# === CONFIGURATION ===
TELEGRAM_BOT_TOKEN = "7643969704:AAEaqJR0La-AifMYlvVuQXj-EtiNhtZdqV0"  # <== Replace this!

# Globals
collected_results = []
ws_connected = False
lock = threading.Lock()

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# WebSocket callbacks
def on_message(ws, message):
    global collected_results
    logger.debug(f"Raw WS message: {message}")

    try:
        # Socket.IO protocol: messages starting with "42" contain events and data
        if message.startswith('42'):
            payload = json.loads(message[2:])
            event = payload[0]
            data = payload[1]

            if event == "vfootball:results":
                with lock:
                    collected_results.append(data)
                logger.info(f"New result collected: {data}")
    except Exception as e:
        logger.error(f"Failed to parse WS message: {e}")

def on_error(ws, error):
    logger.error(f"WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")

def on_open(ws):
    global ws_connected
    ws_connected = True
    logger.info("🟢 Connected to SportyBet WebSocket")
    # Subscribe to virtual football results channel
    ws.send('42["subscribe","vfootball:results"]')

def start_websocket():
    ws = websocket.WebSocketApp(
        "wss://alive-ng.on.sportybet2.com/socket.io/?EIO=3&transport=websocket",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open,
        header={
            "Origin": "https://www.sportybet.com"
        }
    )
    ws.run_forever()

# Telegram commands
def start(update: Update, context):
    update.message.reply_text(
        "JARVIS AI BY ONIMIX TECH:\n"
        "Welcome to SportyBet Virtual Football Predictor Bot!\n"
        "Use /results to see collected results.\n"
        "Use /predict to get predictions (Over 0.5, Over 1.5, First Half Double Chance)."
    )

def results(update: Update, context):
    with lock:
        if not collected_results:
            update.message.reply_text("❌ No results collected yet.")
            return
        # Show last 5 results (formatted)
        last_5 = collected_results[-5:]
    msg = "Last 5 Virtual Football Results:\n"
    for idx, match in enumerate(last_5, 1):
        home = match.get("homeTeam", "N/A")
        away = match.get("awayTeam", "N/A")
        hs = match.get("homeScore", "0")
        as_ = match.get("awayScore", "0")
        ht_hs = match.get("htHomeScore", "0")
        ht_as = match.get("htAwayScore", "0")
        msg += f"{idx}. {home} {hs}-{as_} {away} (HT: {ht_hs}-{ht_as})\n"
    update.message.reply_text(msg)

def predict(update: Update, context):
    with lock:
        if not collected_results:
            update.message.reply_text("❌ No data to predict yet.")
            return
        results_copy = collected_results[:]

    total_matches = len(results_copy)
    over_0_5_count = 0
    over_1_5_count = 0
    first_half_double_chance_count = 0
    first_half_total = 0

    for match in results_copy:
        try:
            hs = int(match.get("homeScore", 0))
            as_ = int(match.get("awayScore", 0))
            ht_hs = int(match.get("htHomeScore", 0))
            ht_as = int(match.get("htAwayScore", 0))

            total_goals = hs + as_
            first_half_goals = ht_hs + ht_as

            if total_goals > 0:
                over_0_5_count += 1
            if total_goals > 1:
                over_1_5_count += 1

            # For first half double chance (home win or draw in HT)
            if ht_hs >= ht_as:
                first_half_double_chance_count += 1
            first_half_total += 1
        except Exception:
            continue

    over_0_5_rate = (over_0_5_count / total_matches) * 100
    over_1_5_rate = (over_1_5_count / total_matches) * 100
    first_half_dc_rate = (first_half_double_chance_count / first_half_total) * 100 if first_half_total > 0 else 0

    msg = (
        f"Prediction stats based on last {total_matches} matches:\n"
        f"Over 0.5 Goals: {over_0_5_rate:.2f}%\n"
        f"Over 1.5 Goals: {over_1_5_rate:.2f}%\n"
        f"First Half Double Chance (Home Win or Draw): {first_half_dc_rate:.2f}%\n\n"
        "Use these stats to guide your betting!"
    )
    update.message.reply_text(msg)

def run_telegram_bot():
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("results", results))
    dp.add_handler(CommandHandler("predict", predict))

    updater.start_polling()
    logger.info("🤖 Telegram bot started and polling...")
    updater.idle()

def main():
    # Start WebSocket in background thread
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    # Start Telegram bot (blocking call)
    run_telegram_bot()

if __name__ == "__main__":
    main()
