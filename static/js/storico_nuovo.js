document.addEventListener('DOMContentLoaded', () => {
    const bounds = {
        A90: [[41.8, 12.3], [42.0, 12.6]],
        SS51: [[46.3, 12.2], [46.7, 12.4]],
        SS675: [[42.4, 12.0], [42.6, 12.3]]
    };
    const baseMaps = {
        "Mappa Grigia": L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '&copy; OpenStreetMap &copy; CARTO' }),
        "Mappa Standard": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }),
        "Mappa Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri' })
    };
    const renderer = L.canvas({ padding: 0.5 });
    const map = L.map('map', { preferCanvas: true, renderer, zoomControl: false, layers: [baseMaps["Mappa Grigia"]] }).setView([42, 12.5], 7);
    L.control.zoom({ position: 'topleft' }).addTo(map);
    L.control.layers(baseMaps, null, { position: 'topleft' }).addTo(map);

    let segmentsData = null, polylines = {}, selectedTratto = null;
    let currentStrada = 'A90';

    const stradaSelect = document.getElementById('stradaSelect');
    const kmSearch = document.getElementById('kmSearch');
    const segmentListContainer = document.getElementById('segmentList');
    const selectedTrattoDisplay = document.getElementById('selected-tratto-display');
    const COLORS = { DEFAULT: '#00338D', SELECTED: '#FFC100' };

    function debounce(fn, ms) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }

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

    async function fetchSegmentsData() {
        if (!segmentsData) {
            segmentsData = await fetch('/static/jsons/tratti_strada_allineati.json').then(r => r.json());
        }
    }

    function displaySegments() {
        Object.values(polylines).forEach(p => map.removeLayer(p));
        polylines = {};
        segmentListContainer.innerHTML = '';

        const filterText = kmSearch.value.trim().toLowerCase();
        const stradaLower = currentStrada.toLowerCase();
        const segmentsForStrada = segmentsData.filter(t => t.nome.toLowerCase().includes(stradaLower));
        let segmentsToShow;

        if (!filterText) {
            segmentsToShow = segmentsForStrada;
        } else {
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
            segmentsToShow = Array.from(combined.values());
        }

        segmentsToShow.forEach(tratto => {
            const poly = L.polyline(tratto.punti.map(p => [p.lat, p.lon]), { renderer, color: COLORS.DEFAULT, weight: 5, nome: tratto.nome })
                .addTo(map).bindTooltip(tratto.nome, { direction: 'top', sticky: true }).on('click', handleTrattoClick);
            polylines[tratto.nome] = poly;

            const div = document.createElement('div');
            div.className = 'item';
            div.textContent = tratto.nome;
            div.onclick = () => {
                handleTrattoClick({ target: poly });
                segmentListContainer.style.display = 'none';
            };
            segmentListContainer.appendChild(div);
        });

        if (filterText === '' && bounds[currentStrada]) {
            map.fitBounds(bounds[currentStrada]);
        }

        if (selectedTratto && polylines[selectedTratto]) {
            polylines[selectedTratto].setStyle({ color: COLORS.SELECTED, weight: 7 }).bringToFront();
        }

        updateUI();
    }

    function handleTrattoClick(e) {
        const clickedPoly = e.target;
        const nomeTratto = clickedPoly.options.nome;

        if (selectedTratto && polylines[selectedTratto]) {
            polylines[selectedTratto].setStyle({ color: COLORS.DEFAULT, weight: 5 });
        }
        selectedTratto = nomeTratto;
        clickedPoly.setStyle({ color: COLORS.SELECTED, weight: 7 });
        clickedPoly.bringToFront();
        kmSearch.value = nomeTratto;

        updateUI();

        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        const params = new URLSearchParams();
        params.append('tratto', nomeTratto);
        params.append('modalita', 'storico');

        if (startDate) {
            params.append('start_date', startDate);
        }
        if (endDate) {
            params.append('end_date', endDate);
        }

        window.open(`/grafico?${params.toString()}`, '_blank');
    }

    function updateUI() {
        if (selectedTratto) {
            selectedTrattoDisplay.textContent = selectedTratto;
            selectedTrattoDisplay.style.fontStyle = 'normal';
            selectedTrattoDisplay.style.color = '#111';
        } else {
            selectedTrattoDisplay.textContent = 'Nessun tratto selezionato';
            selectedTrattoDisplay.style.fontStyle = 'italic';
            selectedTrattoDisplay.style.color = '#495057';
        }
    }

    stradaSelect.onchange = async function () {
        currentStrada = this.value;
        kmSearch.value = '';
        selectedTratto = null;
        segmentListContainer.style.display = 'none';
        await fetchSegmentsData();
        displaySegments();
    };

    kmSearch.addEventListener('input', debounce(() => {
        segmentListContainer.style.display = kmSearch.value.length > 0 ? 'block' : 'none';
        displaySegments();
    }, 300));


    (async () => {
        await fetchSegmentsData();
        displaySegments();
        updateUI();
    })();
});