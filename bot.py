import requests
import time
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import socket

TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

API_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json"
INFO_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_information.json"

WATCHED_STATIONS = {
    "338": "GUILLAUMET - CEAT",
    "402": "GRYNFOGEL - GAILLARDIE"
}

NEARBY_STATIONS = {
    "338": ["408", "177", "212", "337"],
    "402": ["387", "276"]
}

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


# ---------------------------
# Charger noms + coordonnées
# ---------------------------

def load_station_info():

    r = requests.get(INFO_URL, timeout=10)
    data = r.json()

    names = {}
    coords = {}

    for station in data["data"]["stations"]:

        sid = station["station_id"]

        names[sid] = station["name"]
        coords[sid] = (station["lat"], station["lon"])

    return names, coords


# ---------------------------
# Distance GPS
# ---------------------------

def distance(lat1, lon1, lat2, lon2):

    R = 6371

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat/2)**2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon/2)**2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


# ---------------------------
# Google Maps navigation
# ---------------------------

def maps_link(station_id):

    lat, lon = STATION_COORDS[station_id]

    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"


# ---------------------------
# Carte Telegram
# ---------------------------

def send_location(lat, lon):

    url = f"https://api.telegram.org/bot{TOKEN}/sendLocation"

    payload = {
        "chat_id": CHAT_ID,
        "latitude": lat,
        "longitude": lon
    }

    requests.post(url, json=payload)


# ---------------------------
# Récupérer stations
# ---------------------------

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
            "name": STATION_NAMES.get(sid, ""),
            "mechanical": mechanical,
            "total": station.get("num_bikes_available", 0),
            "docks": station.get("num_docks_available", 0)
        }

    return stations


# ---------------------------
# Telegram message
# ---------------------------

def send_telegram(message):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    requests.post(url, json=payload)


# ---------------------------
# Station info
# ---------------------------

def format_station(name, data):

    return (
        f"🚏 {name}\n\n"
        f"🔧 Vélos mécaniques : {data['mechanical']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )


# ---------------------------
# Stations proches
# ---------------------------

def format_nearby(sid, stations):

    if sid not in NEARBY_STATIONS:
        return ""

    nearby_list = []

    for nid in NEARBY_STATIONS[sid]:

        if nid not in stations:
            continue

        s = stations[nid]

        if s["mechanical"] > 0:

            nearby_list.append((s["mechanical"], nid))

    if not nearby_list:
        return "\n⚠️ Aucune station proche avec vélo mécanique."

    nearby_list.sort(reverse=True)

    msg = "\n-------------------------------------------------------------\n"
    msg += "📍 Stations proches avec vélos mécaniques :\n\n"

    for mech, sid2 in nearby_list:

        name = STATION_NAMES.get(sid2, sid2)
        link = maps_link(sid2)

        msg += f"🚏 <a href='{link}'>{name}</a> : 🔧 {mech}\n"

    return msg


# ---------------------------
# Alerte
# ---------------------------

def format_alert(sid, name, data, stations):

    now = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Hh%M")

    msg = (
        f"🚨 Alerte vélo\n\n"
        f"🕓 {now}\n"
        f"🚏 {name}\n"
        f"🔧 Vélos mécaniques : {data['mechanical']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )

    if data["mechanical"] == 0:
        msg += format_nearby(sid, stations)

    return msg


def format_ok(name, data):

    return (
        f"✅ Station redevenue OK\n\n"
        f"🚏 {name}\n"
        f"🔧 {data['mechanical']} vélos mécaniques disponibles"
    )


# ---------------------------
# Meilleure station
# ---------------------------

def best_station_from_point(lat, lon):

    stations = get_all_stations()

    candidates = []

    for sid, data in stations.items():

        if data["mechanical"] == 0:
            continue

        if sid not in STATION_COORDS:
            continue

        slat, slon = STATION_COORDS[sid]

        dist = distance(lat, lon, slat, slon)

        candidates.append((dist, sid, data["mechanical"]))

    if not candidates:
        return "Aucune station avec vélos mécaniques."

    candidates.sort()

    dist, sid, mech = candidates[0]

    name = STATION_NAMES[sid]
    lat2, lon2 = STATION_COORDS[sid]

    msg = (
        f"🏆 Meilleure station proche\n\n"
        f"🚏 <a href='{maps_link(sid)}'>{name}</a>\n"
        f"🔧 {mech} vélos mécaniques\n"
        f"📏 {round(dist*1000)} m"
    )

    send_location(lat2, lon2)

    return msg


def command_best_station(sid):

    lat, lon = STATION_COORDS[sid]

    return best_station_from_point(lat, lon)


# ---------------------------
# Vérification stations
# ---------------------------

def command_station(sid, name):

    stations = get_all_stations()

    if sid not in stations:
        return "Station non trouvée"

    data = stations[sid]

    msg = (
        f"🚏 {name}\n\n"
        f"🔧 Vélos mécaniques : {data['mechanical']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )

    if data["mechanical"] == 0:
        msg += format_nearby(sid, stations)

    return msg

def command_near(sid):

    stations = get_all_stations()

    if sid not in NEARBY_STATIONS:
        return "Aucune station proche configurée"

    station_name = STATION_NAMES.get(sid, sid)

    msg = f"📍 Stations proches {station_name} avec vélos mécaniques\n\n"

    nearby_list = []

    for nid in NEARBY_STATIONS[sid]:

        if nid not in stations:
            continue

        s = stations[nid]

        nearby_list.append((s["mechanical"], nid))

    nearby_list.sort(reverse=True)

    for mech, nid in nearby_list:

        name = STATION_NAMES.get(nid, nid)
        link = maps_link(nid)

        msg += f"🚏 <a href='{link}'>{name}</a> : 🔧 {mech}\n"

    return msg

def check_stations():

    global last_alert_state

    stations = get_all_stations()

    for sid, name in WATCHED_STATIONS.items():

        if sid not in stations:
            continue

        data = stations[sid]
        mechanical = data["mechanical"]

        state = "OK"

        if mechanical == 0:
            state = "NO_MECH"

        if sid not in last_alert_state:

            last_alert_state[sid] = {"state": state, "mechanical": mechanical}
            send_telegram(format_alert(sid, name, data, stations))
            continue

        last = last_alert_state[sid]

        if state != last["state"] or mechanical != last["mechanical"]:

            if state == "OK":
                send_telegram(format_ok(name, data))
            else:
                send_telegram(format_alert(sid, name, data, stations))

            last_alert_state[sid] = {"state": state, "mechanical": mechanical}


# ---------------------------
# Commandes Telegram
# ---------------------------

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

        message = update["message"]

        if "location" in message:

            lat = message["location"]["latitude"]
            lon = message["location"]["longitude"]

            send_telegram(best_station_from_point(lat, lon))
            continue

        text = message.get("text", "").lower()

        if text == "/status":

            stations = get_all_stations()

            msg = "🎯 Stations surveillées\n\n"

            for sid, name in WATCHED_STATIONS.items():

                if sid not in stations:
                    continue

                msg += format_station(name, stations[sid]) + "\n\n"

            send_telegram(msg)

        elif text == "/guillaumet":

            send_telegram(command_station("338", "GUILLAUMET - CEAT"))

        elif text == "/grynfogel":

            send_telegram(command_station("402", "GRYNFOGEL - GAILLARDIE"))

        elif text == "/near guillaumet":

            send_telegram(command_near("338"))

        elif text == "/near grynfogel":

            send_telegram(command_near("402"))

        elif text == "/best":

            send_telegram("📍 Envoie ta position Telegram.")

        elif text == "/best guillaumet":

            send_telegram(command_best_station("338"))

        elif text == "/best grynfogel":

            send_telegram(command_best_station("402"))


# ---------------------------
# Initialisation
# ---------------------------

STATION_NAMES, STATION_COORDS = load_station_info()

log(f"Bot démarré sur {socket.gethostname()}")

while True:

    try:

        check_stations()
        check_commands()

    except Exception as e:

        log(f"Erreur : {e}")

    time.sleep(30)