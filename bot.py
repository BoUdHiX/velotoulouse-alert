import requests
import matplotlib
matplotlib.use("Agg")
import time
import os
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import socket
import json
import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

# pour communication avec telegram
TOKEN = os.environ["TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

# url data Toulouse Métropole pour veloToulouse
API_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json"
INFO_URL = "https://api.cyclocity.fr/contracts/toulouse/gbfs/station_information.json"

# Fichier historique et chemin db
HISTORY_FILE = "stations_history.csv"
DB_FILE = "/data/stations.db"

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

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {"bike_type": "mechanical"}

    BIKE_TYPE = data.get("bike_type", "mechanical")

    return data

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump({"bike_type": BIKE_TYPE}, f)
        log("config.json créé ou mis à jour")

def log(msg):
    print(f"[BOT] {msg}", flush=True)

# ---------------------------
# Fonction save data pour historique
# ---------------------------

def save_history(sid, data):

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO station_history
        (timestamp, station, bikes_mech, bikes_elec, bikes_total, docks)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        now,
        sid,
        data["mechanical"],
        data["electrical"],
        data["total"],
        data["docks"]
    ))

    conn.commit()
    conn.close()

# ---------------------------
# Generation du graphique stat
# ---------------------------

def generate_day_chart(station_id, station_name):

    conn = sqlite3.connect(DB_FILE)

    query = """
    SELECT timestamp, bikes_mech, bikes_elec, bikes_total, docks
    FROM station_history
    WHERE station = ?
    """

    df = pd.read_sql_query(query, conn, params=(station_id,))
    conn.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    today = df[df["timestamp"].dt.date == datetime.now().date()]

    if today.empty:
        send_telegram("📊 Pas encore assez de données pour aujourd'hui.")
        return None
        
    # choisir la colonne selon le mode
    config = load_config() or {}
    mode = config.get("bike_mode", "mechanical")
    
    if mode == "mechanical":
        column = "bikes_mech"
    
    elif mode == "electrical":
        column = "bikes_elec"
    
    else:
        column = "bikes_total"
        
    plt.figure()

    # vélos
    plt.plot(
        today["timestamp"],
        today[column],
        label=bike_label()
    )

    # places libres
    plt.plot(
        today["timestamp"],
        today["docks"],
        label="Places libres"
    )

    # zone sous la courbe vélos
    plt.fill_between(today["timestamp"], today[column], alpha=0.2)

    # ligne zéro
    plt.axhline(0)
    plt.axvline(datetime.now(), linestyle="--", alpha=0.5)

    plt.title(f"Statistiques - {station_name}")
    plt.xlabel("Heure")
    plt.ylabel("Nombre")

    plt.legend()

    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout(rect=[0,0,1,0.95])

    file = "chart.png"

    plt.savefig(file)
    plt.close()

    return file

# ---------------------------
# Creation base automatique
# ---------------------------

def init_db():

    # créer le dossier /data si il n'existe pas
    os.makedirs("/data", exist_ok=True)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS station_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        station INTEGER,
        bikes_mech INTEGER,
        bikes_elec INTEGER,
        bikes_total INTEGER,
        docks INTEGER
    )
    """)

    conn.commit()
    conn.close()

# ---------------------------
# Envoi du graphique stat sur Telegram
# ---------------------------

def send_photo(path):

    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"

    files = {"photo": open(path, "rb")}

    data = {
        "chat_id": CHAT_ID
    }

    requests.post(url, data=data, files=files)

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

def send_telegram(text, keyboard=None):

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json=payload
    )

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
# Fonction pour stations avec places libres
# ---------------------------

def format_nearby_docks(sid, stations):

    if sid not in NEARBY_STATIONS:
        return ""

    nearby_list = []

    for nid in NEARBY_STATIONS[sid]:

        if nid not in stations:
            continue

        s = stations[nid]

        if s["docks"] > 0:
            nearby_list.append((s["docks"], nid))

    if not nearby_list:
        return "\n⚠️ Aucune station proche avec places libres."

    nearby_list.sort(reverse=True)

    msg = "\n-------------------------------------------------------------\n"
    msg += "📍 Stations proches avec places libres :\n\n"

    for docks, sid2 in nearby_list:

        name = STATION_NAMES.get(sid2, sid2)
        link = maps_link(sid2)

        msg += f"🚏 <a href='{link}'>{name}</a> : 🅿️ {docks}\n"

    return msg

# ---------------------------
# Fonction pour d’alerte station pleine
# ---------------------------

def format_full_alert(sid, name, data, stations):

    now = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Hh%M")

    msg = (
        f"🚨 Station pleine\n\n"
        f"🕓 {now}\n"
        f"🚏 {name}\n"
        f"🚲 Vélos présents : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}\n"
    )

    msg += format_nearby_docks(sid, stations)

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
# fonction pour verif stations home et boulot
# ---------------------------

def check_work_route():

    stations = get_all_stations()

    msg = "🚲 Etat du trajet maison/travail 🔄\n\n"

    # Guillaumet → vélos disponibles
    sid_home = "338"

    if sid_home in stations:

        s = stations[sid_home]

        msg += (
            "🏠 Station Guillaumet\n"
            f"{bike_icon()} {bike_label()} : {s['bikes']}\n"
            f"🚲 Vélos présents : {s['total']}\n"
            f"🅿️ Places libres : {s['docks']}\n"
        )

        if s["bikes"] == 0:
            msg += format_nearby(sid_home, stations)

    # Grynfogel → places libres
    sid_work = "402"

    if sid_work in stations:

        s = stations[sid_work]

        msg += (
            "\n🏢 Station Grynfogel\n"
            f"{bike_icon()} {bike_label()} : {s['bikes']}\n"
            f"🚲 Vélos présents : {s['total']}\n"
            f"🅿️ Places libres : {s['docks']}\n"
        )

        if s["docks"] == 0:
            msg += format_nearby_docks(sid_work, stations)

    send_telegram(msg)


# ---------------------------
# Alerte
# ---------------------------

def format_alert(sid, name, data, stations):

    now = datetime.now(ZoneInfo("Europe/Paris")).strftime("%Hh%M")

    msg = (
        f"🚨 Alerte vélo\n\n"
        f"🕓 {now}\n"
        f"🚏 {name}\n"
        f"{bike_icon()} {bike_label()} : {data['bikes']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )

    if data["bikes"] == 0:
        msg += format_nearby(sid, stations)

    return msg

# ---------------------------
# Retour normal station
# ---------------------------

def format_ok(name, data):

    return (
        f"✅ Station redevenue OK\n\n"
        f"🚏 {name}\n"
        f"{bike_icon()} {data['bikes']} {bike_label()} disponibles"
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
        f"{bike_icon()} {mech} {bike_label()}\n"
        f"📏 {round(dist*1000)} m"
    )

    send_location(lat2, lon2)

    return msg

# ---------------------------
# Coordonnée pour best station
# ---------------------------

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

    msg = (
        f"⚙️ Mode actuel du bot\n\n"
        f"{bike_icon()} {bike_label()}"
    )
    send_telegram(msg)

# ---------------------------
# Reponse callback
# ---------------------------

def answer_callback(callback_id):

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery",
        json={
            "callback_query_id": callback_id
        }
    )

# ---------------------------
# Gestion des boutons
# ---------------------------

def handle_callback(callback):

    answer_callback(callback["id"])
    
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


    elif data == "menu_work":
    
        check_work_route()


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
        f"{bike_icon()} {bike_label()} : {data['bikes']}\n"
        f"🚲 Total vélos disponibles : {data['total']}\n"
        f"🅿️ Places libres : {data['docks']}"
    )

    if data["bikes"] == 0:
        msg += format_nearby(sid, stations)

    return msg
    
# ---------------------------
# Pour commande proche
# ---------------------------

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

        msg += f"🚏 <a href='{link}'>{name}</a> : {bike_icon()} {mech}\n"

    return msg

# ---------------------------
# Verif des stations
# ---------------------------

def check_stations():

    global last_alert_state

    stations = get_all_stations()

    for sid, name in WATCHED_STATIONS.items():

        if sid not in stations:
            continue

        data = stations[sid]
        # Build history Data
        save_history(sid, data)
        bikes = data["bikes"]

        state = "OK"

        if bikes == 0:
            state = "NO_MECH"

        elif data["docks"] == 0:
            state = "FULL"

        if sid not in last_alert_state:

            last_alert_state[sid] = {"state": state, "bikes": bikes}
            send_telegram(format_alert(sid, name, data, stations))
            continue

        last = last_alert_state[sid]

        if state != last["state"] or bikes != last["bikes"]:
        
            if state == "OK":
        
                send_telegram(format_ok(name, data))
        
            elif state == "FULL":
        
                send_telegram(format_full_alert(sid, name, data, stations))
        
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
            {"text": "🏢 Work", "callback_data": "menu_work"}
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

        elif text.startswith("/chart"):
        
            if "guillaumet" in text:
        
                chart = generate_day_chart("338", "GUILLAUMET - CEAT")
        
            elif "grynfogel" in text:
        
                chart = generate_day_chart("402", "GRYNFOGEL - GAILLARDIE")
        
            else:
                send_telegram("❌ Station inconnue")
                continue
        
            if chart:
                send_photo(chart)

        elif text == "/grynfogel":

            send_telegram(command_station("402", "GRYNFOGEL - GAILLARDIE"))

        elif text == "/near guillaumet":

            send_telegram(command_near("338"))

        elif text == "/near grynfogel":

            send_telegram(command_near("402"))

        elif text == "/stade":

            send_telegram(command_stadium())

        elif text == "/work":
        
            send_telegram(
                "🚲 Mode trajet travail activé\n\n"
                " Surveillance actuelle :\n"
                "• vélos disponibles à Guillaumet\n"
                "• places libres à Grynfogel"
            )
        
            check_work_route()

        elif text == "/best":
            request_location()

        elif text == "/best guillaumet":

            send_telegram(command_best_station("338"))

        elif text == "/best grynfogel":

            send_telegram(command_best_station("402"))


# ---------------------------
# Initialisations
# ---------------------------

STATION_NAMES, STATION_COORDS = load_station_info()

init_db()
load_config()
log(f"Bot démarré sur {socket.gethostname()}")

while True:

    try:

        check_stations()
        check_commands()

    except Exception as e:

        log(f"Erreur : {e}")

    time.sleep(30)
