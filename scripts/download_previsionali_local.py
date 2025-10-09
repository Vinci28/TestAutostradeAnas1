import requests
import json
import os
import time
import re
import shutil
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
FORECAST_DAYS = 4
MAX_RETRIES = 5
REQUEST_TIMEOUT = 10
INITIAL_DELAY = 5
SLEEP_TIME = 0.5

# Cartella di output dedicata per i previsionali
OUTPUT_BASE_FOLDER = "./download_previsionali"


def pulisci_cartella_previsionali():
    """Cancella tutto il contenuto della cartella download_previsionali"""
    if os.path.exists(OUTPUT_BASE_FOLDER):
        registra_log(f"Pulizia cartella {OUTPUT_BASE_FOLDER}...")
        for filename in os.listdir(OUTPUT_BASE_FOLDER):
            file_path = os.path.join(OUTPUT_BASE_FOLDER, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                registra_log(f"Rimosso: {filename}")
            except Exception as e:
                registra_log(f"Errore durante la cancellazione di {file_path}: {e}", is_error=True)
        registra_log("Pulizia cartella completata")
    else:
        registra_log(f"Cartella {OUTPUT_BASE_FOLDER} non esistente, verrà creata")
        os.makedirs(OUTPUT_BASE_FOLDER, exist_ok=True)


def registra_log(messaggio, is_error=False):
    """Stampa un messaggio a console con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix = "❌ " if is_error else "✅ "
    print(f"[{timestamp}] {prefix}{messaggio}")


def download_data(params, nome_punto_completo, strada_nome, lat, lon, is_storico=False):
    """
    Funzione per scaricare i dati da meteoblue.
    Include la logica per salvare il file in una sottocartella basata sulla strada.
    Ritorna True se il download ha avuto successo, False altrimenti.
    """
    url = f"{BASE_URL}?{params}&lat={lat}&lon={lon}&apikey={API_KEY}"

    # --- DEFINIZIONE SOTTOCARTELLA ---
    # Crea il percorso completo, includendo la sottocartella della strada
    output_subdir = os.path.join(OUTPUT_BASE_FOLDER, strada_nome)
    # --- FINE DEFINIZIONE SOTTOCARTELLA ---

    for attempt in range(MAX_RETRIES):
        try:
            registra_log(
                f"Tentativo {attempt + 1}/{MAX_RETRIES}: Download per {nome_punto_completo} in /{strada_nome}...")
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

                # --- SALVATAGGIO CON SOTTOCARTELLA ---
                # Assicura che la sottocartella esista
                os.makedirs(output_subdir, exist_ok=True)
                # Crea il percorso completo del file
                file_path = os.path.join(output_subdir, filename)

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(response_data, f, indent=2)

                registra_log(f"✅ Successo! Salvato come {strada_nome}/{filename}")
                # --- FINE SALVATAGGIO CON SOTTOCARTELLA ---

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
    registra_log(f"Avvio download dati meteo PREVISIONALI per {data_download_run.strftime('%Y-%m-%d %H:%M')}")

    # NUOVA FUNZIONALITÀ: Pulisce la cartella prima di iniziare il download
    pulisci_cartella_previsionali()

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

            # Parametri specifici per i previsionali
            params = f"forecast_days={FORECAST_DAYS}&params=temperature_max,temperature_min,windspeed_max,windspeed_min,winddirection_max,winddirection_min,felttemperature_max,felttemperature_min,precipitation_probability,uvindex,rainspot,predictability,predictability_class"

            # Passa il nome della strada alla funzione download_data
            if download_data(params, nome_punto_completo, strada, lat, lon):
                downloaded_count += 1

    registra_log(f"*** Elaborazione completata: Scaricati {downloaded_count} file su {total_points} ***")


if __name__ == "__main__":
    main_download()