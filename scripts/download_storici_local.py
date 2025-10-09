import requests
import json
import os
import time
import re
from datetime import datetime

# --- CONFIGURAZIONE E SETUP ---

# Carica l'API Key, URL di base da config.json
try:
    with open("config.json", "r") as f:
        config = json.load(f)
    API_KEY = config["api_key"]
    BASE_URL = config["base_url"]
except FileNotFoundError:
    print("ERRORE: File 'config.json' non trovato.")
    exit()

# Carica le nuove coordinate da punti_per_strada.json
try:
    with open("D:\PycharmProjects\Dimostratore - Copy\static\punti_per_strada.json", "r") as f:
        PUNTI_PER_STRADA = json.load(f)
except FileNotFoundError:
    print("ERRORE: File 'punti_per_strada.json' non trovato.")
    exit()

# Parametri di default (per la robustezza della chiamata API)
FORECAST_DAYS = 1
MAX_RETRIES = 5
REQUEST_TIMEOUT = 10
INITIAL_DELAY = 5
SLEEP_TIME = 0.5

# Cartella di output dedicata per i dati storici
OUTPUT_BASE_FOLDER = "./download_storici"


def registra_log(messaggio, is_error=False):
    """Stampa un messaggio a console con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "❌ " if is_error else "✅ "
    print(f"[{timestamp}] {prefix}{messaggio}")


def download_data(params, nome_punto_completo, strada_nome, lat, lon, data_odierna):
    """
    Funzione per scaricare i dati da meteoblue.
    Include la logica per salvare il file in una sottocartella basata sulla data e sulla strada.
    Ritorna True se il download ha avuto successo, False altrimenti.
    """
    url = f"{BASE_URL}?{params}&lat={lat}&lon={lon}&apikey={API_KEY}"

    # --- NUOVA STRUTTURA CARTELLE ---
    # Crea il percorso completo: download_storici/data_odierna/strada_nome
    output_subdir = os.path.join(OUTPUT_BASE_FOLDER, data_odierna, strada_nome)
    # --- FINE NUOVA STRUTTURA CARTELLE ---

    for attempt in range(MAX_RETRIES):
        try:
            registra_log(
                f"Tentativo {attempt + 1}/{MAX_RETRIES}: Download per {nome_punto_completo} in /{data_odierna}/{strada_nome}...")
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()  # Solleva un'eccezione per codici di stato HTTP errati

            if response.status_code == 200:
                response_data = response.json()

                # --- LOGICA DI ESTRAZIONE modelrun_utc ---
                try:
                    modelrun_utc_str = response_data['metadata']['modelrun_utc']
                    modelrun_dt = datetime.strptime(modelrun_utc_str, '%Y-%m-%d %H:%M')
                    timestamp_parte_file = modelrun_dt.strftime('%Y-%m-%d_%H-%M')
                except (KeyError, ValueError, TypeError):
                    registra_log(
                        f"AVVISO: Impossibile estrarre o parsare 'modelrun_utc' da {nome_punto_completo}. Uso l'ora di download.",
                        is_error=True)
                    timestamp_parte_file = datetime.now().strftime('%Y-%m-%d_%H-%M')
                # --- FINE LOGICA DI ESTRAZIONE ---

                # Genera il nome file
                filename = f"{nome_punto_completo}_{timestamp_parte_file}.json"

                # --- SALVATAGGIO CON NUOVA STRUTTURA CARTELLE ---
                # Assicura che la sottocartella esista
                os.makedirs(output_subdir, exist_ok=True)
                # Crea il percorso completo del file
                file_path = os.path.join(output_subdir, filename)

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(response_data, f, indent=2)

                registra_log(f"✅ Successo! Salvato come {data_odierna}/{strada_nome}/{filename}")
                # --- FINE SALVATAGGIO CON NUOVA STRUTTURA CARTELLE ---

                time.sleep(SLEEP_TIME)  # Attesa tra i download
                return True

        except requests.exceptions.RequestException as e:
            registra_log(f"❌ Fallito per {nome_punto_completo}: Errore di Rete/HTTP: {str(e)}",
                         is_error=True)
            if attempt < MAX_RETRIES - 1:
                delay = INITIAL_DELAY * (2 ** attempt)
                registra_log(f"Riprovo tra {delay:.1f} secondi...")
                time.sleep(delay)
        except Exception as e:
            registra_log(f"Errore non gestito durante il download per {nome_punto_completo}: {str(e)}", is_error=True)
            break

    registra_log(f"❌ Fallito dopo {MAX_RETRIES} tentativi per {nome_punto_completo}", is_error=True)
    return False


def main_download():
    """Funzione principale per orchestrare il download dei dati."""
    data_download_run = datetime.now()
    registra_log(f"Avvio download dati meteo STORICI per {data_download_run.strftime('%Y-%m-%d %H:%M')}")

    # Ottieni la data di oggi nel formato "YYYY-MM-DD"
    data_odierna = datetime.now().strftime("%Y-%m-%d")
    registra_log(f"Cartella di destinazione: {data_odierna}")

    total_points = sum(len(points) for points in PUNTI_PER_STRADA.values())
    downloaded_count = 0

    for strada, punti in PUNTI_PER_STRADA.items():
        registra_log(f"--- Elaborazione Strada: {strada} ({len(punti)} Punti) ---")
        for punto in punti:
            # nome_punto_abbreviato è ad esempio "A90_1"
            nome_punto_abbreviato = punto["nome"]
            lat = punto["lat"]
            lon = punto["lon"]

            # Ricostruisce il nome completo del punto (es. 'A90_Punto_1')
            match = re.search(r'_(\d+)$', nome_punto_abbreviato)
            if match:
                punto_id = match.group(1)
                nome_punto_completo = f"{strada}_Punto_{punto_id}"
            else:
                nome_punto_completo = nome_punto_abbreviato

            # Parametri specifici per i dati storici
            params = f"forecast_days={FORECAST_DAYS}&params=temperature_max,temperature_min,windspeed_max,windspeed_min,winddirection_max,winddirection_min,felttemperature_max,felttemperature_min,precipitation_probability,uvindex,rainspot,predictability,predictability_class"

            # Passa il nome della strada e la data di oggi alla funzione download_data
            if download_data(params, nome_punto_completo, strada, lat, lon, data_odierna):
                downloaded_count += 1

    registra_log(f"*** Elaborazione completata: Scaricati {downloaded_count} file su {total_points} ***")
    registra_log(f"*** Dati salvati in: {OUTPUT_BASE_FOLDER}/{data_odierna} ***")


if __name__ == "__main__":
    main_download()