import requests
import time
import os
from datetime import datetime

TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

STATION_ID = "338"
STATION_NAME = "GUILLAUMET - CEAT"

API_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json"

last_alert_state = "OK"
last_update_id = None


def log(msg):
    print(f"[BOT] {msg}", flush=True)


def get_station_data():

    r = requests.get(API_URL, timeout=10)
    data = r.json()

    for station in data["data"]["stations"]:

        if station["station_id"] == STATION_ID:

            mechanical = station.get("num_bikes_available_types", {}).get("mechanical", 0)
            total = station.get("num_bikes_available", 0)
            docks = station.get("num_docks_available", 0)

            return mechanical, total, docks

    return None, None, None


def send_telegram(message):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    requests.post(url, data=payload)


def format_alert(mechanical, total, docks):

    now = datetime.now().strftime("%Hh%M")

    return (
        f"🚨 Alerte vélo\n\n"
        f"🕓 {now}\n"
        f"🚲 {STATION_NAME}\n"
        f"⚠️ Seulement {mechanical} vélo mécanique\n\n"
        f"🚲 Vélos mécaniques : {mechanical}\n"
        f"🚲 Total vélos : {total}\n"
        f"🅿️ Places libres : {docks}"
    )


def format_ok(mechanical):

    return (
        f"✅ Station redevenue OK\n\n"
        f"🚲 {STATION_NAME}\n"
        f"🚲 {mechanical} vélos mécaniques disponibles"
    )


def format_status(mechanical, total, docks):

    return (
        f"🚲 {STATION_NAME}\n\n"
        f"🚲 Vélos mécaniques : {mechanical}\n"
        f"🚲 Total vélos : {total}\n"
        f"🅿️ Places libres : {docks}"
    )


def check_station():

    global last_alert_state

    mechanical, total, docks = get_station_data()

    if mechanical is None:
        log("Station non trouvée")
        return

    log(f"Station check → mécaniques={mechanical}")

    if mechanical < 2:

        if last_alert_state != "LOW":

            msg = format_alert(mechanical, total, docks)
            send_telegram(msg)

            log("Alerte envoyée")

            last_alert_state = "LOW"

    else:

        if last_alert_state == "LOW":

            msg = format_ok(mechanical)
            send_telegram(msg)

            log("Message retour OK envoyé")

        last_alert_state = "OK"


def check_commands():

    global last_update_id

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"

    params = {}

    if last_update_id:
        params["offset"] = last_update_id + 1

    r = requests.get(url, params=params)
    data = r.json()

    for update in data["result"]:

        last_update_id = update["update_id"]

        if "message" not in update:
            continue

        text = update["message"].get("text", "")
        chat = update["message"]["chat"]["id"]

        if text == "/status":

            mechanical, total, docks = get_station_data()

            msg = format_status(mechanical, total, docks)

            send_telegram(msg)

            log("Commande /status exécutée")


log("Bot démarré")

while True:

    try:

        check_station()

        check_commands()

    except Exception as e:

        log(f"Erreur : {e}")

    time.sleep(60)