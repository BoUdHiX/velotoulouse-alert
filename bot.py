import requests
import time
import os
from datetime import datetime

TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

API_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/v2/station_status.json"

STATIONS = {
    "338": "GUILLAUMET - CEAT",
    "402": "GRYNFOGEL - GAILLARDIE"
}

last_state = {}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    requests.post(url, json=payload)

def get_mechanical_count(station):
    for v in station["vehicle_types_available"]:
        if v["vehicle_type_id"] == "mechanical":
            return v["count"]
    return 0

def compute_state(station):

    mechanical = get_mechanical_count(station)
    vehicles = station["num_vehicles_available"]
    docks = station["num_docks_available"]

    if vehicles == 0:
        return "EMPTY"

    if docks == 0:
        return "FULL"

    if mechanical == 0:
        return "NO_MECH"

    if mechanical < 2:
        return "LOW_MECH"

    return "OK"

def message_for_state(name, state, mechanical, vehicles, docks):

    heure = datetime.now().strftime("%Hh%M")

    if state == "EMPTY":
        alert = "⚠️ Station vide"

    elif state == "FULL":
        alert = "⚠️ Station pleine"

    elif state == "NO_MECH":
        alert = "⚠️ Plus de vélos mécaniques"

    elif state == "LOW_MECH":
        alert = f"⚠️ Seulement {mechanical} vélo mécanique"

    else:
        alert = "✅ Situation normale"

    message = (
        f"🕓 {heure}\n"
        f"🚲 {name}\n"
        f"{alert}\n"
        f"🚲 Vélos mécaniques : {mechanical}\n"
        f"🚲 Total vélos : {vehicles}\n"
        f"🅿️ Places libres : {docks}"
    )

    return message

def check():

    r = requests.get(API_URL)
    data = r.json()

    for station in data["data"]["stations"]:

        sid = station["station_id"]

        if sid not in STATIONS:
            continue

        name = STATIONS[sid]

        mechanical = get_mechanical_count(station)
        vehicles = station["num_vehicles_available"]
        docks = station["num_docks_available"]

        state = compute_state(station)

        if sid not in last_state:
            last_state[sid] = state
            continue

        if last_state[sid] != state:

            msg = message_for_state(name, state, mechanical, vehicles, docks)

            send_telegram(msg)

            last_state[sid] = state

while True:

    try:
        check()
    except Exception as e:
        print("Erreur:", e)

    time.sleep(60)