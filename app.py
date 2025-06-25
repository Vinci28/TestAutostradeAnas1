from flask import Flask, render_template, request, jsonify, send_from_directory
import psycopg2
import logging
import os
import pandas as pd
from datetime import datetime, timedelta

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


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# Mappatura autostrada ➜ tabella corretta
def get_table_from_punto(punto):
    if 'A90' in punto:
        return 'datia90'
    elif 'SS51' in punto:
        return 'datiss51'
    elif 'SS675' in punto:
        return 'datiss675'
    else:
        return None  # Autostrada non supportata


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
    conn = None
    cursor = None
    try:
        tratto = request.args.get('tratto')
        modalita = request.args.get('modalità', 'storico')

        if not tratto:
            logging.error("Parametro 'tratto' mancante")
            return "Parametro 'tratto' obbligatorio", 400

        tabella = get_table_from_punto(tratto)
        if not tabella:
            logging.warning(f"Autostrada non riconosciuta per tratto: {tratto}")
            return "Autostrada non riconosciuta", 400

        conn = get_connection()
        cursor = conn.cursor()

        if modalita == 'previsionale':
            # 1. Trova l'ultimo download disponibile
            query_max = f"""
                SELECT MAX(downloaded_at) 
                FROM {tabella} 
                WHERE tratto = %s
            """
            params_max = (tratto,)

            logging.info("📜 QUERY NATIVA PREVISIONALE (ultimo download):")
            logging.info("SQL: %s", query_max.replace('\n', ' ').strip())
            logging.info("Parametri: %s", params_max)

            cursor.execute(query_max, params_max)
            ultimo_download = cursor.fetchone()[0]

            if not ultimo_download:
                logging.warning(f"⚠️ Nessun dato trovato per tratto: {tratto}")
                return "Nessun dato disponibile per questo tratto", 404

            # 2. Query per i dati previsionali a partire dall'orario dell'ultimo download
            query_previsionale = f"""
                SELECT 
                    time, 
                    temperature, 
                    precipitation, 
                    windspeed, 
                    precipitation_probability
                FROM {tabella}
                WHERE tratto = %s AND downloaded_at = %s AND time >= %s
                ORDER BY time
            """
            params_previsionale = (tratto, ultimo_download, ultimo_download)

            logging.info("📜 QUERY NATIVA PREVISIONALE (dati):")
            logging.info("SQL: %s", query_previsionale.replace('\n', ' ').strip())
            logging.info("Parametri: %s", params_previsionale)

            cursor.execute(query_previsionale, params_previsionale)
            rows = cursor.fetchall()

            columns = ['time', 'temperature', 'precipitation',
                       'windspeed', 'precipitation_probability']
            df = pd.DataFrame(rows, columns=columns)

            return render_template('grafico_previsionale.html',
                                   dati=df.to_dict(orient='records'),
                                   punto=tratto,
                                   ultimo_download=ultimo_download)

        elif modalita == 'storico':
            # La logica per la modalità 'storico' rimane invariata
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            query_punto = f"""
                SELECT DISTINCT punto 
                FROM {tabella} 
                WHERE tratto = %s 
                LIMIT 1
            """
            cursor.execute(query_punto, (tratto,))
            punto_result = cursor.fetchone()

            if not punto_result:
                logging.warning(f"❌ Nessun punto trovato per tratto: {tratto}")
                return "Tratto non trovato", 404
            punto = punto_result[0]

            if not start_date or not end_date:
                logging.info(f"📊 Caricamento dati storici delle 21:00 per ogni giorno disponibile per tratto: {tratto}")
                query_giorni = f"""
                    SELECT DISTINCT DATE(downloaded_at) as giorno
                    FROM {tabella}
                    WHERE tratto = %s AND punto = %s
                    ORDER BY giorno
                """
                cursor.execute(query_giorni, (tratto, punto))
                giorni_disponibili = cursor.fetchall()
                rows = []
                for (giorno,) in giorni_disponibili:
                    giorno_dt = datetime.combine(giorno, datetime.min.time())
                    downloaded_start = giorno_dt.replace(hour=21, minute=0, second=0)
                    downloaded_end = giorno_dt.replace(hour=21, minute=59, second=59)
                    time_start = giorno_dt.replace(hour=0, minute=0, second=0)
                    time_end = giorno_dt.replace(hour=23, minute=59, second=59)
                    query_giorno = f"""
                        SELECT downloaded_at, tratto, punto, time, temperature, precipitation, windspeed, precipitation_probability
                        FROM {tabella}
                        WHERE tratto = %s AND punto = %s AND downloaded_at BETWEEN %s AND %s AND time BETWEEN %s AND %s
                        ORDER BY time
                    """
                    cursor.execute(query_giorno,
                                   (tratto, punto, downloaded_start, downloaded_end, time_start, time_end))
                    rows.extend(cursor.fetchall())
            else:
                logging.info(f"📊 Caricamento dati storici filtrati per tratto: {tratto}, da {start_date} a {end_date}")
                query_storico = f"""
                    SELECT downloaded_at, tratto, punto, time, temperature, precipitation, windspeed, precipitation_probability
                    FROM {tabella}
                    WHERE tratto = %s AND punto = %s AND downloaded_at BETWEEN %s AND %s
                    ORDER BY time
                """
                cursor.execute(query_storico, (tratto, punto, start_date, end_date))
                rows = cursor.fetchall()

            columns = ['downloaded_at', 'tratto', 'punto', 'time', 'temperature', 'precipitation', 'windspeed',
                       'precipitation_probability']
            df = pd.DataFrame(rows, columns=columns)
            return render_template('grafico.html', dati=df.to_dict(orient='records'), punto=tratto)

        else:
            return "Modalità non riconosciuta", 400

    except Exception as e:
        logging.error(f"💥 Errore durante l'elaborazione della richiesta: {str(e)}", exc_info=True)
        return "Si è verificato un errore interno", 500
    finally:
        if cursor:
            cursor.close()
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

        # Trova il punto associato
        cursor.execute(f"SELECT DISTINCT punto FROM {tabella} WHERE tratto = %s LIMIT 1", (tratto,))
        result = cursor.fetchone()

        if not result:
            logging.warning("❌ Nessun punto trovato per il tratto: %s", tratto)
            return jsonify({"errore": "Tratto non trovato"}), 404

        punto = result[0]
        logging.info(f"ℹ️ Punto associato al tratto {tratto}: {punto}")

        giorni_da_processare = []

        # Caso 1: Date specificate dall'utente
        if start_date_str and end_date_str:
            logging.info(f"📆 Intervallo richiesto: da {start_date_str} a {end_date_str}")
            try:
                start = datetime.fromisoformat(start_date_str).date()
                end = datetime.fromisoformat(end_date_str).date()

                delta = end - start
                for i in range(delta.days + 1):  # +1 per includere la data di fine
                    day = start + timedelta(days=i)
                    giorni_da_processare.append(day)
            except ValueError:
                return jsonify({"errore": "Formato data non valido. Usare YYYY-MM-DD."}), 400

        # Caso 2: Nessuna data, prendi tutti i giorni disponibili
        else:
            logging.info("📆 Nessun intervallo specificato, carico tutti i giorni disponibili.")
            query_giorni = f"""
                SELECT DISTINCT DATE(downloaded_at) as giorno
                FROM {tabella}
                WHERE tratto = %s AND punto = %s
                ORDER BY giorno
            """
            cursor.execute(query_giorni, (tratto, punto))
            giorni_da_processare = [row[0] for row in cursor.fetchall()]

        logging.info(f"📅 Trovati {len(giorni_da_processare)} giorni da processare per il tratto {tratto}")

        dati_finali = []

        # Per ogni giorno identificato, esegui la query specifica
        for giorno in giorni_da_processare:
            giorno_dt = datetime.combine(giorno, datetime.min.time())

            downloaded_start = giorno_dt.replace(hour=21, minute=0, second=0)
            downloaded_end = giorno_dt.replace(hour=21, minute=59, second=59)
            time_start = giorno_dt.replace(hour=0, minute=0, second=0)
            time_end = giorno_dt.replace(hour=23, minute=59, second=59)

            logging.info(f"🟢 Giorno {giorno}: filtro downloaded_at=[{downloaded_start}, {downloaded_end}]")

            query_giorno = f"""
                SELECT downloaded_at, tratto, punto, time, temperature, precipitation, windspeed, precipitation_probability
                FROM {tabella}
                WHERE tratto = %s AND punto = %s
                  AND downloaded_at BETWEEN %s AND %s
                  AND time BETWEEN %s AND %s
                ORDER BY time
            """
            cursor.execute(query_giorno, (tratto, punto, downloaded_start, downloaded_end, time_start, time_end))
            rows_giorno = cursor.fetchall()

            logging.info(f"📊 Recuperate {len(rows_giorno)} righe per il giorno {giorno}")
            dati_finali.extend(rows_giorno)

        if not dati_finali:
            logging.warning("⚠️ Nessun dato meteo trovato per i criteri specificati.")

        columns = ['downloaded_at', 'tratto', 'punto', 'time', 'temperature', 'precipitation', 'windspeed',
                   'precipitation_probability']
        df = pd.DataFrame(dati_finali, columns=columns)

        return df.to_json(orient='records')

    except Exception as e:
        logging.error(f"💥 Errore durante l'elaborazione della richiesta API: {str(e)}", exc_info=True)
        return jsonify({"errore": "Si è verificato un errore interno"}), 500
    finally:
        if conn:
            conn.close()