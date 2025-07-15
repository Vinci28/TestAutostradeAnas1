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
    const header = 'Time,Temperatura_C,Precipitazione_mm,Vento_ms,Prob_Precipitazione_Percent';
    let csvRows = [header];
    datiPerReport.forEach(row => {
        const date = new Date(row.time);
        date.setHours(date.getHours() + 2); // FIX: Aggiunta di 2 ore
        const time = date.toISOString().slice(0, 19).replace('T', ' ');
        const temp = row.temperature;
        const prec = row.precipitation;
        const wind = row.windspeed;
        const prob = row.precipitation_probability;
        csvRows.push(`${time},${temp},${prec},${wind},${prob}`);
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
    const reportConfig = {
        'temp': { header: 'Time,Temperatura_C', columns: ['time', 'temperature'] },
        'prec': { header: 'Time,Precipitazione_mm', columns: ['time', 'precipitation'] },
        'wind': { header: 'Time,Vento_ms', columns: ['time', 'windspeed'] },
        'prob': { header: 'Time,Prob_Precipitazione_Percent', columns: ['time', 'precipitation_probability'] }
    };
    const config = reportConfig[chartId];
    if (!config) return;
    let csvRows = [config.header];
    datiPerReport.forEach(row => {
        const date = new Date(row[config.columns[0]]);
        date.setHours(date.getHours() + 2); // FIX: Aggiunta di 2 ore
        const time = date.toISOString().slice(0, 19).replace('T', ' ');
        const value = row[config.columns[1]];
        csvRows.push(`${time},${value}`);
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
            if (typeof existingOnPanComplete === 'function') {
                existingOnPanComplete(chartContext);
            }
            updateHandle();
        };
        const existingOnZoomComplete = chart.options.plugins.zoom.zoom.onZoomComplete;
        chart.options.plugins.zoom.zoom.onZoomComplete = (chartContext) => {
            if (typeof existingOnZoomComplete === 'function') {
                existingOnZoomComplete(chartContext);
            }
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

function caricaIntervalloDate(tratto) {
  const infoElement = document.getElementById('date-range-info');
  if (!tratto) {
    infoElement.textContent = 'Selezionare un tratto per visualizzare l\'intervallo date disponibili.';
    return;
  }
  fetch(`/api/data_range?tratto=${encodeURIComponent(tratto)}`)
    .then(res => res.ok ? res.json() : res.json().then(err => { throw new Error(err.errore || "Errore API") }))
    .then(data => {
      if (data.start_date && data.end_date) {
        const startDate = new Date(data.start_date);
        const endDate = new Date(data.end_date);
        const options = { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' };
        const formattedStart = startDate.toLocaleDateString('it-IT', options);
        const formattedEnd = endDate.toLocaleDateString('it-IT', options);
        infoElement.textContent = `Periodo dati storici: dal ${formattedStart} al ${formattedEnd}`;
      } else {
        infoElement.textContent = 'Intervallo date non disponibile per questo tratto.';
      }
    })
    .catch(err => {
      console.error('Errore nel recupero dell\'intervallo date:', err);
      infoElement.textContent = `Impossibile caricare l'intervallo date: ${err.message}`;
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const tratto = urlParams.get('tratto');

  const startDateFromUrl = urlParams.get('start_date');
  const endDateFromUrl = urlParams.get('end_date');

  document.getElementById('titolo-tratto').textContent = `Grafico Storico - ${tratto || 'N/D'}`;
  caricaIntervalloDate(tratto);

  if (startDateFromUrl) {
      document.getElementById('filtro-inizio').value = startDateFromUrl;
  }
  if (endDateFromUrl) {
      document.getElementById('filtro-fine').value = endDateFromUrl;
  }

  let currentRoad = '';
  if (tratto) {
    currentRoad = tratto.split(' ')[0];
    caricaDati(tratto, startDateFromUrl, endDateFromUrl);
  }

  fetch('/static/jsons/tratti_strada_allineati.json')
    .then(res => res.json())
    .then(data => {
        allRoadSegments = data;
    })
    .catch(e => console.error("Impossibile caricare i tratti stradali", e));

  document.getElementById('applica-filtro').addEventListener('click', () => {
    const inizio = document.getElementById('filtro-inizio').value;
    const fine = document.getElementById('filtro-fine').value;
    if (new Date(fine) < new Date(inizio)) return alert("La data di fine non può precedere quella di inizio.");

    // Aggiorniamo l'URL per mantenere i filtri
    const newUrl = new URL(window.location);
    newUrl.searchParams.set('tratto', tratto);
    newUrl.searchParams.set('start_date', inizio);
    newUrl.searchParams.set('end_date', fine);
    window.history.pushState({}, '', newUrl); // Aggiorna l'URL senza ricaricare

    caricaDati(tratto, inizio, fine);
  });

  document.getElementById('reset-zoom-globale').addEventListener('click', resetAllZooms);
  document.getElementById('download-report-globale').addEventListener('click', downloadGlobalCSV);
  const searchInput = document.getElementById('search-tratto');
  const suggestionsContainer = document.getElementById('suggestions-container');
  const searchButton = document.getElementById('search-button');
  searchButton.addEventListener('click', () => {
    const nuovoTratto = searchInput.value;
    if (nuovoTratto) {
      window.location.href = window.location.pathname + '?tratto=' + encodeURIComponent(nuovoTratto);
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

function caricaDati(tratto, startDate, endDate) {
  let url = `/api/dati_tratto?tratto=${encodeURIComponent(tratto)}`;
  if (startDate && endDate) {
    url += `&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
  }
  Object.values(chartRefs).forEach(chart => {
      if (chart && typeof chart.destroy === 'function') chart.destroy();
  });
  fetch(url)
    .then(res => res.ok ? res.json() : res.json().then(err => { throw new Error(err.errore || "Errore API") }))
    .then(dati => {
      if (!dati.length) {
        alert("Nessun dato disponibile per il tratto e l'intervallo selezionato.");
        datiPerReport = [];
        creaGrafici(dati); // Chiama per pulire i grafici esistenti
        return;
      }
      datiPerReport = dati;
      creaGrafici(dati);
    })
    .catch(err => alert(`Errore nel caricamento dei dati: ${err.message}`));
}

function creaGrafici(dati) {
    // Pulisce i contenitori dei grafici prima di disegnarli o mostrare il messaggio
    document.querySelectorAll('.chart-container').forEach(container => {
        const canvasId = container.parentElement.querySelector('canvas').id;
        // Ricrea il canvas MANTENENDO il suo ID originale
        container.innerHTML = `<canvas id="${canvasId}"></canvas>`;
    });
    // Cancella i vecchi riferimenti
    Object.keys(chartRefs).forEach(id => delete chartRefs[id]);


    if (!dati || dati.length === 0) {
        console.log("Nessun dato da visualizzare.");
        document.querySelectorAll('.grafico-card').forEach(card => {
            const container = card.querySelector('.chart-container');
            container.innerHTML = '<p style="text-align: center; color: #aaa; margin-top: 50px;">Nessun dato da visualizzare per questo intervallo.</p>';
        });
        return;
    }

    const labels = dati.map(d => {
        const date = new Date(d.time);
        date.setHours(date.getHours() + 2); // FIX: Aggiunta di 2 ore
        const dayMonth = date.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', timeZone: 'UTC' });
        const hour = date.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false });
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
        datasets: [{ label, data, borderColor: color, backgroundColor: color + '22', tension: 0.3, fill: true, pointRadius: 3, pointHoverRadius: 5 }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#6c757d' } },
          zoom: { pan: { enabled: true, mode: 'x' }, zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' } }
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
        'prob': config('Prob. Precipitazione (%)', dati.map(d => d.precipitation_probability), '#ffc107', 0, 100)
    };
    const probConfig = configs['prob'];
    probConfig.type = 'bar';
    probConfig.data.datasets[0].backgroundColor = '#ffc107';
    delete probConfig.data.datasets[0].tension;
    delete probConfig.data.datasets[0].fill;
    ids.forEach(id => {
        // Questa linea ora funzionerà perché il canvas ha di nuovo il suo ID
        const canvas = document.querySelector(`#${id}`).getContext('2d');
        chartRefs[id] = new Chart(canvas, configs[id]);
        setupCustomScrollbar(chartRefs[id], document.getElementById(`scrollbar-${id}`), dati);
    });
}