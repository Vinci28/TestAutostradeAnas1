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
            # Query per ultimo download disponibile
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
                conn.close()
                return "Nessun dato disponibile per questo tratto", 404

            # Query per dati previsionali
            query_previsionale = f"""
                SELECT 
                    time, 
                    temperature, 
                    precipitation, 
                    windspeed, 
                    precipitation_probability
                FROM {tabella}
                WHERE tratto = %s AND downloaded_at = %s
                ORDER BY time
            """
            params_previsionale = (tratto, ultimo_download)

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
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')

            if not start_date or not end_date:
                logging.error("Parametri temporali mancanti per modalità storico")
                conn.close()
                return "Intervallo temporale obbligatorio per modalità storico", 400

            # Query per trovare il punto associato
            query_punto = f"""
                SELECT DISTINCT punto 
                FROM {tabella} 
                WHERE tratto = %s 
                LIMIT 1
            """
            params_punto = (tratto,)

            logging.info("📜 QUERY NATIVA STORICO (trova punto):")
            logging.info("SQL: %s", query_punto.replace('\n', ' ').strip())
            logging.info("Parametri: %s", params_punto)

            cursor.execute(query_punto, params_punto)
            punto = cursor.fetchone()

            if not punto:
                logging.warning(f"❌ Nessun punto trovato per tratto: {tratto}")
                conn.close()
                return "Tratto non trovato", 404
            punto = punto[0]

            # Query principale per dati storici
            query_storico = f"""
                SELECT 
                    downloaded_at, 
                    tratto, 
                    punto, 
                    time, 
                    temperature, 
                    precipitation, 
                    windspeed, 
                    precipitation_probability
                FROM {tabella}
                WHERE tratto = %s 
                  AND punto = %s
                  AND downloaded_at BETWEEN %s AND %s
                ORDER BY time
            """
            params_storico = (tratto, punto, start_date, end_date)

            logging.info("📜 QUERY NATIVA STORICO (dati):")
            logging.info("SQL: %s", query_storico.replace('\n', ' ').strip())
            logging.info("Parametri: %s", params_storico)

            cursor.execute(query_storico, params_storico)
            rows = cursor.fetchall()

            columns = ['downloaded_at', 'tratto', 'punto',
                       'time', 'temperature', 'precipitation',
                       'windspeed', 'precipitation_probability']
            df = pd.DataFrame(rows, columns=columns)

            return render_template('grafico.html',
                                   dati=df.to_dict(orient='records'),
                                   punto=tratto)

        else:
            conn.close()
            return "Modalità non riconosciuta", 400

    except Exception as e:
        logging.error(f"💥 Errore durante l'elaborazione della richiesta: {str(e)}", exc_info=True)
        if 'conn' in locals() and conn:
            conn.close()
        return "Si è verificato un errore interno", 500
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()


@app.route('/api/dati_tratto')
def dati_tratto():
    tratto = request.args.get('tratto')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    logging.info(f"📥 Richiesta dati storico per tratto={tratto}, start={start_date}, end={end_date}")

    tabella = get_table_from_punto(tratto)
    if not tabella:
        logging.warning("❌ Autostrada non riconosciuta per tratto: %s", tratto)
        return {"errore": "Autostrada non riconosciuta"}, 400

    conn = get_connection()
    cursor = conn.cursor()

    # Trovo il punto associato
    cursor.execute(f"SELECT DISTINCT punto FROM {tabella} WHERE tratto = %s LIMIT 1", (tratto,))
    result = cursor.fetchone()

    if not result:
        logging.warning("❌ Nessun punto trovato per il tratto: %s", tratto)
        conn.close()
        return {"errore": "Tratto non trovato"}, 404

    punto = result[0]
    logging.info(f"ℹ️ Punto associato al tratto {tratto}: {punto}")

    start = datetime.fromisoformat(start_date)
    end = datetime.fromisoformat(end_date)
    giorni = (end - start).days
    logging.info(f"📆 Intervallo richiesto: {giorni} giorno/i")

    dati_finali = []

    for i in range(giorni):
        giorno = start + timedelta(days=i)
        time_start = giorno.replace(hour=0, minute=0, second=0)
        time_end = giorno.replace(hour=23, minute=0, second=0)

        downloaded_start = giorno.replace(hour=21, minute=0, second=0)
        downloaded_end = giorno.replace(hour=21, minute=59, second=59)

        logging.info(f"🟢 Giorno {giorno.strftime('%Y-%m-%d')}: filtro time=[{time_start}, {time_end}], downloaded_at=[{downloaded_start}, {downloaded_end}]")

        cursor.execute(f"""
            SELECT downloaded_at, tratto, punto, time, temperature, precipitation, windspeed, precipitation_probability
            FROM {tabella}
            WHERE tratto = %s AND punto = %s
              AND downloaded_at BETWEEN %s AND %s
              AND time BETWEEN %s AND %s
            ORDER BY time
        """, (tratto, punto, downloaded_start, downloaded_end, time_start, time_end))

        rows = cursor.fetchall()
        logging.info(f"📊 Recuperate {len(rows)} righe per il giorno {giorno.strftime('%Y-%m-%d')}")
        dati_finali.extend(rows)

    cursor.close()
    conn.close()

    if not dati_finali:
        logging.warning("⚠️ Nessun dato meteo trovato per l'intervallo richiesto.")

    columns = ['downloaded_at', 'tratto', 'punto', 'time', 'temperature', 'precipitation', 'windspeed', 'precipitation_probability']
    df = pd.DataFrame(dati_finali, columns=columns)

    return df.to_json(orient='records')

##DATI DISPONIBILI DAL 06 GIUGNO FINO AL 12 ALLE 13 PER A90
## DAL 06 FINO AL 13 PER LA SS675 FINO ALLE 6
## DAL 06 FINO AL 13 PER LA SS51 ALLE 11
