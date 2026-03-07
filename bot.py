import requests
import time
import os
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

def load_station_info():

    r = requests.get(INFO_URL, timeout=10)
    data = r.json()

    names = {}
    coords = {}

    for station in data["data"]["stations"]:

        sid = station["station_id"]
        names[sid] = station["name"]
        coords[sid] = (station["lat"], station["lon"])

    return names

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


def maps_link(station_id):

    lat, lon = STATION_COORDS[station_id]

    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"


def send_location(lat, lon):

    url = f"https://api.telegram.org/bot{TOKEN}/sendLocation"

    payload = {
        "chat_id": CHAT_ID,
        "latitude": lat,
        "longitude": lon
    }

    requests.post(url, json=payload)


def send_telegram(message):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    requests.post(url, json=payload)


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


def best_station_from_point(lat, lon):

    stations = get_all_stations()

    candidates = []

    for sid, data in stations.items():

        if sid not in STATION_COORDS:
            continue

        mechanical = data["mechanical"]

        if mechanical == 0:
            continue

        slat, slon = STATION_COORDS[sid]

        dist = distance(lat, lon, slat, slon)

        candidates.append((dist, mechanical, sid))

    if not candidates:
        return None

    candidates.sort()

    return candidates[0]


def format_station(name, data):

    return (
        f"🚏 {name}\n\n"
        f"🔧 Vélos mécaniques : {data['mechanical']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )


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

    msg = (
        "\n-------------------------------------------------------------\n"
        "📍 Stations proches avec vélos mécaniques :\n\n"
    )

    for mech, nid in nearby_list:

        name = STATION_NAMES.get(nid, nid)
        link = maps_link(nid)

        msg += f"🚏 <a href='{link}'>{name}</a> : 🔧 {mech}\n"

    return msg


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


def command_best_station_from_station(sid):

    lat, lon = STATION_COORDS[sid]

    result = best_station_from_point(lat, lon)

    if not result:
        return "Aucune station avec vélos mécaniques."

    dist, mech, best_sid = result

    name = STATION_NAMES[best_sid]

    link = maps_link(best_sid)

    msg = (
        f"🏆 Meilleure station proche\n\n"
        f"🚏 <a href='{link}'>{name}</a>\n"
        f"🔧 {mech} vélos mécaniques\n"
        f"📏 {round(dist*1000)} m\n"
        f"🧭 <a href='{link}'>Ouvrir l’itinéraire</a>"
    )

    lat_station, lon_station = STATION_COORDS[best_sid]

    send_telegram(msg)
    send_location(lat_station, lon_station)


def command_best_from_user(lat, lon):

    result = best_station_from_point(lat, lon)

    if not result:
        send_telegram("Aucune station avec vélos mécaniques.")
        return

    dist, mech, sid = result

    name = STATION_NAMES[sid]

    link = maps_link(sid)

    msg = (
        f"🏆 Meilleure station proche\n\n"
        f"🚏 <a href='{link}'>{name}</a>\n"
        f"🔧 {mech} vélos mécaniques\n"
        f"📏 {round(dist*1000)} m\n"
        f"🧭 <a href='{link}'>Ouvrir l’itinéraire</a>"
    )

    send_telegram(msg)

    lat_station, lon_station = STATION_COORDS[sid]

    send_location(lat_station, lon_station)


def command_best_station(sid):

    if sid not in STATION_COORDS:
        return "Station inconnue"

    lat, lon = STATION_COORDS[sid]

    return best_station_from_point(lat, lon)
    
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
    
def best_station_from_point(lat, lon):

    stations = get_all_stations()

    candidates = []

    for sid, data in stations.items():

        if sid not in STATION_COORDS:
            continue

        mechanical = data["mechanical"]

        if mechanical == 0:
            continue

        slat, slon = STATION_COORDS[sid]

        dist = distance(lat, lon, slat, slon)

        candidates.append((dist, mechanical, sid))

    if not candidates:
        return "Aucune station avec vélos mécaniques"

    candidates.sort()

    dist, mech, sid = candidates[0]

    name = STATION_NAMES.get(sid, sid)

    return (
        f"🏆 Meilleure station proche\n\n"
        f"🚏 {name}\n"
        f"🔧 {mech} vélos mécaniques\n"
        f"📏 {round(dist*1000)} m"
    )

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

        if text == "/status":

            lat = message["location"]["latitude"]
            lon = message["location"]["longitude"]

            command_best_from_user(lat, lon)
            continue

        text = message.get("text", "").lower()

        if text == "/best guillaumet":

            command_best_station_from_station("338")

        elif text == "/best grynfogel":

            send_telegram(command_near("402"))

# Chargement des noms des stations au demarrage
STATION_NAMES = load_station_names()

log(f"Bot démarré sur {socket.gethostname()}")

while True:

    try:

        check_stations()

        check_commands()
        
        STATION_NAMES, STATION_COORDS = load_station_info()

    except Exception as e:

        log(f"Erreur : {e}")

    time.sleep(30)