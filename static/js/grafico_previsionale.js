// Questo oggetto serve per mantenere i riferimenti a tutti i grafici creati.
// È utile per poterli manipolare (es. reset dello zoom) in un secondo momento.
const chartRefs = {};
// Array globale che conterrà i dati grezzi caricati dall'API, usati per generare i grafici e i report CSV.
let datiPerReport = [];
// Array globale che conterrà tutti i tratti stradali caricati da un file JSON.
let allRoadSegments = [];

// Funzione per convertire una stringa di chilometraggio del formato "KmX+YYY" in metri.
// Ad esempio, "Km10+500" diventa 10500.
function parseKm(kmStr) {
    // Verifica se la stringa è valida e non nulla.
    if (!kmStr || typeof kmStr !== 'string') return null;
    // Separa la stringa in chilometri e metri.
    const parts = kmStr.split('+');
    // Si assicura che il formato sia corretto (es. "Km+m").
    if (parts.length !== 2) return null;
    const km = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    // Verifica che i valori siano numeri validi.
    if (isNaN(km) || isNaN(m)) return null;
    // Calcola il totale in metri.
    return km * 1000 + m;
}

// Funzione per estrarre l'intervallo di chilometraggio (in metri) da una stringa che descrive un tratto stradale.
// Ad esempio, da "Tratto A-B Km 10+500 - Km 12+000" estrae l'intervallo [10500, 12000].
function getKmRange(segmentName) {
    const kmRegex = /Km\s(\d+\+\d{3})/g;
    const matches = [...segmentName.matchAll(kmRegex)];
    // Deve trovare almeno due corrispondenze per un intervallo.
    if (matches.length < 2) return null;
    const start = parseKm(matches[0][1]);
    const end = parseKm(matches[1][1]);
    // Verifica che entrambi i valori siano validi.
    if (start === null || end === null) return null;
    // Restituisce l'intervallo ordinato.
    return { start: Math.min(start, end), end: Math.max(start, end) };
}

// Funzione helper per avviare il download di un file dal browser.
function triggerDownload(blob, filename) {
    const link = document.createElement('a');
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

// Funzione per scaricare un report CSV contenente tutti i dati dei grafici.
function downloadGlobalCSV() {
    if (!datiPerReport || datiPerReport.length === 0) {
        alert('Nessun dato disponibile per generare il report.');
        return;
    }
    // L'header del file CSV. Il punto e virgola (;) è usato come separatore.
    const header = 'Time;Temperatura_C;Precipitazione_mm;Vento_ms;Prob_Precipitazione_Percent';
    let csvRows = [header];
    datiPerReport.forEach(row => {
        // Formatta la data e l'ora.
        const time = new Date(row.time).toISOString().slice(0, 19).replace('T', ' ');

        // Prepara i valori, sostituendo il punto decimale con una virgola e gestendo i valori null.
        const temp = row.temperature !== null && row.temperature !== undefined ? row.temperature.toString().replace('.', ',') : '';
        const prec = row.precipitation !== null && row.precipitation !== undefined ? row.precipitation.toString().replace('.', ',') : '';
        const wind = row.windspeed !== null && row.windspeed !== undefined ? row.windspeed.toString().replace('.', ',') : '';
        const prob = row.precipitation_probability !== null && row.precipitation_probability !== undefined ? row.precipitation_probability.toString().replace('.', ',') : '';

        // Unisce i valori con il punto e virgola.
        csvRows.push(`${time};${temp};${prec};${wind};${prob}`);
    });
    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const urlParams = new URLSearchParams(window.location.search);
    const tratto = urlParams.get('tratto') || 'report';
    const filename = `Report_Globale_${tratto.replace(/[^a-z0-9]/gi, '_')}.csv`;
    triggerDownload(blob, filename);
}

// Funzione per scaricare un singolo report CSV per un grafico specifico (es. solo temperatura).
function downloadChartCSV(chartId) {
    if (!datiPerReport || datiPerReport.length === 0) {
        alert('Nessun dato disponibile per generare il report.');
        return;
    }
    // Configurazione per i vari report.
    const reportConfig = {
        'temp': { header: 'Time;Temperatura_C', columns: ['time', 'temperature'] },
        'prec': { header: 'Time;Precipitazione_mm', columns: ['time', 'precipitation'] },
        'wind': { header: 'Time;Vento_ms', columns: ['time', 'windspeed'] },
        'prob': { header: 'Time;Prob_Precipitazione_Percent', columns: ['time', 'precipitation_probability'] }
    };
    const config = reportConfig[chartId];
    if (!config) return;
    let csvRows = [config.header];
    datiPerReport.forEach(row => {
        const time = new Date(row[config.columns[0]]).toISOString().slice(0, 19).replace('T', ' ');
        const valueRaw = row[config.columns[1]];
        const value = valueRaw !== null && valueRaw !== undefined ? valueRaw.toString().replace('.', ',') : '';
        csvRows.push(`${time};${value}`);
    });
    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const urlParams = new URLSearchParams(window.location.search);
    const tratto = urlParams.get('tratto') || 'report';
    const filename = `Report_${chartId}_${tratto.replace(/[^a-z0-9]/gi, '_')}.csv`;
    triggerDownload(blob, filename);
}

// Funzione per impostare una scrollbar personalizzata sotto ogni grafico.
function setupCustomScrollbar(chart, scrollbarElement, allData) {
    const handle = scrollbarElement.querySelector('.scrollbar-handle');
    const track = scrollbarElement.querySelector('.scrollbar-track');
    let isDragging = false;

    // Aggiorna la posizione della maniglia della scrollbar in base allo zoom del grafico.
    const updateHandle = () => {
        if (!chart.scales || !chart.scales.x) return;
        const scale = chart.scales.x;
        const totalPoints = allData.length;
        const visiblePoints = scale.max - scale.min;
        // Nasconde la scrollbar se tutti i dati sono visibili.
        if (totalPoints <= Math.ceil(visiblePoints)) {
            scrollbarElement.style.display = 'none';
            return;
        }
        scrollbarElement.style.display = 'block';
        const scrollableRange = totalPoints - visiblePoints;
        if (scrollableRange <= 0) return;
        const scrollPercent = scale.min / scrollableRange;
        const maxHandleLeft = track.offsetWidth - handle.offsetWidth;
        handle.style.left = `${scrollPercent * maxHandleLeft}px`;
    };

    // Collega l'aggiornamento della scrollbar agli eventi di zoom e pan di Chart.js.
    if (chart.options.plugins.zoom) {
        const existingOnPanComplete = chart.options.plugins.zoom.pan.onPanComplete;
        chart.options.plugins.zoom.pan.onPanComplete = (chartContext) => {
            if (typeof existingOnPanComplete === 'function') existingOnPanComplete(chartContext);
            updateHandle();
        };
        const existingOnZoomComplete = chart.options.plugins.zoom.zoom.onZoomComplete;
        chart.options.plugins.zoom.zoom.onZoomComplete = (chartContext) => {
            if (typeof existingOnZoomComplete === 'function') existingOnZoomComplete(chartContext);
            updateHandle();
        };
    }
    // Avvia un aggiornamento iniziale dopo un breve ritardo.
    setTimeout(updateHandle, 500);

    // Gestisce il trascinamento della maniglia della scrollbar per navigare nel grafico.
    handle.addEventListener('mousedown', (e) => {
        isDragging = true;
        handle.style.cursor = 'grabbing';
        document.body.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';
        const startX = e.pageX;
        const startLeft = handle.offsetLeft;
        const maxHandleLeft = track.offsetWidth - handle.offsetWidth;
        const scale = chart.scales.x;
        const totalPoints = allData.length;
        const initialVisiblePoints = scale.max - scale.min;
        const scrollableRange = totalPoints - initialVisiblePoints;

        const onMouseMove = (moveEvent) => {
            if (!isDragging || scrollableRange <= 0) return;
            moveEvent.preventDefault();
            const deltaX = moveEvent.pageX - startX;
            let newLeft = startLeft + deltaX;
            newLeft = Math.max(0, Math.min(newLeft, maxHandleLeft));
            handle.style.left = `${newLeft}px`;
            const positionPercent = newLeft / maxHandleLeft;
            const newMin = positionPercent * scrollableRange;
            const newMax = newMin + initialVisiblePoints;
            chart.zoomScale('x', {min: newMin, max: newMax}, 'none');
        };

        const onMouseUp = () => {
            isDragging = false;
            handle.style.cursor = 'grab';
            document.body.style.cursor = 'default';
            document.body.style.userSelect = '';
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });
}

// Funzione per resettare lo zoom di un singolo grafico.
function resetZoom(id) {
  if (chartRefs[id]) {
    chartRefs[id].resetZoom();
  }
}

// Funzione per resettare lo zoom di tutti i grafici.
function resetAllZooms() {
  Object.keys(chartRefs).forEach(id => {
    if (chartRefs[id]) chartRefs[id].resetZoom();
  });
}

// Funzione per configurare il polling automatico dei dati.
// Controlla periodicamente se ci sono nuovi dati disponibili dall'API e ricarica la pagina in caso affermativo.
function setupUpdatePolling(tratto, initialTimestamp) {
    const POLLING_INTERVAL_MS = 30000;
    const countdownElement = document.getElementById('countdown-refresh');

    if (!tratto || !initialTimestamp) {
        countdownElement.textContent = "Informazioni per l'aggiornamento automatico mancanti.";
        return;
    }

    console.log(`Polling iniziato. Timestamp iniziale della pagina: ${initialTimestamp}`);

    const check = () => {
        // Chiama l'API per controllare l'ultimo aggiornamento.
        fetch(`/api/check_update?tratto=${encodeURIComponent(tratto)}`)
            .then(response => {
                if (!response.ok) throw new Error('Risposta del server non valida durante il polling.');
                return response.json();
            })
            .then(data => {
                if (data.latest_update) {
                    const latestTimestamp = data.latest_update;
                    // Se il timestamp dell'API è più recente di quello della pagina corrente, ricarica.
                    if (new Date(latestTimestamp) > new Date(initialTimestamp)) {
                        countdownElement.textContent = "Nuovi dati disponibili! Ricarico la pagina...";
                        setTimeout(() => {
                            window.location.reload();
                        }, 2000);
                    } else {
                        countdownElement.textContent = "I dati visualizzati sono i più recenti. Prossimo controllo tra un minuto.";
                    }
                } else {
                    countdownElement.textContent = "In attesa di dati per questo tratto. Controllo di nuovo tra un minuto.";
                }
            })
            .catch(err => {
                console.error("Errore durante il polling degli aggiornamenti:", err);
                countdownElement.textContent = "Errore di connessione durante la verifica di nuovi dati.";
            });
    };
    // Imposta l'intervallo per il controllo periodico.
    setInterval(check, POLLING_INTERVAL_MS);
    countdownElement.textContent = "Verifica automatica di nuovi dati attiva.";
}

// Esegue il codice quando la pagina è completamente caricata.
document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const tratto = urlParams.get('tratto');

  let currentRoad = '';
  if (tratto) {
      currentRoad = tratto.split(' ')[0];
      document.getElementById('titolo-tratto').textContent = `Grafico Previsionale - ${tratto}`;
  }

  // Carica i tratti stradali da un file JSON.
  fetch('/static/jsons/tratti_strada_allineati.json')
    .then(res => res.json())
    .then(data => {
        allRoadSegments = data;
    })
    .catch(e => console.error("Impossibile caricare i tratti stradali", e));

  // Legge i dati e il timestamp dall'oggetto 'window' iniettato da Flask.
  datiPerReport = window.chartData || [];
  const ultimoDownloadVal = window.ultimoDownload || null;

  const ultimoDownloadDate = new Date(ultimoDownloadVal);
  if (ultimoDownloadVal) {
      document.getElementById('ultimo-download').textContent = `Dati aggiornati alle: ${ultimoDownloadDate.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'medium' })}`;
  } else {
      document.getElementById('ultimo-download').textContent = 'Data di aggiornamento non disponibile.';
  }

  // Crea i grafici con i dati ottenuti.
  creaGrafici(datiPerReport);

  // Aggiunge i listener per i pulsanti di reset e download.
  document.getElementById('reset-zoom-globale').addEventListener('click', resetAllZooms);
  document.getElementById('download-report-globale').addEventListener('click', downloadGlobalCSV);

  // Se i dati e il tratto sono disponibili, avvia il polling.
  if (ultimoDownloadVal && tratto) {
    const initialTimestampISO = ultimoDownloadDate.toISOString();
    setupUpdatePolling(tratto, initialTimestampISO);
  }

  // Sezione per la ricerca e i suggerimenti dei tratti stradali.
  const searchInput = document.getElementById('search-tratto');
  const suggestionsContainer = document.getElementById('suggestions-container');
  const searchButton = document.getElementById('search-button');

  // Gestisce il click sul pulsante di ricerca.
  searchButton.addEventListener('click', () => {
    const nuovoTratto = searchInput.value;
    if (nuovoTratto) {
      window.location.href = `/grafico?tratto=${encodeURIComponent(nuovoTratto)}&modalita=previsionale`;
    } else {
      alert('Inserisci un nome di tratto da cercare.');
    }
  });

  // Gestisce l'input nella barra di ricerca per mostrare i suggerimenti.
  searchInput.addEventListener('input', () => {
        suggestionsContainer.innerHTML = '';
        const filterText = searchInput.value.trim().toLowerCase();

        if (filterText.length < 2) {
            suggestionsContainer.style.display = 'none';
            return;
        }

        const stradaLower = currentRoad.toLowerCase();
        // Filtra i tratti per la strada corrente.
        const segmentsForStrada = allRoadSegments.filter(t => t.nome.toLowerCase().includes(stradaLower));
        // Filtra per corrispondenza di testo.
        const textResults = segmentsForStrada.filter(t => t.nome.toLowerCase().includes(filterText));

        let intelligentResults = [];
        const searchKmRegex = /(?:km\s*)?(\d+\+\d{1,3})/i;
        const searchMatch = filterText.match(searchKmRegex);

        // Aggiunge risultati "intelligenti" basati sul chilometraggio.
        if (searchMatch) {
            const searchedKmValue = parseKm(searchMatch[1]);
            if (searchedKmValue !== null) {
                intelligentResults = segmentsForStrada.filter(t => {
                    const range = getKmRange(t.nome);
                    return range && searchedKmValue >= range.start && searchedKmValue <= range.end;
                });
            }
        }

        // Unisce i risultati di testo e di chilometraggio per evitare duplicati.
        const combined = new Map();
        textResults.forEach(t => combined.set(t.nome, t));
        intelligentResults.forEach(t => combined.set(t.nome, t));
        const filteredForList = Array.from(combined.values());

        // Popola il contenitore dei suggerimenti.
        if (filteredForList.length > 0) {
            filteredForList.forEach(tratto => {
                const item = document.createElement('div');
                item.classList.add('suggestion-item');
                item.textContent = tratto.nome;
                item.addEventListener('click', () => {
                    searchInput.value = tratto.nome;
                    suggestionsContainer.style.display = 'none';
                    searchButton.click();
                });
                suggestionsContainer.appendChild(item);
            });
            suggestionsContainer.style.display = 'block';
        } else {
            suggestionsContainer.style.display = 'none';
        }
    });
});

// Funzione principale per la creazione dei grafici.
function creaGrafici(dati) {
  // Se non ci sono dati, mostra un messaggio e si ferma.
  if (!dati || dati.length === 0) {
      console.log("Nessun dato da visualizzare.");
      Array.from(document.getElementsByClassName('grafico-card')).forEach(card => {
          card.innerHTML += '<p style="text-align: center; color: #aaa;">Nessun dato disponibile per questo grafico.</p>';
      });
      return;
  }

  // Prepara le etichette per l'asse X (tempo).
  const labels = dati.map(d => {
      const date = new Date(d.time);
      const dayMonth = date.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
      const hour = date.toLocaleTimeString('it-IT', { hour: '2-digit', timeZone: 'UTC', hour12: false });
      return `${dayMonth} ${hour}`;
  });

  // Estrae i dati numerici e filtra i valori non validi.
  const temps = dati.map(d => d.temperature).filter(t => t !== null && t !== undefined);
  const winds = dati.map(d => d.windspeed).filter(w => w !== null && w !== undefined);

  // Calcola i limiti dell'asse Y per una migliore visualizzazione.
  let yMinTemp = -10, yMaxTemp = 40;
  if (temps.length > 0) {
      yMinTemp = Math.floor(Math.min(...temps) - 5);
      yMaxTemp = Math.ceil(Math.max(...temps) + 5);
  }

  const yMinWind = 0;
  let yMaxWind = 10;
  if (winds.length > 0) {
      yMaxWind = Math.ceil(Math.max(...winds) + 1);
  }

  // Funzione helper per creare le configurazioni dei grafici Chart.js.
  const config = (label, data, color, yMin, yMax) => ({
    type: 'line',
    data: {
      labels: labels,
      datasets: [{ label, data, borderColor: color, backgroundColor: color + '22', tension: 0.3, fill: true, pointRadius: 4, pointHoverRadius: 6 }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        zoom: {
          pan: { enabled: true, mode: 'x' },
          zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
        },
        legend: { labels: { color: '#6c757d' } }
      },
      scales: {
          x: {
              ticks: { autoSkip: true, maxTicksLimit: 15, maxRotation: 45, minRotation: 0, color: '#555' },
              grid: { color: '#e9ecef'}
          },
          y: {
              min: yMin,
              max: yMax,
              grid: { zeroLineColor: 'rgba(255, 99, 132, 0.8)', zeroLineWidth: 2, color: '#e9ecef' },
              ticks: { color: '#555' }
          }
        }
    }
  });

  // I nomi dei grafici per l'HTML.
  const ids = ['temp', 'prec', 'wind', 'prob'];

  // Le configurazioni complete per ogni grafico.
  const configs = {
      'temp': config('Temperatura (°C)', dati.map(d => d.temperature), '#dc3545', yMinTemp, yMaxTemp),
      'prec': config('Precipitazione (mm)', dati.map(d => d.precipitation), '#007bff', 0, 50),
      'wind': config('Vento (m/s)', dati.map(d => d.windspeed), '#28a745', yMinWind, yMaxWind),
      'prob': config('Prob. Precipitazione (%)', dati.map(d => d.precipitation_probability), '#198f9b', 0, 100)
  };

  // Modifica la configurazione del grafico di probabilità per renderlo a barre.
  const probConfig = configs['prob'];
  probConfig.type = 'bar';
  probConfig.data.datasets[0].backgroundColor = '#198f9b';
  delete probConfig.data.datasets[0].tension;
  delete probConfig.data.datasets[0].fill;

  // Itera sugli ID e crea ogni grafico.
  ids.forEach(id => {
      const chartElement = document.getElementById(id);
      if (chartElement) {
          // Crea un nuovo grafico e lo memorizza in chartRefs.
          chartRefs[id] = new Chart(chartElement, configs[id]);
          // Aggiunge la scrollbar personalizzata.
          setupCustomScrollbar(chartRefs[id], document.getElementById(`scrollbar-${id}`), dati);
      }
  });
}