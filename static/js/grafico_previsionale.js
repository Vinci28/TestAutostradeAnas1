const chartRefs = {};
let datiPerReport = [];
let allRoadSegments = [];

function parseKm(kmStr) {
    if (!kmStr || typeof kmStr !== 'string') return null;
    const parts = kmStr.split('+');
    if (parts.length !== 2) return null;
    const km = parseInt(parts[0], 10);
    const m = parseInt(parts[1], 10);
    if (isNaN(km) || isNaN(m)) return null;
    return km * 1000 + m;
}

function getKmRange(segmentName) {
    const kmRegex = /Km\s(\d+\+\d{3})/g;
    const matches = [...segmentName.matchAll(kmRegex)];
    if (matches.length < 2) return null;
    const start = parseKm(matches[0][1]);
    const end = parseKm(matches[1][1]);
    if (start === null || end === null) return null;
    return { start: Math.min(start, end), end: Math.max(start, end) };
}

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

function downloadGlobalCSV() {
    if (!datiPerReport || datiPerReport.length === 0) {
        alert('Nessun dato disponibile per generare il report.');
        return;
    }
    // USA IL PUNTO E VIRGOLA come separatore
    const header = 'Time;Temperatura_C;Precipitazione_mm;Vento_ms;Prob_Precipitazione_Percent';
    let csvRows = [header];
    datiPerReport.forEach(row => {
        const time = new Date(row.time).toISOString().slice(0, 19).replace('T', ' ');

        // Sostituisce il punto con la virgola per i decimali e gestisce valori null
        const temp = row.temperature !== null && row.temperature !== undefined ? row.temperature.toString().replace('.', ',') : '';
        const prec = row.precipitation !== null && row.precipitation !== undefined ? row.precipitation.toString().replace('.', ',') : '';
        const wind = row.windspeed !== null && row.windspeed !== undefined ? row.windspeed.toString().replace('.', ',') : '';
        const prob = row.precipitation_probability !== null && row.precipitation_probability !== undefined ? row.precipitation_probability.toString().replace('.', ',') : '';

        // Usa il punto e virgola per unire
        csvRows.push(`${time};${temp};${prec};${wind};${prob}`);
    });
    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const urlParams = new URLSearchParams(window.location.search);
    const tratto = urlParams.get('tratto') || 'report';
    const filename = `Report_Globale_${tratto.replace(/[^a-z0-9]/gi, '_')}.csv`;
    triggerDownload(blob, filename);
}

function downloadChartCSV(chartId) {
    if (!datiPerReport || datiPerReport.length === 0) {
        alert('Nessun dato disponibile per generare il report.');
        return;
    }
    // USA IL PUNTO E VIRGOLA come separatore
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

        // Sostituisce il punto con la virgola per i decimali e gestisce valori null
        const valueRaw = row[config.columns[1]];
        const value = valueRaw !== null && valueRaw !== undefined ? valueRaw.toString().replace('.', ',') : '';

        // Usa il punto e virgola per unire
        csvRows.push(`${time};${value}`);
    });
    const csvContent = csvRows.join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const urlParams = new URLSearchParams(window.location.search);
    const tratto = urlParams.get('tratto') || 'report';
    const filename = `Report_${chartId}_${tratto.replace(/[^a-z0-9]/gi, '_')}.csv`;
    triggerDownload(blob, filename);
}

function setupCustomScrollbar(chart, scrollbarElement, allData) {
    const handle = scrollbarElement.querySelector('.scrollbar-handle');
    const track = scrollbarElement.querySelector('.scrollbar-track');
    let isDragging = false;
    const updateHandle = () => {
        if (!chart.scales || !chart.scales.x) return;
        const scale = chart.scales.x;
        const totalPoints = allData.length;
        const visiblePoints = scale.max - scale.min;
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
    setTimeout(updateHandle, 500);
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

function resetZoom(id) {
  if (chartRefs[id]) {
    chartRefs[id].resetZoom();
  }
}

function resetAllZooms() {
  Object.keys(chartRefs).forEach(id => {
    if (chartRefs[id]) chartRefs[id].resetZoom();
  });
}

function setupUpdatePolling(tratto, initialTimestamp) {
    const POLLING_INTERVAL_MS = 30000;
    const countdownElement = document.getElementById('countdown-refresh');

    if (!tratto || !initialTimestamp) {
        countdownElement.textContent = "Informazioni per l'aggiornamento automatico mancanti.";
        return;
    }

    console.log(`Polling iniziato. Timestamp iniziale della pagina: ${initialTimestamp}`);

    const check = () => {
        fetch(`/api/check_update?tratto=${encodeURIComponent(tratto)}`)
            .then(response => {
                if (!response.ok) throw new Error('Risposta del server non valida durante il polling.');
                return response.json();
            })
            .then(data => {
                if (data.latest_update) {
                    const latestTimestamp = data.latest_update;
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
    setInterval(check, POLLING_INTERVAL_MS);
    countdownElement.textContent = "Verifica automatica di nuovi dati attiva.";
}

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const tratto = urlParams.get('tratto');

  let currentRoad = '';
  if (tratto) {
      currentRoad = tratto.split(' ')[0];
      document.getElementById('titolo-tratto').textContent = `Grafico Previsionale - ${tratto}`;
  }

  fetch('/static/jsons/tratti_strada_allineati.json')
    .then(res => res.json())
    .then(data => {
        allRoadSegments = data;
    })
    .catch(e => console.error("Impossibile caricare i tratti stradali", e));

  // Leggiamo i dati passati da Flask attraverso l'HTML
  datiPerReport = window.chartData || [];
  const ultimoDownloadVal = window.ultimoDownload || null;

  const ultimoDownloadDate = new Date(ultimoDownloadVal);
  if (ultimoDownloadVal) {
      document.getElementById('ultimo-download').textContent = `Dati aggiornati alle: ${ultimoDownloadDate.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'medium' })}`;
  } else {
      document.getElementById('ultimo-download').textContent = 'Data di aggiornamento non disponibile.';
  }

  // Creiamo i grafici con i dati ottenuti
  creaGrafici(datiPerReport);

  document.getElementById('reset-zoom-globale').addEventListener('click', resetAllZooms);
  document.getElementById('download-report-globale').addEventListener('click', downloadGlobalCSV);

  if (ultimoDownloadVal && tratto) {
    const initialTimestampISO = ultimoDownloadDate.toISOString();
    setupUpdatePolling(tratto, initialTimestampISO);
  }

  const searchInput = document.getElementById('search-tratto');
  const suggestionsContainer = document.getElementById('suggestions-container');
  const searchButton = document.getElementById('search-button');

  searchButton.addEventListener('click', () => {
    const nuovoTratto = searchInput.value;
    if (nuovoTratto) {
      window.location.href = `/grafico?tratto=${encodeURIComponent(nuovoTratto)}&modalita=previsionale`;
    } else {
      alert('Inserisci un nome di tratto da cercare.');
    }
  });

  searchInput.addEventListener('input', () => {
        suggestionsContainer.innerHTML = '';
        const filterText = searchInput.value.trim().toLowerCase();

        if (filterText.length < 2) {
            suggestionsContainer.style.display = 'none';
            return;
        }

        const stradaLower = currentRoad.toLowerCase();
        const segmentsForStrada = allRoadSegments.filter(t => t.nome.toLowerCase().includes(stradaLower));

        const textResults = segmentsForStrada.filter(t => t.nome.toLowerCase().includes(filterText));

        let intelligentResults = [];
        const searchKmRegex = /(?:km\s*)?(\d+\+\d{1,3})/i;
        const searchMatch = filterText.match(searchKmRegex);

        if (searchMatch) {
            const searchedKmValue = parseKm(searchMatch[1]);
            if (searchedKmValue !== null) {
                intelligentResults = segmentsForStrada.filter(t => {
                    const range = getKmRange(t.nome);
                    return range && searchedKmValue >= range.start && searchedKmValue <= range.end;
                });
            }
        }

        const combined = new Map();
        textResults.forEach(t => combined.set(t.nome, t));
        intelligentResults.forEach(t => combined.set(t.nome, t));
        const filteredForList = Array.from(combined.values());

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

function creaGrafici(dati) {
  if (!dati || dati.length === 0) {
      console.log("Nessun dato da visualizzare.");
      Array.from(document.getElementsByClassName('grafico-card')).forEach(card => {
          card.innerHTML += '<p style="text-align: center; color: #aaa;">Nessun dato disponibile per questo grafico.</p>';
      });
      return;
  }

  const labels = dati.map(d => {
      const date = new Date(d.time);
      const dayMonth = date.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
      const hour = date.toLocaleTimeString('it-IT', { hour: '2-digit', timeZone: 'UTC', hour12: false });
      return `${dayMonth} ${hour}`;
  });

  const temps = dati.map(d => d.temperature).filter(t => t !== null && t !== undefined);
  const winds = dati.map(d => d.windspeed).filter(w => w !== null && w !== undefined);

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
        legend: {
            labels: {
                color: '#6c757d'
            }
        }
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
  const ids = ['temp', 'prec', 'wind', 'prob'];
  const configs = {
      'temp': config('Temperatura (°C)', dati.map(d => d.temperature), '#dc3545', yMinTemp, yMaxTemp),
      'prec': config('Precipitazione (mm)', dati.map(d => d.precipitation), '#007bff', 0, 50),
      'wind': config('Vento (m/s)', dati.map(d => d.windspeed), '#28a745', yMinWind, yMaxWind),
      'prob': config('Prob. Precipitazione (%)', dati.map(d => d.precipitation_probability), '#198f9b', 0, 100)
  };
  const probConfig = configs['prob'];
  probConfig.type = 'bar';
  probConfig.data.datasets[0].backgroundColor = '#198f9b';
  delete probConfig.data.datasets[0].tension;
  delete probConfig.data.datasets[0].fill;

  ids.forEach(id => {
      const chartElement = document.getElementById(id);
      if (chartElement) {
          chartRefs[id] = new Chart(chartElement, configs[id]);
          setupCustomScrollbar(chartRefs[id], document.getElementById(`scrollbar-${id}`), dati);
      }
  });
}