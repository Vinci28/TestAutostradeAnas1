# Importazione delle librerie necessarie per l'applicazione Flask.
# Flask: Framework per la creazione del server web.
# render_template: Per rendere i file HTML.
# request, jsonify: Per gestire le richieste e le risposte JSON delle API.
# redirect, url_for: Per la gestione dei reindirizzamenti URL.
# psycopg2, psycopg2.extras: Driver e utilità per la connessione al database PostgreSQL.
# logging: Per la registrazione di messaggi di stato, avvisi ed errori.
# pandas: Libreria per l'analisi e la manipolazione dei dati, usata per gestire i risultati delle query.
# datetime, timedelta: Per la gestione di date e intervalli di tempo.
# re: Libreria per le espressioni regolari.
from flask import Flask, render_template, request, jsonify, redirect, url_for
import psycopg2
import psycopg2.extras
import logging
import pandas as pd
from datetime import datetime, timedelta
import re

# Inizializza l'applicazione Flask e imposta il percorso per i file statici.
app = Flask(__name__, static_url_path='/static')

# ----------------- #
# CONFIGURAZIONI    #
# ----------------- #

# Configurazione del sistema di logging.
# Imposta il livello di logging su INFO per registrare messaggi informativi, avvisi ed errori.
# Definisce il formato dei messaggi di log, includendo data/ora, livello e messaggio.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configurazione per la connessione al database PostgreSQL.
# Contiene i parametri necessari: nome del DB, utente, password, host e porta.
DB_CONFIG = {
    "dbname": "autostradeanasdb",
    "user": "vinc",
    "password": "1234",
    "host": "localhost",
    "port": 5432
}

# Soglie predefinite per generare gli allarmi.
# 'temperature_min': Sotto questo valore, si genera un allarme di gelo.
# 'windspeed_max': Sopra questo valore (in km/h), si genera un allarme di vento forte.
# 'precipitation_max': Sopra questo valore (in mm), si genera un allarme di pioggia intensa.
ALLARMI_SOGLIE = {
    'temperature_min': 20.0,
    'windspeed_max': 80.0,
    'precipitation_max': 25.0
}

# Lista degli identificativi delle strade gestite dall'applicazione.
ROAD_IDENTIFIERS = ['A90', 'SS51', 'SS675']

# ----------------- #
# FUNZIONI DI UTILITÀ #
# ----------------- #

def get_connection():
    """
    Stabilisce e restituisce una connessione al database.
    In caso di errore di connessione, registra un errore critico e restituisce None.
    """
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        # Registra un errore critico se la connessione al DB fallisce.
        logging.error(f"ERRORE CRITICO DI CONNESSIONE AL DATABASE: {e}")
        return None

def get_table_name(strada, tipo):
    """
    Determina il nome della tabella del database in base all'identificativo della strada e al tipo di dati (es. 'previsionale' o 'storico').
    Normalizza la stringa della strada e restituisce il nome della tabella corrispondente in minuscolo.
    Se la strada o il tipo non sono supportati, restituisce None e registra un avviso.
    """
    if not strada or not tipo: return None

    table_type = tipo

    strada_norm = strada.upper()
    prefix = f"dati_{table_type}_"

    if 'A90' in strada_norm: return f"{prefix}a90"
    if 'SS51' in strada_norm: return f"{prefix}ss51"
    if 'SS675' in strada_norm: return f"{prefix}ss675"

    logging.warning(f"Nessuna tabella trovata per la strada '{strada}' e tipo '{tipo}'")
    return None

def normalize_key(name):
    """
    Normalizza una stringa per usarla come chiave JSON o in un URL.
    Sostituisce caratteri non alfanumerici (eccetto il '+') con stringhe vuote.
    """
    if not name: return ""
    return re.sub(r'[^a-z0-9+]', '', str(name).lower())

# ----------------- #
# ENDPOINT STATICI (PAGINE HTML) #
# ----------------- #

@app.route("/")
def index():
    """Reindirizza la root URL alla pagina previsionale."""
    return redirect(url_for('previsionale'))

@app.route("/storico")
def storico():
    """Rende la pagina HTML per la visualizzazione dei dati storici."""
    return render_template("storico_nuovo.html")

@app.route("/previsionale")
def previsionale():
    """Rende la pagina HTML per la visualizzazione dei dati previsionali."""
    return render_template("previsionale_nuovo.html")

@app.route("/allarmi")
def allarmi_page():
    """Rende la pagina HTML per la visualizzazione degli allarmi."""
    return render_template("allarmi.html")

# ----------------- #
# ENDPOINT API      #
# ----------------- #

@app.route("/api/mappa/previsionale")
def mappa_previsionale():
    """
    API per ottenere i dati meteorologici previsionali per la mappa.
    Filtra i dati in base all'ultima 'downloaded_at' per garantire di avere l'ultimo batch di previsioni.
    Esegue una query per selezionare solo i dati più recenti per ogni 'tratto' e 'time'.
    Converte la velocità del vento da m/s a km/h prima di inviare la risposta.
    """
    strada = request.args.get('strada')
    if not strada: return jsonify({"errore": "Parametro 'strada' richiesto"}), 400

    tabella = get_table_name(strada, 'previsionale')
    if not tabella: return jsonify({"errore": f"Strada non supportata: {strada}"}), 400

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore di connessione al DB"}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Trova il timestamp dell'ultimo download per filtrare i dati più recenti.
            cursor.execute(f"SELECT MAX(downloaded_at) FROM {tabella}")
            max_ts_row = cursor.fetchone()
            if not max_ts_row or not max_ts_row[0]: return jsonify({"times": [], "data": {}})
            max_ts = max_ts_row[0]

            # Definisce un intervallo di 15 minuti prima dell'ultimo download per la query.
            batch_start_ts = max_ts - timedelta(minutes=15)

            # Query SQL che usa una "CTE" (Common Table Expression) `latest_data`
            # per selezionare l'ultimo record per ogni combinazione 'tratto' e 'time',
            # garantendo che si usino solo i dati più recenti.
            query = """
                WITH latest_data AS (
                    SELECT
                        tratto, time, temperature, windspeed, precipitation,
                        ROW_NUMBER() OVER(PARTITION BY tratto, time ORDER BY downloaded_at DESC) as rn
                    FROM {table_name}
                    WHERE downloaded_at BETWEEN %s AND %s
                )
                SELECT tratto, time, temperature, windspeed, precipitation
                FROM latest_data
                WHERE rn = 1 AND time >= %s
                ORDER BY tratto, time;
            """.format(table_name=tabella)

            # Esegue la query con i parametri di tempo.
            cursor.execute(query, (batch_start_ts, max_ts, datetime.now()))
            rows = cursor.fetchall()
            if not rows: return jsonify({"times": [], "data": {}})

            risultati, orari_set = {}, set()
            for row in rows:
                tratto_norm = normalize_key(row['tratto'])
                time_iso = row['time'].isoformat()
                orari_set.add(time_iso)
                if tratto_norm not in risultati: risultati[tratto_norm] = []

                # Converte la velocità del vento da m/s a km/h.
                windspeed_kmh = round(row['windspeed'] * 3.6, 2) if row['windspeed'] is not None else None

                risultati[tratto_norm].append({
                    "time": time_iso, "temperature": row['temperature'],
                    "windspeed": windspeed_kmh, "precipitation": row['precipitation'],
                    "tratto_originale": row['tratto']
                })

            logging.info(
                f"Caricati dati per {len(risultati)} tratti e {len(orari_set)} timestamps per la strada {strada}")
            return jsonify({
                "times": sorted(list(orari_set)),
                "data": risultati,
                "last_update_timestamp": max_ts.isoformat() if max_ts else None
            })

    except Exception as e:
        logging.error(f"Errore in mappa_previsionale: {e}", exc_info=True)
        return jsonify({"errore": "Errore interno del server"}), 500
    finally:
        if conn: conn.close()

@app.route("/api/allarmi")
def api_allarmi():
    """
    Endpoint per recuperare gli allarmi basati sulle soglie predefinite.
    Identifica le condizioni che superano le soglie (es. temperatura bassa, vento forte, pioggia intensa)
    e restituisce una lista di allarmi in formato JSON.
    Converte le soglie e i valori del vento per coerenza (m/s nel DB, km/h nelle risposte).
    """
    strada = request.args.get('strada')
    if not strada: return jsonify({"errore": "Parametro 'strada' richiesto"}), 400

    tabella = get_table_name(strada, 'previsionale')
    if not tabella: return jsonify([])

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore di connessione al DB"}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            # Trova l'ultimo batch di dati scaricati.
            cursor.execute(f"SELECT MAX(downloaded_at) FROM {tabella}")
            max_ts_row = cursor.fetchone()
            if not max_ts_row or not max_ts_row[0]: return jsonify([])
            max_ts = max_ts_row[0]
            batch_start_ts = max_ts - timedelta(minutes=15)

            # Converte la soglia del vento da km/h a m/s per la query del DB.
            windspeed_threshold_ms = ALLARMI_SOGLIE['windspeed_max'] / 3.6

            # Query per trovare i dati che superano le soglie.
            # Simile alla query di mappa_previsionale ma con clausola WHERE aggiuntiva per i valori di allarme.
            query = """
                WITH latest_data AS (
                    SELECT
                        tratto, time, temperature, windspeed, precipitation,
                        ROW_NUMBER() OVER(PARTITION BY tratto, time ORDER BY downloaded_at DESC) as rn
                    FROM {table_name}
                    WHERE downloaded_at BETWEEN %s AND %s
                )
                SELECT tratto, time, temperature, windspeed, precipitation
                FROM latest_data
                WHERE rn = 1 AND (
                    temperature < %s OR
                    windspeed > %s OR
                    precipitation > %s
                )
                ORDER BY time, tratto;
            """.format(table_name=tabella)

            cursor.execute(query, (
                batch_start_ts, max_ts,
                ALLARMI_SOGLIE['temperature_min'],
                windspeed_threshold_ms,
                ALLARMI_SOGLIE['precipitation_max']
            ))
            rows = cursor.fetchall()

            allarmi_risultanti = []
            for row in rows:
                # Logica per determinare quale tipo di allarme si è verificato.
                if row['temperature'] is not None and row['temperature'] < ALLARMI_SOGLIE['temperature_min']:
                    allarmi_risultanti.append({
                        "tratto": row['tratto'], "time": row['time'].isoformat(), "variabile": "Gelo",
                        "valore": f"{row['temperature']:.1f} °C", "tipo": "gelo"
                    })

                windspeed_kmh = round(row['windspeed'] * 3.6, 1) if row['windspeed'] is not None else None
                if windspeed_kmh is not None and windspeed_kmh > ALLARMI_SOGLIE['windspeed_max']:
                    allarmi_risultanti.append({
                        "tratto": row['tratto'], "time": row['time'].isoformat(), "variabile": "Vento Forte",
                        "valore": f"{windspeed_kmh:.1f} km/h", "tipo": "vento"
                    })

                if row['precipitation'] is not None and row['precipitation'] > ALLARMI_SOGLIE['precipitation_max']:
                    allarmi_risultanti.append({
                        "tratto": row['tratto'], "time": row['time'].isoformat(), "variabile": "Pioggia Intensa",
                        "valore": f"{row['precipitation']:.1f} mm", "tipo": "pioggia"
                    })

            logging.info(f"Trovati {len(allarmi_risultanti)} allarmi per la strada {strada}")
            return jsonify(allarmi_risultanti)

    except Exception as e:
        logging.error(f"Errore in api_allarmi: {e}", exc_info=True)
        return jsonify({"errore": "Errore interno del server"}), 500
    finally:
        if conn: conn.close()

@app.route('/grafico')
def grafico():
    """
    Rende la pagina HTML per visualizzare i grafici dei dati (storici o previsionali) per un singolo tratto.
    La logica varia a seconda del parametro 'modalita'.
    Se 'previsionale', recupera i dati più recenti.
    Se 'storico', rende la pagina e lascia al frontend il compito di recuperare i dati storici tramite un'altra API.
    """
    tratto = request.args.get('tratto')
    modalita = request.args.get('modalita', 'storico')

    if not tratto: return "Parametro 'tratto' mancante.", 400

    tabella = get_table_name(tratto, modalita)
    if not tabella: return f"Configurazione non trovata per il tratto '{tratto}'.", 404

    conn = get_connection()
    if not conn: return "Errore di connessione al database.", 500

    try:
        if modalita == 'previsionale':
            cursor = conn.cursor()
            query_max = f"SELECT MAX(downloaded_at) FROM {tabella} WHERE tratto = %s"
            cursor.execute(query_max, (tratto,))
            ultimo_download = cursor.fetchone()[0]
            cursor.close()

            if not ultimo_download:
                return "Nessun dato previsionale disponibile per questo tratto.", 404

            # Seleziona i dati previsionali per l'ultimo download.
            query_dati = f"SELECT time, temperature, precipitation, windspeed, precipitation_probability FROM {tabella} WHERE tratto = %s AND downloaded_at = %s AND time >= %s ORDER BY time"
            # Usa pandas per leggere i dati direttamente in un DataFrame.
            df = pd.read_sql(query_dati, conn, params=(tratto, ultimo_download, datetime.now()))

            # Rende la pagina del grafico, passando i dati come dizionario.
            return render_template('grafico_previsionale.html', dati=df.to_dict(orient='records'), tratto=tratto,
                                   ultimo_download=ultimo_download.isoformat())

        elif modalita == 'storico':
            # Per i dati storici, il frontend gestirà la richiesta dei dati.
            return render_template('grafico.html', tratto=tratto)
        else:
            return "Modalità non valida.", 400
    except Exception as e:
        logging.error(f"Errore in /grafico: {e}", exc_info=True)
        return "Errore interno del server.", 500
    finally:
        if conn: conn.close()

@app.route('/api/dati_tratto')
def dati_tratto():
    """
    API per recuperare i dati storici per un tratto specifico, con un'opzione di filtro per intervallo di date.
    Usa la libreria pandas per leggere i dati dal DB e convertirli in formato JSON.
    """
    tratto = request.args.get('tratto')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not tratto: return jsonify({"errore": "Parametro 'tratto' mancante"}), 400
    tabella = get_table_name(tratto, 'storico')
    if not tabella: return jsonify({"errore": f"Autostrada non riconosciuta: {tratto}"}), 400

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore connessione DB"}), 500
    try:
        # Costruisce la query in modo dinamico per includere il filtro per data, se specificato.
        query = f"SELECT time, temperature, precipitation, windspeed, precipitation_probability FROM {tabella} WHERE tratto = %s"
        params = [tratto]

        if start_date_str and end_date_str:
            query += " AND time::date BETWEEN %s AND %s"
            params.extend([start_date_str, end_date_str])

        query += " ORDER BY time"

        # Legge i dati dal DB e li restituisce come JSON.
        df = pd.read_sql(query, conn, params=params)
        return df.to_json(orient='records', date_format='iso')
    except Exception as e:
        logging.error(f"Errore in /api/dati_tratto: {e}", exc_info=True)
        return jsonify({"errore": "Errore recupero dati storici"}), 500
    finally:
        if conn: conn.close()

@app.route('/api/data_range')
def data_range():
    """
    API per ottenere l'intervallo di date minimo e massimo dei dati storici disponibili per un tratto.
    Utile per configurare i selettori di data nell'interfaccia utente.
    """
    tratto = request.args.get('tratto')
    if not tratto:
        return jsonify({"errore": "Parametro 'tratto' mancante"}), 400

    tabella = get_table_name(tratto, 'storico')
    if not tabella:
        return jsonify({"errore": "Impossibile determinare la tabella per il tratto"}), 400

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore connessione DB"}), 500

    try:
        with conn.cursor() as cursor:
            # Esegue una query per ottenere la data minima e massima.
            query = f"SELECT MIN(time), MAX(time) FROM {tabella}"
            cursor.execute(query)
            min_date, max_date = cursor.fetchone()

            if min_date and max_date:
                # Restituisce le date formattate come stringhe.
                return jsonify({
                    "start_date": min_date.strftime('%Y-%m-%d'),
                    "end_date": max_date.strftime('%Y-%m-%d')
                })
            else:
                return jsonify({"start_date": None, "end_date": None})
    except Exception as e:
        logging.error(f"Errore in /api/data_range: {e}", exc_info=True)
        return jsonify({"errore": "Errore interno durante il recupero dell'intervallo date"}), 500
    finally:
        if conn: conn.close()

# ----------------- #
# API PER IL POLLING #
# ----------------- #

@app.route('/api/check_update')
def check_update():
    """
    API per controllare l'ultimo timestamp di aggiornamento per un tratto specifico.
    Utilizzata per il "polling" da parte del frontend, consentendo di aggiornare i dati senza ricaricare l'intera pagina.
    """
    tratto = request.args.get('tratto')
    if not tratto:
        return jsonify({"errore": "Parametro 'tratto' mancante"}), 400

    tabella = get_table_name(tratto, 'previsionale')
    if not tabella:
        return jsonify({"errore": f"Configurazione non trovata per il tratto: {tratto}"}), 404
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = f"SELECT MAX(downloaded_at) FROM {tabella} WHERE tratto = %s"
        cursor.execute(query, (tratto,))
        latest_update = cursor.fetchone()[0]
        if latest_update:
            # Restituisce il timestamp in formato ISO 8601, standard per JS.
            return jsonify({"latest_update": latest_update.isoformat()})
        else:
            # Nessun dato trovato per questo tratto.
            return jsonify({"latest_update": None})
    except Exception as e:
        logging.error(f"💥 Errore in /api/check_update: {str(e)}", exc_info=True)
        return jsonify({"errore": "Errore interno durante il controllo degli aggiornamenti"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/api/check_update_mappa')
def check_update_mappa():
    """
    Endpoint leggero per il polling. Controlla il timestamp dell'ultimo set di dati scaricato
    per una data strada. È simile a `check_update`, ma opera sull'intera strada, non su un singolo tratto.
    """
    strada = request.args.get('strada')
    if not strada:
        return jsonify({"errore": "Parametro 'strada' mancante"}), 400

    tabella = get_table_name(strada, 'previsionale')
    if not tabella:
        return jsonify({"errore": f"Configurazione non trovata per la strada: {strada}"}), 404

    conn = None
    try:
        conn = get_connection()
        if not conn: return jsonify({"errore": "Errore di connessione al DB"}), 500

        with conn.cursor() as cursor:
            # Trova l'ultimo timestamp di download per l'intera tabella.
            query = f"SELECT MAX(downloaded_at) FROM {tabella}"
            cursor.execute(query)
            latest_update = cursor.fetchone()[0]

            if latest_update:
                return jsonify({"latest_update": latest_update.isoformat()})
            else:
                # Nessun dato trovato per questa strada.
                return jsonify({"latest_update": None})

    except Exception as e:
        logging.error(f"Errore in /api/check_update_mappa: {e}", exc_info=True)
        return jsonify({"errore": "Errore interno durante il controllo degli aggiornamenti"}), 500
    finally:
        if conn:
            conn.close()

# ----------------- #
# ESECUZIONE DELL'APP #
# ----------------- #

if __name__ == '__main__':
    # Avvia il server web di Flask. 'debug=True' abilita il ricaricamento automatico
    # e la visualizzazione degli errori dettagliati per lo sviluppo.
    app.run(debug=True, port=5000)