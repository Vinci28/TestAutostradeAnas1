from flask import Flask, render_template, request, jsonify, send_from_directory
import psycopg2
import logging
import os
import pandas as pd
from datetime import datetime, timedelta
import re

app = Flask(__name__)

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === CONFIG DB ===
DB_CONFIG = {
    "dbname": "puntiautostrade",
    "user": "vinc",
    "password": "1234",
    "host": "localhost",
    "port": 5432
}

# === LISTA PER LA RICERCA ===
ALL_DATA_TABLES = ['datia90', 'datiss51', 'datiss675']


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# Mappatura autostrada ➜ tabella corretta
def get_table_from_punto(punto):
    if not punto:
        return None
    punto_upper = punto.upper()
    if 'A90' in punto_upper:
        return 'datia90'
    elif 'SS51' in punto_upper:
        return 'datiss51'
    elif 'SS675' in punto_upper:
        return 'datiss675'
    else:
        for table in ALL_DATA_TABLES:
            if table.replace('dati', '').upper() in punto_upper:
                return table
        return None


# === ENDPOINT STATICI ===
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


# === ENDPOINT PER LA RICERCA DEI TRATTI (MODIFICATO) ===
@app.route('/api/tratti')
def search_tratti():
    """
    Endpoint per la ricerca autocomplete dei tratti.
    - Se la ricerca matcha il pattern "STRADA Km X+...", cerca per range chilometrico.
    - Altrimenti, usa il parametro 'strada' per limitare la ricerca a una singola autostrada.
    """
    query_param = request.args.get('search', '')
    strada_param = request.args.get('strada', None)  # Nuovo parametro per il contesto

    if len(query_param) < 2:
        return jsonify([])

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        sql_query = ""
        params = ()

        # Logica per la ricerca a range chilometrico (es. "A90 Km 1+...")
        km_pattern = re.compile(r'^(?P<road>\S+)\s+Km\s+(?P<km_major>\d+)', re.IGNORECASE)
        match = km_pattern.match(query_param)

        if match:
            road_name = match.group('road')
            km_major = match.group('km_major')
            table_for_km_search = get_table_from_punto(road_name)

            if table_for_km_search:
                search_term = f"{road_name.upper()} Km {km_major}+%"
                sql_query = f"SELECT DISTINCT tratto FROM {table_for_km_search} WHERE tratto ILIKE %s ORDER BY tratto LIMIT 20"
                params = (search_term,)
                logging.info(f"🔎 Ricerca per range chilometrico: '{search_term}' nella tabella {table_for_km_search}")

        else:
            # Logica di ricerca contestuale standard
            table_to_search = get_table_from_punto(strada_param)
            search_term = f"{query_param}%"

            if table_to_search:
                # Se il contesto della strada è fornito, cerca solo in quella tabella
                sql_query = f"SELECT DISTINCT tratto FROM {table_to_search} WHERE tratto ILIKE %s ORDER BY tratto LIMIT 10"
                params = (search_term,)
                logging.info(f"🔎 Ricerca contestuale per '{search_term}' nella tabella {table_to_search}")
            else:
                # Fallback: se nessun contesto è fornito, cerca in tutte le tabelle
                union_queries = [f"SELECT DISTINCT tratto FROM {table}" for table in ALL_DATA_TABLES]
                full_query = " UNION ".join(union_queries)
                sql_query = f"""
                    SELECT tratto FROM ({full_query}) as tutti_i_tratti
                    WHERE tratto ILIKE %s ORDER BY tratto LIMIT 10
                """
                params = (search_term,)
                logging.info(f"🔎 Ricerca globale per '{search_term}'")

        if sql_query:
            cursor.execute(sql_query, params)
            results = [row[0] for row in cursor.fetchall()]
        else:
            results = []

        logging.info(f"✅ Trovati {len(results)} suggerimenti.")
        return jsonify(results)

    except Exception as e:
        logging.error(f"💥 Errore durante la ricerca dei tratti: {str(e)}", exc_info=True)
        return jsonify({"errore": "Errore interno durante la ricerca"}), 500
    finally:
        if conn:
            conn.close()


# === API: FILE DINAMICI PER TRATTI ===
@app.route('/api/files/<strada>/<tratto>')
def lista_file_per_tratto(strada, tratto):
    directory = os.path.join("static", "jsons", "history", strada)
    if not os.path.exists(directory):
        return jsonify([])

    pattern = f"{strada}_{strada}_{tratto}_"
    files = [f for f in os.listdir(directory) if f.startswith(pattern) and f.endswith(".jsons")]
    files.sort(reverse=True)
    return jsonify(files)


@app.route('/grafico')
def grafico():
    tratto = request.args.get('tratto')
    if not tratto:
        return render_template('grafico.html', punto=None)

    conn = None
    try:
        modalita = request.args.get('modalità', 'storico')
        tabella = get_table_from_punto(tratto)

        if not tabella:
            logging.warning(f"Autostrada non riconosciuta per tratto: {tratto}")
            return "Autostrada non riconosciuta", 400

        conn = get_connection()
        cursor = conn.cursor()

        if modalita == 'previsionale':
            query_max = f"SELECT MAX(downloaded_at) FROM {tabella} WHERE tratto = %s"
            cursor.execute(query_max, (tratto,))
            ultimo_download = cursor.fetchone()[0]

            if not ultimo_download:
                return "Nessun dato previsionale per questo tratto", 404

            query_previsionale = f"""
                SELECT time, temperature, precipitation, windspeed, precipitation_probability
                FROM {tabella}
                WHERE tratto = %s AND downloaded_at = %s AND time >= %s
                ORDER BY time
            """
            cursor.execute(query_previsionale, (tratto, ultimo_download, ultimo_download))
            rows = cursor.fetchall()
            columns = ['time', 'temperature', 'precipitation', 'windspeed', 'precipitation_probability']
            df = pd.DataFrame(rows, columns=columns)

            return render_template('grafico_previsionale.html',
                                   dati=df.to_dict(orient='records'),
                                   tratto=tratto,
                                   ultimo_download=ultimo_download)

        return render_template('grafico.html', tratto=tratto)

    except Exception as e:
        logging.error(f"💥 Errore in /grafico: {str(e)}", exc_info=True)
        return "Si è verificato un errore interno", 500
    finally:
        if conn:
            conn.close()


@app.route('/api/dati_tratto')
def dati_tratto():
    tratto = request.args.get('tratto')
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    logging.info(f"📥 Richiesta dati storico per tratto={tratto}, start={start_date_str}, end={end_date_str}")

    if not tratto:
        return jsonify({"errore": "Parametro 'tratto' mancante"}), 400

    tabella = get_table_from_punto(tratto)
    if not tabella:
        logging.warning("❌ Autostrada non riconosciuta per tratto: %s", tratto)
        return jsonify({"errore": "Autostrada non riconosciuta"}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(f"SELECT DISTINCT punto FROM {tabella} WHERE tratto = %s LIMIT 1", (tratto,))
        result = cursor.fetchone()

        if not result:
            logging.warning("❌ Nessun punto trovato per il tratto: %s", tratto)
            return jsonify({"errore": "Tratto non trovato"}), 404

        punto = result[0]
        logging.info(f"ℹ️ Punto associato al tratto {tratto}: {punto}")

        giorni_da_processare = []

        if start_date_str and end_date_str:
            logging.info(f"📆 Intervallo richiesto: da {start_date_str} a {end_date_str}")
            try:
                start = datetime.fromisoformat(start_date_str).date()
                end = datetime.fromisoformat(end_date_str).date()
                delta = end - start
                giorni_da_processare = [start + timedelta(days=i) for i in range(delta.days + 1)]
            except ValueError:
                return jsonify({"errore": "Formato data non valido. Usare YYYY-MM-DD."}), 400
        else:
            logging.info("📆 Nessun intervallo specificato, carico tutti i giorni disponibili.")
            query_giorni = f"""
                SELECT DISTINCT DATE(downloaded_at) as giorno
                FROM {tabella} WHERE tratto = %s AND punto = %s ORDER BY giorno
            """
            cursor.execute(query_giorni, (tratto, punto))
            giorni_da_processare = [row[0] for row in cursor.fetchall()]

        logging.info(f"📅 Trovati {len(giorni_da_processare)} giorni da processare per il tratto {tratto}")
        dati_finali = []

        for giorno in giorni_da_processare:
            giorno_dt = datetime.combine(giorno, datetime.min.time())
            downloaded_start = giorno_dt.replace(hour=21, minute=0, second=0)
            downloaded_end = giorno_dt.replace(hour=21, minute=59, second=59)
            time_start = giorno_dt.replace(hour=0, minute=0, second=0)
            time_end = giorno_dt.replace(hour=23, minute=59, second=59)

            query_giorno = f"""
                SELECT downloaded_at, tratto, punto, time, temperature, precipitation, windspeed, precipitation_probability
                FROM {tabella}
                WHERE tratto = %s AND punto = %s
                  AND downloaded_at BETWEEN %s AND %s
                  AND time BETWEEN %s AND %s
                ORDER BY time
            """
            cursor.execute(query_giorno, (tratto, punto, downloaded_start, downloaded_end, time_start, time_end))
            dati_finali.extend(cursor.fetchall())

        logging.info(f"📊 Recuperate {len(dati_finali)} righe totali.")

        columns = ['downloaded_at', 'tratto', 'punto', 'time', 'temperature', 'precipitation', 'windspeed',
                   'precipitation_probability']
        df = pd.DataFrame(dati_finali, columns=columns)
        return df.to_json(orient='records')

    except Exception as e:
        logging.error(f"💥 Errore in /api/dati_tratto: {str(e)}", exc_info=True)
        return jsonify({"errore": "Si è verificato un errore interno"}), 500
    finally:
        if conn:
            conn.close()

# if __name__ == '__main__':
#     app.run(debug=True)