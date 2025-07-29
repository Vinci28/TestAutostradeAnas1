document.addEventListener('DOMContentLoaded', () => {
    const SCALES = {
        temperature: { unit: '°C', steps: [{ value: -5, color: 'rgb(102, 0, 153)', label: 'Gelo Intenso' }, { value: 0, color: 'rgb(0, 51, 204)', label: 'Gelo Moderato' }, { value: 10, color: 'rgb(51, 153, 255)', label: 'Freddo' }, { value: 25, color: 'rgb(0, 204, 0)', label: 'Normale' }, { value: 35, color: 'rgb(255, 190, 0)', label: 'Caldo' }, { value: Infinity, color: 'rgb(204, 0, 0)', label: 'Molto Caldo' }], labels: ['< -5°C', '-5°C - 0°C', '0°C - 10°C', '10°C - 25°C', '25°C - 35°C', '> 35°C'] },
        windspeed: { unit: 'km/h', steps: [{ value: 20, color: 'rgb(204, 229, 255)', label: 'Assente/Debole' }, { value: 40, color: 'rgb(153, 255, 153)', label: 'Moderato' }, { value: 60, color: 'rgb(255, 255, 102)', label: 'Sostenuto' }, { value: 80, color: 'rgb(255, 153, 51)', label: 'Forte' }, { value: Infinity, color: 'rgb(255, 51, 51)', label: 'Molto Forte' }], labels: ['0-20', '20-40', '40-60', '60-80', '> 80'] },
        precipitation: { unit: 'mm', steps: [{ value: 0.2, color: 'rgb(173, 216, 230)', label: 'Assente' }, { value: 2.0, color: 'rgb(0, 0, 255)', label: 'Debole' }, { value: 10.0, color: 'rgb(0, 128, 0)', label: 'Moderato' }, { value: 25.0, color: 'rgb(255, 255, 0)', label: 'Intenso' }, { value: 50.0, color: 'rgb(255, 165, 0)', label: 'Forte' }, { value: Infinity, color: 'rgb(255, 0, 0)', label: 'Molto Forte' }], labels: ['< 0.2', '0.2-2.0', '2.0-10.0', '10.0-25.0', '25.0-50.0', '> 50.0'] }
    };
    const BOUNDS = { A90: [[41.8, 12.3], [42.0, 12.7]], SS51: [[45.8, 12.2], [46.7, 12.4]], SS675: [[42.3, 11.9], [42.7, 12.4]] };
    const COLORS = { DEFAULT: '#808080', SELECTED_BLUE: '#00338D', SELECTED_WEIGHT: 8, DEFAULT_WEIGHT: 5 };

    const renderer = L.canvas({ padding: 0.5 });
    const map = L.map('map', { preferCanvas: true, renderer, zoomControl: false }).setView([42.5, 12.5], 7);
    L.control.zoom({ position: 'topleft' }).addTo(map);
    const baseMaps = {
        "Mappa Chiara": L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '&copy; OpenStreetMap &copy; CARTO' }).addTo(map),
        "Mappa Standard": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }),
        "Mappa Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri' })
    };
    L.control.layers(baseMaps, null, { position: 'topleft' }).addTo(map);

    let allSegments = [], polylines = {}, apiData = {}, times = [], selectedPoly = null;
    let currentVar = 'temperature', currentStrada = 'A90';
    let isPlaying = false, playInterval = null;
    let highlightGroup = L.layerGroup().addTo(map);
    let highlightFill = null;

    const loadingEl = document.getElementById('loading');
    const stradaSelect = document.getElementById('stradaSelect');
    const variabileSelect = document.getElementById('variabileSelect');
    const kmSearch = document.getElementById('kmSearch');
    const segmentListContainer = document.getElementById('segmentList');
    const playPauseBtn = document.getElementById('playPauseBtn');
    const timeSlider = document.getElementById('timeSlider');
    const btnGrafico = document.getElementById('btnGrafico');

    const AlertControl = L.Control.extend({
        onAdd: function (map) {
            const container = L.DomUtil.create('div', 'leaflet-control-alerts leaflet-control leaflet-bar');
            const link = L.DomUtil.create('a', '', container);
            link.id = 'alert-link';
            link.href = '#';
            link.title = 'Visualizza Allarmi';
            const badge = L.DomUtil.create('span', 'alert-badge', link);
            badge.id = 'alert-badge';
            L.DomEvent.on(link, 'click', L.DomEvent.stop).on(link, 'click', (ev) => {
                window.open(ev.currentTarget.href, '_blank');
            });
            return container;
        },
    });
    new AlertControl({ position: 'topleft' }).addTo(map);
    const alertLink = document.getElementById('alert-link');
    const alertBadge = document.getElementById('alert-badge');

    const normalizeKey = (str) => str ? str.replace(/[\s._()-]/g, "").toLowerCase() : '';
    const debounce = (fn, ms) => { let t; return (...args) => { clearTimeout(t); t = setTimeout(() => fn.apply(this, args), ms); }; };

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

    function renderLegend() {
        const lg = document.getElementById('legend');
        const scale = SCALES[currentVar];
        lg.innerHTML = `<div class="title">${variabileSelect.selectedOptions[0].text}</div>`;
        scale.steps.forEach((step, index) => {
            const labelText = `${step.label} (${scale.labels[index]} ${scale.unit})`;
            lg.innerHTML += `<div class="step"><div class="color-box" style="background:${step.color}"></div> ${labelText}</div>`;
        });
    }

    function pausePlayback() { if (!isPlaying) return; isPlaying = false; clearInterval(playInterval); playPauseBtn.innerHTML = '▶'; }
    function startPlayback() {
        if (isPlaying || times.length === 0) return;
        isPlaying = true; playPauseBtn.innerHTML = '❚❚';
        playInterval = setInterval(() => {
            let currentIndex = +timeSlider.value;
            let nextIndex = (currentIndex + 1) % times.length;
            updateMap(nextIndex, true);
        }, 1000);
    }

    async function fetchSegmentsData() {
        if (allSegments.length > 0) return;
        try {
            const res = await fetch('/static/jsons/tratti_strada_allineati.json');
            allSegments = await res.json();
        } catch (e) {
            console.error("Impossibile caricare i tratti stradali", e);
            alert("Errore critico: impossibile caricare la geometria dei tratti stradali.");
        }
    }

    function displaySegmentsAndList() {
        Object.values(polylines).forEach(p => map.removeLayer(p));
        polylines = {};
        const stradaLower = currentStrada.toLowerCase();
        const segmentsToDraw = allSegments.filter(t => t.nome.toLowerCase().includes(stradaLower));

        segmentsToDraw.forEach(tratto => {
            const normKey = normalizeKey(tratto.nome);
            const poly = L.polyline(tratto.punti.map(p => [p.lat, p.lon]), {
                renderer, color: COLORS.DEFAULT, weight: COLORS.DEFAULT_WEIGHT,
                nome: tratto.nome, key: normKey
            }).addTo(map).bindTooltip(tratto.nome, { direction: 'top', sticky: true }).on('click', (e) => handleSelection(e.target));
            polylines[normKey] = poly;
        });
        updateSearchList();
        if (BOUNDS[currentStrada] && !kmSearch.value) {
            map.fitBounds(BOUNDS[currentStrada]);
        }
    }

    function updateSearchList() {
        segmentListContainer.innerHTML = '';
        const filterText = kmSearch.value.trim().toLowerCase();
        if (!filterText) {
            segmentListContainer.style.display = 'none';
            return;
        }
        const stradaLower = currentStrada.toLowerCase();
        const segmentsForStrada = allSegments.filter(t => t.nome.toLowerCase().includes(stradaLower));
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
                const div = document.createElement('div');
                div.className = 'item';
                div.textContent = tratto.nome;
                div.onclick = () => {
                    kmSearch.value = tratto.nome;
                    segmentListContainer.style.display = 'none';
                    const targetPoly = Object.values(polylines).find(p => p.options.nome === tratto.nome);
                    if (targetPoly) {
                        map.fitBounds(targetPoly.getBounds().pad(0.1));
                        handleSelection(targetPoly);
                    }
                };
                segmentListContainer.appendChild(div);
            });
            segmentListContainer.style.display = 'block';
        } else {
            segmentListContainer.style.display = 'none';
        }
    }

    function handleSelection(poly) {
        highlightGroup.clearLayers();
        highlightFill = null;
        if (selectedPoly) {
            selectedPoly.setStyle({ opacity: 1 });
        }
        if (selectedPoly === poly) {
            selectedPoly = null;
            kmSearch.value = '';
            btnGrafico.style.display = 'none';
            updateMapColors();
            return;
        }
        selectedPoly = poly;
        poly.setStyle({ opacity: 0 });
        const latlngs = poly.getLatLngs();
        const currentVal = getCurrentValue(poly);
        const initialColor = getColorForValue(currentVal);
        const border = L.polyline(latlngs, { color: COLORS.SELECTED_BLUE, weight: COLORS.SELECTED_WEIGHT, opacity: 1, interactive: false });
        highlightFill = L.polyline(latlngs, { color: initialColor, weight: COLORS.SELECTED_WEIGHT / 2, opacity: 1, interactive: false });
        highlightGroup.addLayer(border).addLayer(highlightFill);
        highlightGroup.bindTooltip(poly.getTooltip().getContent(), { direction: 'top', sticky: true });
        kmSearch.value = poly.options.nome;
        btnGrafico.style.display = 'block';
    }

    window.visualizzaGraficoPrevisionale = function () {
        if (!selectedPoly) { return alert("Seleziona prima un tratto dalla mappa."); }
        const nomeTratto = selectedPoly.options.nome;
        window.open(`/grafico?tratto=${encodeURIComponent(nomeTratto)}&modalita=previsionale`, '_blank');
    }

    let pollingInterval = null;
    let currentPageTimestamp = null;

    function setupPolling(strada, initialTimestamp) {
        const POLLING_INTERVAL_MS = 30000;
        const statusElement = document.getElementById('update-status');
        if (pollingInterval) { clearInterval(pollingInterval); }
        if (!strada || !initialTimestamp) {
            statusElement.textContent = "Informazioni per l'aggiornamento automatico mancanti.";
            return;
        }
        currentPageTimestamp = initialTimestamp;
        statusElement.textContent = "Controllo aggiornamenti automatico attivo.";
        const check = () => {
            fetch(`/api/check_update_mappa?strada=${encodeURIComponent(strada)}`)
                .then(response => {
                    if (!response.ok) throw new Error('Risposta del server non valida.');
                    return response.json();
                })
                .then(data => {
                    if (data.latest_update) {
                        const latestTimestamp = data.latest_update;
                        if (new Date(latestTimestamp) > new Date(currentPageTimestamp)) {
                            statusElement.textContent = "Nuovi dati disponibili! Aggiornamento in corso...";
                            loadData();
                        } else {
                            statusElement.textContent = "I dati visualizzati sono i più recenti.";
                        }
                    } else {
                        statusElement.textContent = "Nessun dato previsionale trovato per questa strada.";
                    }
                })
                .catch(err => {
                    console.error("Errore durante il polling degli aggiornamenti:", err);
                    statusElement.textContent = "Errore di connessione durante la verifica di nuovi dati.";
                });
        };
        pollingInterval = setInterval(check, POLLING_INTERVAL_MS);
    }

    async function loadData() {
        pausePlayback();
        loadingEl.style.display = 'block';
        const url = `/api/mappa/previsionale?strada=${encodeURIComponent(currentStrada)}`;
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`Errore API: ${res.status}`);
            const json = await res.json();
            if (json.errore) throw new Error(json.errore);

            const lastUpdate = json.last_update_timestamp;
            if (lastUpdate && lastUpdate === currentPageTimestamp) {
                document.getElementById('update-status').textContent = "I dati visualizzati sono i più recenti.";
                loadingEl.style.display = 'none';
                return;
            }

            const allTimes = json.times || [];
            const now = new Date();
            const limitTime = new Date(now.getTime() + 73 * 60 * 60 * 1000);
            times = allTimes.filter(t => new Date(t) <= limitTime);
            apiData = json.data || {};
            renderTimeline(0);
            updateMap(0, true);
            if (lastUpdate) { setupPolling(currentStrada, lastUpdate); }
        } catch (error) {
            console.error(`Errore caricamento dati:`, error);
            times = []; apiData = {};
            renderTimeline(0);
            document.getElementById('update-status').textContent = "Errore nel caricamento dei dati.";
        } finally {
            loadingEl.style.display = 'none';
        }
    }

    function renderTimeline(startIndex = 0) {
        const dayLabelsContainer = document.getElementById('dayLabels');
        dayLabelsContainer.innerHTML = '';

        if (times.length === 0) {
            timeSlider.style.display = 'none';
            document.getElementById('dayLabels-wrapper').style.display = 'none';
            playPauseBtn.disabled = true;
            document.getElementById('currentTime').textContent = "--";
            return;
        }

        document.getElementById('dayLabels-wrapper').style.display = 'flex';
        playPauseBtn.disabled = false;
        timeSlider.style.display = 'block';

        times.forEach((time, index) => {
            const hourSlot = document.createElement('div');
            hourSlot.className = 'hour-slot';
            const currentTime = new Date(time);
            const prevTime = index > 0 ? new Date(times[index - 1]) : null;
            const isNewDay = !prevTime || currentTime.getDate() !== prevTime.getDate();
            const isThreeHourMark = currentTime.getHours() % 3 === 0;
            const markerContainer = document.createElement('div');
            markerContainer.className = 'timeline-marker';
            if (isNewDay) {
                const dayLabel = document.createElement('div');
                dayLabel.className = 'timeline-day-label';
                dayLabel.id = `day-label-${currentTime.getDate()}`;
                dayLabel.textContent = currentTime.toLocaleDateString('it-IT', { weekday: 'short', day: 'numeric' });
                markerContainer.appendChild(dayLabel);
            }
            const tickContainer = document.createElement('div');
            tickContainer.className = 'timeline-tick-container';
            if (isThreeHourMark) {
                const hourLabel = document.createElement('div');

                hourLabel.className = 'timeline-hour-label';
                hourLabel.textContent = currentTime.getHours().toString().padStart(2, '0');
                const tick = document.createElement('div');

                tick.className = 'timeline-tick major';
                tickContainer.appendChild(tick);
                tickContainer.appendChild(hourLabel);

            } else {
                const tick = document.createElement('div');
                tick.className = 'timeline-tick';
                tickContainer.appendChild(tick);
            }
            markerContainer.appendChild(tickContainer);
            hourSlot.appendChild(markerContainer);
            dayLabelsContainer.appendChild(hourSlot);
        });

        timeSlider.min = 0;
        timeSlider.max = times.length > 0 ? times.length - 1 : 0;
        timeSlider.value = startIndex;
    }

    function updateMap(idx, updateSlider = false) {
        if (!times || !times[idx]) return;
        if (updateSlider) timeSlider.value = idx;
        const dt = new Date(times[idx]);
        document.getElementById('currentTime').textContent = dt.toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' });
        document.querySelectorAll('.timeline-day-label').forEach(el => el.classList.remove('active'));
        const activeDayLabel = document.getElementById(`day-label-${dt.getDate()}`);
        if (activeDayLabel) activeDayLabel.classList.add('active');
        updateMapColors();
    }

    function updateMapColors() {
        Object.values(polylines).forEach(poly => {
            if (poly !== selectedPoly) {
                const val = getCurrentValue(poly);
                updatePolylineColor(poly, val);
            }
        });
        if (selectedPoly) {
            const val = getCurrentValue(selectedPoly);
            const newColor = getColorForValue(val);
            if (highlightFill) {
                highlightFill.setStyle({ color: newColor });
            }
            const tooltipText = buildTooltipText(selectedPoly, val);
            highlightGroup.unbindTooltip();
            highlightGroup.bindTooltip(tooltipText, { direction: 'top', sticky: true });
        }
    }

    function buildTooltipText(poly, val) {
        const varLabel = variabileSelect.selectedOptions[0].text.split(' (')[0];
        const unit = SCALES[currentVar].unit;
        const valueText = val !== null ? Number(val).toFixed(1) + ' ' + unit : 'Dato non disponibile';
        return `<b>${poly.options.nome}</b><br>${varLabel}: ${valueText}`;
    }

    function updatePolylineColor(poly, val) {
        const tooltipText = buildTooltipText(poly, val);
        poly.setTooltipContent(tooltipText);
        const color = val !== null ? getColorForValue(val) : COLORS.DEFAULT;
        poly.setStyle({ color: color, weight: COLORS.DEFAULT_WEIGHT, opacity: 1 });
    }

    function getCurrentValue(poly) {
        const idx = +timeSlider.value;
        if (!times[idx] || !apiData) return null;
        const normName = poly.options.key;
        const recordsForSegment = apiData[normName];
        if (!recordsForSegment) return null;
        const recordForTime = recordsForSegment.find(r => r.time === times[idx]);
        return recordForTime ? recordForTime[currentVar] : null;
    }

    function getColorForValue(v) {
        const sc = SCALES[currentVar];
        if (v === null || v === undefined) return COLORS.DEFAULT;
        for (const step of sc.steps) { if (v < step.value) return step.color; }
        return sc.steps[sc.steps.length - 1].color;
    }

    async function checkForAlerts() {
        try {
            const res = await fetch(`/api/allarmi?strada=${currentStrada}`);
            if (!res.ok) throw new Error('Risposta API non valida');
            const allarmi = await res.json();
            if (allarmi.length > 0) {
                alertBadge.textContent = allarmi.length;
                alertBadge.style.display = 'block';
            } else {
                alertBadge.style.display = 'none';
            }
        } catch (e) {
            console.error("Errore nel controllo allarmi:", e);
            alertBadge.style.display = 'none';
        }
    }

    async function handleStradaChange() {
        pausePlayback();
        if (pollingInterval) clearInterval(pollingInterval);
        currentPageTimestamp = null;
        currentStrada = stradaSelect.value;
        kmSearch.value = '';
        if (selectedPoly) { selectedPoly = null; highlightFill = null; }
        highlightGroup.clearLayers();
        btnGrafico.style.display = 'none';
        displaySegmentsAndList();
        await loadData();
        alertLink.href = `/allarmi?strada=${currentStrada}`;
        await checkForAlerts();
    }

    function handleVariabileChange() {
        pausePlayback();
        currentVar = variabileSelect.value;
        renderLegend();
        updateMapColors();
    }

    kmSearch.addEventListener('input', debounce(updateSearchList, 300));
    kmSearch.addEventListener('focus', updateSearchList);
    document.addEventListener('click', (e) => {
        if (!document.getElementById('search-container').contains(e.target)) {
            segmentListContainer.style.display = 'none';
        }
    });

    stradaSelect.onchange = handleStradaChange;
    variabileSelect.onchange = handleVariabileChange;
    playPauseBtn.onclick = () => { isPlaying ? pausePlayback() : startPlayback(); };
    timeSlider.oninput = debounce(e => { pausePlayback(); updateMap(+e.target.value); }, 50);

    (async () => {
        await fetchSegmentsData();
        renderLegend();
        await handleStradaChange();
    })();
});