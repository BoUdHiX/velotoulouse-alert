import requests
import time
import os
from datetime import datetime

TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

API_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json"

# Stations surveillées automatiquement
WATCHED_STATIONS = {
    "338": "GUILLAUMET - CEAT",
    "402": "GRYNFOGEL - GAILLARDIE"
}

# Stations autour du stade
STADIUM_STATIONS = {
    "287": "STADE TOULOUSAIN",
    "308": "SEPT DENIERS - TROÈNES",
    "131": "RTE DE BLAGNAC - BERNIES",
    "307": "SUISSE - POLITKOVSKAIA"
}

last_alert_state = {}
last_update_id = None


def log(msg):
    print(f"[BOT] {msg}", flush=True)


def get_all_stations():

    r = requests.get(API_URL, timeout=10)
    data = r.json()

    stations = {}

    for station in data["data"]["stations"]:

        sid = station["station_id"]

        mechanical = 0

        for v in station.get("vehicle_types_available", []):
            if v["vehicle_type_id"] == "mechanical":
                mechanical = v["count"]

        stations[sid] = {
            "mechanical": mechanical,
            "total": station.get("num_bikes_available", 0),
            "docks": station.get("num_docks_available", 0)
        }

    return stations


def send_telegram(message):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    requests.post(url, json=payload)


def format_station(name, data):

    return (
        f"🚏 {name}\n\n"
        f"🔧 Vélos mécaniques : {data['mechanical']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )


def format_alert(name, data):

    now = datetime.now().strftime("%Hh%M")

    return (
        f"🚨 Alerte vélo\n\n"
        f"🕓 {now}\n"
        f"🚏 {name}\n"
        f"🔧 Vélos mécaniques : {data['mechanical']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )


def format_ok(name, data):

    return (
        f"✅ Station redevenue OK\n\n"
        f"🚏 {name}\n"
        f"🔧 {data['mechanical']} vélos mécaniques disponibles"
    )


def check_stations():

    global last_alert_state

    stations = get_all_stations()

    for sid, name in WATCHED_STATIONS.items():

        if sid not in stations:
            continue

        data = stations[sid]

        mechanical = data["mechanical"]
        total = data["total"]
        docks = data["docks"]

        state = "OK"

        if total == 0:
            state = "EMPTY"

        elif docks == 0:
            state = "FULL"

        elif mechanical == 0:
            state = "NO_MECH"

        elif mechanical < 2:
            state = "LOW_MECH"

        if sid not in last_alert_state:
            last_alert_state[sid] = state
            continue

        if last_alert_state[sid] != state:

            if state == "OK":

                send_telegram(format_ok(name, data))

            else:

                send_telegram(format_alert(name, data))

            log(f"Changement détecté {name} -> {state}")

            last_alert_state[sid] = state

            log(f"{name} mécaniques = {mechanical}")


def command_station(sid, name):

    stations = get_all_stations()

    if sid not in stations:
        return "Station non trouvée"

    return format_station(name, stations[sid])


def command_stadium():

    stations = get_all_stations()

    msg = "🏉 Stations autour du stade\n\n"

    for sid, name in STADIUM_STATIONS.items():

        if sid not in stations:
            continue

        data = stations[sid]

        msg += (
            f"🚏 {name}\n"
            f"🔧 mécaniques : {data['mechanical']} | "
            f"🚲 vélos dispos : {data['total']} | "
            f"🅿️ places libres : {data['docks']}\n\n"
        )

    return msg


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

        text = update["message"].get("text", "").lower()

        if text == "/status":

            stations = get_all_stations()

            msg = "🚲 Stations surveillées\n\n"

            for sid, name in WATCHED_STATIONS.items():

                if sid not in stations:
                    continue

                msg += format_station(name, stations[sid]) + "\n\n"

            send_telegram(msg)

        elif text == "/guillaumet":

            send_telegram(command_station("338", "GUILLAUMET - CEAT"))

        elif text == "/grynfogel":

            send_telegram(command_station("402", "GRYNFOGEL - GAILLARDIE"))

        elif text == "/stade":

            send_telegram(command_stadium())


log("Bot démarré")

while True:

    try:

        check_stations()

        check_commands()

    except Exception as e:

        log(f"Erreur : {e}")

    time.sleep(60)