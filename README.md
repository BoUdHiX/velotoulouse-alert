:::writing{variant=“standard” id=“48215”}

🚲 VélÔToulouse Telegram Bot

Bot Telegram permettant de surveiller automatiquement les stations VélÔToulouse et d’être alerté lorsqu’il n’y a plus de vélos mécaniques disponibles.

Le bot utilise les API publiques de Toulouse Métropole pour récupérer les données en temps réel et envoie des alertes via Telegram.

Fonctionnalités principales :
	•	Surveillance automatique de stations favorites
	•	Alerte lorsqu’il n’y a plus de vélos mécaniques
	•	Alerte station vide ou pleine
	•	Suggestion de stations proches avec vélos mécaniques
	•	Recherche de la meilleure station autour de soi
	•	Commandes Telegram pour consulter l’état des stations
	•	Utilisation possible avec la géolocalisation Telegram

⸻

📡 APIs utilisées

Données ouvertes de Toulouse Métropole :

Station status
https://api.cyclocity.fr/contracts/toulouse/gbfs/station_status.json

Station information (nom, coordonnées GPS)
https://api.cyclocity.fr/contracts/toulouse/gbfs/v2/station_information.json

⸻

⚙️ Installation

1. Cloner le repository
git clone https://github.com/yourrepo/velotoulouse-bot.git
cd velotoulouse-bot

2. Installer les dépendances
pip install requests

3. Variables d’environnement

Le bot nécessite deux variables :
TOKEN   = Token du bot Telegram
CHAT_ID = ID du chat Telegram

4. Lancer le bot
python bot.py

Le script vérifie les stations toutes les 30 à 60 secondes.

🚨 Surveillance automatique

Les stations surveillées sont définies dans :
WATCHED_STATIONS

Exemple :
338 → GUILLAUMET - CEAT
402 → GRYNFOGEL - GAILLARDIE

Le bot envoie une alerte lorsqu’un changement d’état est détecté :
	•	🚨 Station vide
	•	🚨 Station pleine
	•	⚠️ Aucun vélo mécanique
	•	⚠️ Peu de vélos mécaniques

Lorsque la situation redevient normale, un message Station redevenue OK est envoyé.

⸻

🤖 Commandes Telegram

/status

Affiche l’état actuel des stations surveillées.

Exemple :

🚲 Stations surveillées

🚏 GUILLAUMET - CEAT
🔧 Vélos mécaniques : 2
🚲 Total vélos : 7
🅿️ Places libres : 6

⸻

/guillaumet

Affiche le statut détaillé de la station GUILLAUMET - CEAT.

⸻

/grynfogel

Affiche le statut détaillé de la station GRYNFOGEL - GAILLARDIE.

⸻

/stade

Affiche l’état des stations autour du Stade Toulousain.

Stations surveillées :
	•	STADE TOULOUSAIN
	•	SEPT DENIERS - TROÈNES
	•	RTE DE BLAGNAC - BERNIES
	•	SUISSE - POLITKOVSKAIA

⸻

/near guillaumet

Affiche les stations proches de GUILLAUMET - CEAT avec leurs vélos mécaniques disponibles.

Exemple :

📍 Stations proches GUILLAUMET - CEAT

🚏 BRUNAUD - CEAT : 🔧 10
🚏 CHIRAC - CHAUMIÈRE : 🔧 4
🚏 CHIRAC - HEREDIA : 🔧 2
🚏 BRUNAUD - BAILLAUD : 🔧 1

⸻

/near grynfogel

Affiche les stations proches de GRYNFOGEL - GAILLARDIE.

⸻

/best guillaumet

Trouve la meilleure station autour de GUILLAUMET.

Critères :
	•	présence de vélos mécaniques
	•	distance la plus courte

Exemple :

🏆 Meilleure station proche

🚏 BRUNAUD - CEAT
🔧 8 vélos mécaniques
📏 320 m

⸻

/best grynfogel

Trouve la meilleure station autour de GRYNFOGEL.

⸻

📍 Utilisation avec la géolocalisation Telegram

Il est possible d’envoyer sa position au bot via Telegram.

Le bot calculera automatiquement la station avec vélos mécaniques la plus proche de votre position.

Exemple :

🏆 Meilleure station proche

🚏 CHIRAC - HEREDIA
🔧 6 vélos mécaniques
📏 190 m

⸻

🧠 Architecture du code

load_station_info()

Charge depuis l’API :
	•	nom des stations
	•	coordonnées GPS

⸻

get_all_stations()

Récupère les données en temps réel :
	•	vélos mécaniques disponibles
	•	total vélos
	•	places libres

⸻

check_stations()

Fonction principale de surveillance.

Compare l’état actuel avec l’état précédent pour détecter :
	•	station vide
	•	station pleine
	•	aucun vélo mécanique
	•	faible nombre de vélos mécaniques

Envoie une alerte Telegram si nécessaire.

⸻

send_telegram()

Envoie un message via l’API Telegram.

⸻

command_station()

Affiche les informations d’une station.

⸻

command_stadium()

Affiche les stations autour du stade.

⸻

command_near()

Affiche les stations proches d’une station donnée.

⸻

best_station_from_point()

Calcule la meilleure station à partir d’un point GPS :
	•	calcule la distance entre stations
	•	filtre celles avec vélos mécaniques
	•	retourne la plus proche

⸻

check_commands()

Récupère les commandes Telegram envoyées au bot et exécute les fonctions correspondantes.

⸻

🔁 Boucle principale

Le bot fonctionne avec une boucle :
while True

qui :
	1.	vérifie les stations surveillées
	2.	vérifie les commandes Telegram
	3.	attend quelques secondes

⸻

☁️ Hébergement

Le bot peut être hébergé sur :
	•	Railway
	•	Render
	•	Fly.io
	•	VPS
	•	Raspberry Pi
	•	NAS

⸻

🚀 Idées d’amélioration
	•	Notification avec carte Google Maps
	•	Limiter la recherche aux stations à moins de 500m
	•	Statistiques de disponibilité des stations
	•	Prédiction de disponibilité des vélos
	•	Dashboard web

⸻

📜 Licence

Projet personnel utilisant les données ouvertes de Toulouse Métropole.
:::
