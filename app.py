from flask import Flask, render_template, request, jsonify, redirect, url_for
import psycopg2
import psycopg2.extras
import logging
import pandas as pd
from datetime import datetime, timedelta
import re

app = Flask(__name__, static_url_path='/static')

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === CONFIGURAZIONE DB ===
DB_CONFIG = {
    "dbname": "autostradeanasdb",
    "user": "vinc",
    "password": "1234",
    "host": "localhost",
    "port": 5432
}

# === SOGLIE PER ALLARMI ===
ALLARMI_SOGLIE = {
    'temperature_min': 0.0,
    'windspeed_max': 80.0,
    'precipitation_max': 25.0
}

# Identificativi delle strade gestite
ROAD_IDENTIFIERS = ['A90', 'SS51', 'SS675']


def get_connection():
    """Stabilisce la connessione al database."""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except psycopg2.OperationalError as e:
        logging.error(f"ERRORE CRITICO DI CONNESSIONE AL DATABASE: {e}")
        return None


# *** FUNZIONE CORRETTA ***
def get_table_name(strada, tipo):
    """Determina il nome corretto della tabella in MINUSCOLO."""
    if not strada or not tipo: return None

    # Modifica: Rimosso l'aggiunta della 'i'. Ora usa 'storico' e 'previsionale'.
    table_type = tipo

    strada_norm = strada.upper()
    prefix = f"dati_{table_type}_"  # es. dati_previsionale_

    if 'A90' in strada_norm: return f"{prefix}a90"
    if 'SS51' in strada_norm: return f"{prefix}ss51"
    if 'SS675' in strada_norm: return f"{prefix}ss675"

    logging.warning(f"Nessuna tabella trovata per la strada '{strada}' e tipo '{tipo}'")
    return None


def normalize_key(name):
    """Normalizza i nomi dei tratti per usarli come chiavi JSON."""
    if not name: return ""
    return re.sub(r'[^a-z0-9+]', '', str(name).lower())


# === ENDPOINT STATICI (PAGINE HTML) ===
@app.route("/")
def index():
    return redirect(url_for('previsionale'))


@app.route("/storico")
def storico():
    return render_template("storico_nuovo.html")


@app.route("/previsionale")
def previsionale():
    return render_template("previsionale_nuovo.html")


@app.route("/allarmi")
def allarmi_page():
    """Pagina che visualizza gli allarmi per una data strada."""
    return render_template("allarmi.html")


# === ENDPOINT API ===

@app.route("/api/mappa/previsionale")
def mappa_previsionale():
    strada = request.args.get('strada')
    if not strada: return jsonify({"errore": "Parametro 'strada' richiesto"}), 400

    tabella = get_table_name(strada, 'previsionale')
    if not tabella: return jsonify({"errore": f"Strada non supportata: {strada}"}), 400

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore di connessione al DB"}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(f"SELECT MAX(downloaded_at) FROM {tabella}")
            max_ts_row = cursor.fetchone()
            if not max_ts_row or not max_ts_row[0]: return jsonify({"times": [], "data": {}})
            max_ts = max_ts_row[0]

            batch_start_ts = max_ts - timedelta(minutes=15)

            # --- MODIFICA APPLICATA QUI ---
            # Aggiunto "AND time >= %s" per filtrare solo le previsioni future.
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

            # Aggiunto datetime.now() come parametro per il nuovo filtro
            cursor.execute(query, (batch_start_ts, max_ts, datetime.now()))
            rows = cursor.fetchall()
            if not rows: return jsonify({"times": [], "data": {}})

            risultati, orari_set = {}, set()
            for row in rows:
                tratto_norm = normalize_key(row['tratto'])
                time_iso = row['time'].isoformat()
                orari_set.add(time_iso)
                if tratto_norm not in risultati: risultati[tratto_norm] = []

                windspeed_kmh = round(row['windspeed'] * 3.6, 2) if row['windspeed'] is not None else None

                risultati[tratto_norm].append({
                    "time": time_iso, "temperature": row['temperature'],
                    "windspeed": windspeed_kmh, "precipitation": row['precipitation'],
                    "tratto_originale": row['tratto']
                })

            logging.info(
                f"Caricati dati per {len(risultati)} tratti e {len(orari_set)} timestamps per la strada {strada}")
            return jsonify({"times": sorted(list(orari_set)), "data": risultati})

    except Exception as e:
        logging.error(f"Errore in mappa_previsionale: {e}", exc_info=True)
        return jsonify({"errore": "Errore interno del server"}), 500
    finally:
        if conn: conn.close()


@app.route("/api/allarmi")
def api_allarmi():
    strada = request.args.get('strada')
    if not strada: return jsonify({"errore": "Parametro 'strada' richiesto"}), 400

    tabella = get_table_name(strada, 'previsionale')
    if not tabella: return jsonify([])

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore di connessione al DB"}), 500

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(f"SELECT MAX(downloaded_at) FROM {tabella}")
            max_ts_row = cursor.fetchone()
            if not max_ts_row or not max_ts_row[0]: return jsonify([])
            max_ts = max_ts_row[0]
            batch_start_ts = max_ts - timedelta(minutes=15)

            windspeed_threshold_ms = ALLARMI_SOGLIE['windspeed_max'] / 3.6

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

            query_dati = f"SELECT time, temperature, precipitation, windspeed, precipitation_probability FROM {tabella} WHERE tratto = %s AND downloaded_at = %s AND time >= %s ORDER BY time"
            df = pd.read_sql(query_dati, conn, params=(tratto, ultimo_download, datetime.now()))

            return render_template('grafico_previsionale.html', dati=df.to_dict(orient='records'), tratto=tratto,
                                   ultimo_download=ultimo_download.isoformat())

        elif modalita == 'storico':
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
    tratto = request.args.get('tratto')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not tratto: return jsonify({"errore": "Parametro 'tratto' mancante"}), 400
    tabella = get_table_name(tratto, 'storico')
    if not tabella: return jsonify({"errore": f"Autostrada non riconosciuta: {tratto}"}), 400

    conn = get_connection()
    if not conn: return jsonify({"errore": "Errore connessione DB"}), 500
    try:
        query = f"SELECT time, temperature, precipitation, windspeed, precipitation_probability FROM {tabella} WHERE tratto = %s"
        params = [tratto]

        if start_date_str and end_date_str:
            query += " AND time::date BETWEEN %s AND %s"
            params.extend([start_date_str, end_date_str])

        query += " ORDER BY time"

        df = pd.read_sql(query, conn, params=params)
        return df.to_json(orient='records', date_format='iso')
    except Exception as e:
        logging.error(f"Errore in /api/dati_tratto: {e}", exc_info=True)
        return jsonify({"errore": "Errore recupero dati storici"}), 500
    finally:
        if conn: conn.close()


@app.route('/api/data_range')
def data_range():
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
            query = f"SELECT MIN(time), MAX(time) FROM {tabella}"
            cursor.execute(query)
            min_date, max_date = cursor.fetchone()

            if min_date and max_date:
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


if __name__ == '__main__':
    app.run(debug=True, port=5000)