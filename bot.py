import requests
import time
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import socket
import json

TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

API_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json"
INFO_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_information.json"

WATCHED_STATIONS = {
    "338": "GUILLAUMET - CEAT",
    "402": "GRYNFOGEL - GAILLARDIE"
}

NEARBY_STATIONS = {
    "338": ["408", "177", "212", "337", "178", "179"],
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


# ---------------------------
# Config persistante
# ---------------------------

CONFIG_FILE = "config.json"
BIKE_TYPE = "mechanical"


def load_config():
    global BIKE_TYPE

    if not os.path.exists(CONFIG_FILE):
        save_config()
        return

    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
        BIKE_TYPE = data.get("bike_type", "mechanical")


def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({"bike_type": BIKE_TYPE}, f)
        log("config.json créé ou mis à jour")

def log(msg):
    print(f"[BOT] {msg}", flush=True)

# ---------------------------
# Fonction utilitaire type vélo
# ---------------------------

def bike_label():

    if BIKE_TYPE == "mechanical":
        return "Vélos mécaniques"

    if BIKE_TYPE == "electrical":
        return "Vélos électriques"

    return "Vélos"

# ---------------------------
# Icone
# ---------------------------

def bike_icon():

    if BIKE_TYPE == "mechanical":
        return "🔧"

    if BIKE_TYPE == "electrical":
        return "⚡"

    return "🚲"

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
# Fonction demande position
# ---------------------------

def request_location():

    keyboard = {
        "keyboard": [
            [
                {
                    "text": "📍 Envoyer ma position",
                    "request_location": True
                }
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

    send_telegram(
        "🏆 Trouver la meilleure station\n\n"
        "Appuie sur le bouton pour envoyer ta position.",
        keyboard
    )

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
        electrical = 0

        for v in station.get("vehicle_types_available", []):

            if v["vehicle_type_id"] == "mechanical":
                mechanical = v["count"]

            if v["vehicle_type_id"] == "electrical":
                electrical = v["count"]

        if BIKE_TYPE == "mechanical":
            bikes = mechanical

        elif BIKE_TYPE == "electrical":
            bikes = electrical

        else:
            bikes = mechanical + electrical

        stations[sid] = {
            "name": STATION_NAMES.get(sid, ""),
            "mechanical": mechanical,
            "electrical": electrical,
            "bikes": bikes,
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

    label = bike_label()

    return (
        f"🚏 {name}\n\n"
        f"🔧 {label} : {data['bikes']}\n"
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

        if s["bikes"] > 0:

            nearby_list.append((s["bikes"], nid))

    if not nearby_list:
        return f"\n⚠️ Aucune station proche avec {bike_label()}."

    nearby_list.sort(reverse=True)

    msg = "\n-------------------------------------------------------------\n"
    msg += f"📍 Stations proches avec {bike_label()} :\n\n"

    for mech, sid2 in nearby_list:

        name = STATION_NAMES.get(sid2, sid2)
        link = maps_link(sid2)

        msg += f"🚏 <a href='{link}'>{name}</a> : 🔧 {mech}\n"

    return msg

# ---------------------------
# Fonction Stade Toulousain 
# ---------------------------

def command_stadium():

    stations = get_all_stations()

    msg = "🏉 Stations autour du stade ❤️🖤\n\n"

    for sid, name in STADIUM_STATIONS.items():

        if sid not in stations:
            continue

        data = stations[sid]

        msg += (
            f"🚏 {name}\n"
            f"{bike_icon()} {bike_label()} : {data['bikes']} | "
            f"🚲 Total : {data['total']} | "
            f"🅿️ Places : {data['docks']}\n\n"
        )

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
        f"🔧 {bike_label()} : {data['bikes']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )

    if data["bikes"] == 0:
        msg += format_nearby(sid, stations)

    return msg


def format_ok(name, data):

    return (
        f"✅ Station redevenue OK\n\n"
        f"🚏 {name}\n"
        f"🔧 {data['bikes']} {bike_label()} disponibles"
    )


# ---------------------------
# Meilleure station
# ---------------------------

def best_station_from_point(lat, lon):

    stations = get_all_stations()

    candidates = []

    for sid, data in stations.items():

        if data["bikes"] == 0:
            continue

        if sid not in STATION_COORDS:
            continue

        slat, slon = STATION_COORDS[sid]

        dist = distance(lat, lon, slat, slon)

        candidates.append((dist, sid, data["bikes"]))

    if not candidates:
        return f"Aucune station avec {bike_label()}."

    candidates.sort()

    dist, sid, mech = candidates[0]

    name = STATION_NAMES[sid]
    lat2, lon2 = STATION_COORDS[sid]

    msg = (
        f"🏆 Meilleure station proche\n\n"
        f"🚏 <a href='{maps_link(sid)}'>{name}</a>\n"
        f"🔧 {mech} {bike_label()}\n"
        f"📏 {round(dist*1000)} m"
    )

    send_location(lat2, lon2)

    return msg


def command_best_station(sid):

    lat, lon = STATION_COORDS[sid]

    return best_station_from_point(lat, lon)

# ---------------------------
# Commande Type
# ---------------------------

def command_type():

    keyboard = {
        "inline_keyboard": [
            [{"text": "🔧 Mécanique", "callback_data": "type_mechanical"}],
            [{"text": "⚡ Électrique", "callback_data": "type_electrical"}],
            [{"text": "🚲 Les deux", "callback_data": "type_both"}]
        ]
    }

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": "🚲 Choisis le type de vélos utilisé par le bot :",
        "reply_markup": keyboard
    })

# ---------------------------
# Mode du bot actuel
# ---------------------------

def command_mode():

    send_telegram(
        f"⚙️ Mode actuel du bot\n\n"
        f"{bike_icon()} {bike_label()}"
    )

# ---------------------------
# Gestion des boutons
# ---------------------------

def handle_callback(callback):

    global BIKE_TYPE

    data = callback["data"]

    # -------- MENU --------

    if data == "menu_status":

        stations = get_all_stations()

        msg = "🎯 Stations surveillées\n\n"

        for sid, name in WATCHED_STATIONS.items():

            if sid not in stations:
                continue

            msg += format_station(name, stations[sid]) + "\n\n"

        send_telegram(msg)


    elif data == "menu_best":
    request_location()


    elif data == "menu_guillaumet":

        send_telegram(command_station("338", "GUILLAUMET - CEAT"))


    elif data == "menu_grynfogel":

        send_telegram(command_station("402", "GRYNFOGEL - GAILLARDIE"))


    elif data == "menu_near_guillaumet":

        send_telegram(command_near("338"))


    elif data == "menu_near_grynfogel":

        send_telegram(command_near("402"))


    elif data == "menu_stade":

        send_telegram(command_stadium())


    elif data == "menu_mode":

        command_mode()


    elif data == "menu_type":

        command_type()


    # -------- TYPE VELO --------

    elif data == "type_mechanical":

        BIKE_TYPE = "mechanical"
        save_config()
        command_menu()

    elif data == "type_electrical":

        BIKE_TYPE = "electrical"
        save_config()
        command_menu()

    elif data == "type_both":

        BIKE_TYPE = "both"
        save_config()
        command_menu()

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
        f"🔧 {bike_label()} : {data['bikes']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )

    if data["bikes"] == 0:
        msg += format_nearby(sid, stations)

    return msg

def command_near(sid):

    stations = get_all_stations()

    if sid not in NEARBY_STATIONS:
        return "Aucune station proche configurée"

    station_name = STATION_NAMES.get(sid, sid)

    msg = f"📍 Stations proches {station_name} avec {bike_label()}\n\n"

    nearby_list = []

    for nid in NEARBY_STATIONS[sid]:

        if nid not in stations:
            continue

        s = stations[nid]

        nearby_list.append((s["bikes"], nid))

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
        bikes = data["bikes"]

        state = "OK"

        if bikes == 0:
            state = "NO_MECH"

        if sid not in last_alert_state:

            last_alert_state[sid] = {"state": state, "bikes": bikes}
            send_telegram(format_alert(sid, name, data, stations))
            continue

        last = last_alert_state[sid]

        if state != last["state"] or bikes != last["bikes"]:

            if state == "OK":
                send_telegram(format_ok(name, data))
            else:
                send_telegram(format_alert(sid, name, data, stations))

            last_alert_state[sid] = {"state": state, "bikes": bikes}

# ---------------------------
# Menu des commandes Telegram
# ---------------------------

def command_menu():

    keyboard = {
    "inline_keyboard": [

        [
            {"text": "📊 Status", "callback_data": "menu_status"},
            {"text": "🏆 Meilleure station", "callback_data": "menu_best"}
        ],

        [
            {"text": "🚏 Guillaumet", "callback_data": "menu_guillaumet"},
            {"text": "🚏 Grynfogel", "callback_data": "menu_grynfogel"}
        ],

        [
            {"text": "📍 Near Guillaumet", "callback_data": "menu_near_guillaumet"},
            {"text": "📍 Near Grynfogel", "callback_data": "menu_near_grynfogel"}
        ],

        [
            {"text": "🏉 Stade Toulousain", "callback_data": "menu_stade"}
        ],

        [
            {"text": "⚙️ Mode", "callback_data": "menu_mode"},
            {"text": "⚙️ Type", "callback_data": "menu_type"}
        ]

    ]
}

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    msg = (
        "🚲 <b>Menu du bot vélos Toulouse</b>\n\n"
        f"⚙️ Mode actuel : {bike_icon()} {bike_label()}"
    )

    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": keyboard
    })

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

        if "callback_query" in update:

            handle_callback(update["callback_query"])
            continue

        if "message" not in update:
            continue

        message = update["message"]

        if "location" in message:

            lat = message["location"]["latitude"]
            lon = message["location"]["longitude"]

            send_telegram(best_station_from_point(lat, lon))

            # supprimer le clavier "envoyer position"
            keyboard = {"remove_keyboard": True}
            send_telegram("📍 Position reçue", keyboard)

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

        elif text == "/menu":

            command_menu()

        elif text == "/type":

            command_type()
        
        elif text == "/mode":

            command_mode()

        elif text == "/guillaumet":

            send_telegram(command_station("338", "GUILLAUMET - CEAT"))

        elif text == "/grynfogel":

            send_telegram(command_station("402", "GRYNFOGEL - GAILLARDIE"))

        elif text == "/near guillaumet":

            send_telegram(command_near("338"))

        elif text == "/near grynfogel":

            send_telegram(command_near("402"))

        elif text == "/stade":

            send_telegram(command_stadium())

        elif text == "/best":
            request_location()

        elif text == "/best guillaumet":

            send_telegram(command_best_station("338"))

        elif text == "/best grynfogel":

            send_telegram(command_best_station("402"))


# ---------------------------
# Initialisation
# ---------------------------

STATION_NAMES, STATION_COORDS = load_station_info()
load_config()

log(f"Bot démarré sur {socket.gethostname()}")

while True:

    try:

        check_stations()
        check_commands()

    except Exception as e:

        log(f"Erreur : {e}")

    time.sleep(30)