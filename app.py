from flask import Flask, render_template, request, jsonify
import psycopg2
import logging
import pandas as pd
from datetime import datetime, timedelta
import re

app = Flask(__name__)

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

# Identificativi delle strade gestite
ROAD_IDENTIFIERS = ['A90', 'SS51', 'SS675']


def get_connection():
    """Stabilisce la connessione al database."""
    return psycopg2.connect(**DB_CONFIG)


def get_table_name(tratto, modalita):
    """
    Determina dinamicamente il nome della tabella in base al tratto e alla modalità.
    Gestisce la differenza tra 'storico' (parametro) e 'storici' (nome tabella).
    """
    if not tratto or not modalita:
        return None

    if modalita == 'storico':
        table_type = 'storici'
    elif modalita == 'previsionale':
        table_type = 'previsionale'
    else:
        logging.error(f"Modalità sconosciuta: '{modalita}'")
        return None

    tratto_upper = tratto.upper()
    for identifier in ROAD_IDENTIFIERS:
        if identifier in tratto_upper:
            road_code = identifier.lower()
            return f"dati_{table_type}_{road_code}"

    logging.warning(f"Nessun identificatore di strada trovato per '{tratto}'")
    return None


# === ENDPOINT STATICI (Invariati) ===
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/punto")
def punto():
    return render_template("previsionale2.html")


@app.route("/storico")
def storico():
    return render_template("storico.html")


@app.route("/previsionale")
def previsionale2():
    return render_template("previsionale2.html")


# === ENDPOINT PER LA RICERCA DEI TRATTI ===
@app.route('/api/tratti')
def search_tratti():
    query_param = request.args.get('search', '').strip()
    strada_param = request.args.get('strada', None)

    if len(query_param) < 2:
        return jsonify([])

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        table_to_search = None
        if strada_param:
            table_to_search = get_table_name(strada_param, 'storico')

        search_term = f"%{query_param}%"

        if table_to_search:
            sql_query = f"SELECT DISTINCT tratto FROM {table_to_search} WHERE tratto ILIKE %s ORDER BY tratto LIMIT 20"
            params = (search_term,)
        else:
            union_queries = [
                f"SELECT DISTINCT tratto FROM {get_table_name(road, 'storico')}" for road in ROAD_IDENTIFIERS
            ]
            full_query = " UNION ".join(union_queries)
            sql_query = f"SELECT tratto FROM ({full_query}) as tutti_i_tratti WHERE tratto ILIKE %s ORDER BY tratto LIMIT 20"
            params = (search_term,)

        cursor.execute(sql_query, params)
        results = [row[0] for row in cursor.fetchall()]
        return jsonify(results)

    except Exception as e:
        logging.error(f"💥 Errore durante la ricerca dei tratti: {str(e)}", exc_info=True)
        return jsonify({"errore": "Errore interno durante la ricerca"}), 500
    finally:
        if conn:
            conn.close()


# === ENDPOINT GRAFICI ===
@app.route('/grafico')
def grafico():
    tratto = request.args.get('tratto')
    # --- MODIFICA QUI ---
    # Rimuoviamo l'accento per una maggiore compatibilità
    modalita = request.args.get('modalita', 'storico')

    if not tratto:
        return "Parametro 'tratto' mancante.", 400

    tabella = get_table_name(tratto, modalita)
    if not tabella:
        logging.error(f"Impossibile determinare la tabella per tratto='{tratto}' e modalità='{modalita}'")
        return f"Configurazione non trovata per il tratto '{tratto}'.", 404

    logging.info(f"Richiesta per tratto '{tratto}' in modalita '{modalita}', tabella '{tabella}'")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if modalita == 'previsionale':
            query_max = f"SELECT MAX(downloaded_at) FROM {tabella} WHERE tratto = %s"
            cursor.execute(query_max, (tratto,))
            ultimo_download = cursor.fetchone()[0]

            if not ultimo_download:
                return "Nessun dato previsionale disponibile per questo tratto.", 404

            query_previsionale = f"SELECT time, temperature, precipitation, windspeed, precipitation_probability FROM {tabella} WHERE tratto = %s AND downloaded_at = %s AND time >= %s ORDER BY time"
            cursor.execute(query_previsionale, (tratto, ultimo_download, ultimo_download))
            rows = cursor.fetchall()
            columns = ['time', 'temperature', 'precipitation', 'windspeed', 'precipitation_probability']
            df = pd.DataFrame(rows, columns=columns)

            return render_template('grafico_previsionale.html', dati=df.to_dict(orient='records'), tratto=tratto,
                                   ultimo_download=ultimo_download)

        elif modalita == 'storico':
            return render_template('grafico.html', tratto=tratto)

        else:
            return "Modalità non valida. Usare 'storico' o 'previsionale'.", 400

    except Exception as e:
        logging.error(f"💥 Errore in /grafico: {str(e)}", exc_info=True)
        return "Si è verificato un errore interno nel server.", 500
    finally:
        if conn:
            conn.close()


# === API PER DATI STORICI ===
@app.route('/api/dati_tratto')
def dati_tratto():
    tratto = request.args.get('tratto')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    logging.info(f"📥 Richiesta dati storici per tratto='{tratto}', start={start_date_str}, end={end_date_str}")

    if not tratto:
        return jsonify({"errore": "Parametro 'tratto' mancante"}), 400

    tabella = get_table_name(tratto, 'storico')
    if not tabella:
        logging.error(f"❌ Impossibile determinare la tabella per il tratto: '{tratto}'")
        return jsonify({"errore": f"Autostrada non riconosciuta per il tratto: {tratto}"}), 400

    logging.info(f"ℹ️ Tabella identificata: '{tabella}' per il tratto '{tratto}'")

    conn = None
    try:
        logging.info("➡️  Tentativo di connessione al database...")
        conn = get_connection()
        cursor = conn.cursor()
        logging.info("✅ Connessione al database stabilita.")

        query = f"SELECT time, temperature, precipitation, windspeed, precipitation_probability FROM {tabella} WHERE tratto = %s"
        params = [tratto]

        if start_date_str and end_date_str:
            start_date = datetime.fromisoformat(start_date_str).strftime('%Y-%m-%d 00:00:00')
            end_date = datetime.fromisoformat(end_date_str).strftime('%Y-%m-%d 23:59:59')
            query += " AND time BETWEEN %s AND %s"
            params.extend([start_date, end_date])

        query += " ORDER BY time"

        logging.info(f"▶️  Esecuzione query sulla tabella '{tabella}'...")
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        logging.info(f"📊 Recuperate {len(rows)} righe.")

        if not rows:
            return jsonify([])

        columns = ['time', 'temperature', 'precipitation', 'windspeed', 'precipitation_probability']
        df = pd.DataFrame(rows, columns=columns)

        return df.to_json(orient='records')

    except psycopg2.errors.UndefinedTable:
        logging.error(f"💥 ERRORE CRITICO: La tabella '{tabella}' non esiste nel database!", exc_info=True)
        return jsonify({"errore": f"Errore del server: la tabella dati '{tabella}' non è stata trovata."}), 500
    except Exception as e:
        logging.error(f"💥 Errore generico in /api/dati_tratto: {str(e)}", exc_info=True)
        return jsonify({"errore": "Si è verificato un errore interno durante il recupero dei dati storici"}), 500
    finally:
        if conn:
            conn.close()
            logging.info("🔌 Connessione al database chiusa.")


if __name__ == '__main__':
    app.run(debug=True, port=5000)