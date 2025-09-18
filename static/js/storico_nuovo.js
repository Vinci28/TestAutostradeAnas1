// Aggiunge un listener per eseguire il codice solo dopo che il DOM è stato completamente caricato
document.addEventListener('DOMContentLoaded', () => {
    // Definisce i limiti (bounds) della mappa per ciascuna strada
    const bounds = {
        A90: [[41.8, 12.3], [42.0, 12.6]],
        SS51: [[46.3, 12.2], [46.7, 12.4]],
        SS675: [[42.4, 12.0], [42.6, 12.3]]
    };
    // Definisce i layer base della mappa (es. Mappa Grigia, Mappa Standard, ecc.)
    const baseMaps = {
        "Mappa Grigia": L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '&copy; OpenStreetMap &copy; CARTO' }),
        "Mappa Standard": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }),
        "Mappa Satellite": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { attribution: 'Tiles &copy; Esri' })
    };
    // Crea un renderer canvas per migliorare le performance di disegno delle polilinee
    const renderer = L.canvas({ padding: 0.5 });
    // Inizializza la mappa con le opzioni di controllo e il layer iniziale
    const map = L.map('map', { preferCanvas: true, renderer, zoomControl: false, layers: [baseMaps["Mappa Grigia"]] }).setView([42, 12.5], 7);
    // Aggiunge i controlli di zoom e di selezione dei layer alla mappa
    L.control.zoom({ position: 'topleft' }).addTo(map);
    L.control.layers(baseMaps, null, { position: 'topleft' }).addTo(map);

    // Variabili per memorizzare i dati dei segmenti, le polilinee sulla mappa e il tratto selezionato
    let segmentsData = null, polylines = {}, selectedTratto = null;
    let currentStrada = 'A90';

    // Riferimenti agli elementi del DOM
    const stradaSelect = document.getElementById('stradaSelect');
    const kmSearch = document.getElementById('kmSearch');
    const segmentListContainer = document.getElementById('segmentList');
    const selectedTrattoDisplay = document.getElementById('selected-tratto-display');
    // Colori per lo stato predefinito e selezionato dei tratti sulla mappa
    const COLORS = { DEFAULT: '#00338D', SELECTED: '#FFC100' };

    // Funzione di debounce per limitare la frequenza di esecuzione della ricerca durante la digitazione
    function debounce(fn, ms) {
        let t;
        return (...args) => {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), ms);
        };
    }

    // Funzioni per l'analisi dei chilometri dai nomi dei tratti (es. "Km 12+345")
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

    // Funzione per caricare i dati dei tratti da un file JSON
    async function fetchSegmentsData() {
        if (!segmentsData) {
            segmentsData = await fetch('/static/jsons/tratti_strada_allineati.json').then(r => r.json());
        }
    }

    // Funzione principale per visualizzare i tratti sulla mappa e nella lista
    function displaySegments() {
        // Rimuove tutte le polilinee esistenti dalla mappa
        Object.values(polylines).forEach(p => map.removeLayer(p));
        polylines = {};
        segmentListContainer.innerHTML = '';

        const filterText = kmSearch.value.trim().toLowerCase();
        const stradaLower = currentStrada.toLowerCase();
        // Filtra i segmenti per la strada corrente
        const segmentsForStrada = segmentsData.filter(t => t.nome.toLowerCase().includes(stradaLower));
        let segmentsToShow;

        // Logica per filtrare i tratti in base al testo di ricerca
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
            // Combina i risultati della ricerca testuale e della ricerca per intervallo KM
            const combined = new Map();
            textResults.forEach(t => combined.set(t.nome, t));
            intelligentResults.forEach(t => combined.set(t.nome, t));
            segmentsToShow = Array.from(combined.values());
        }

        // Aggiunge le polilinee e la lista dei segmenti all'interfaccia
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

        // Adatta la vista della mappa ai limiti della strada selezionata
        if (filterText === '' && bounds[currentStrada]) {
            map.fitBounds(bounds[currentStrada]);
        }

        // Evidenzia il tratto se è stato selezionato in precedenza
        if (selectedTratto && polylines[selectedTratto]) {
            polylines[selectedTratto].setStyle({ color: COLORS.SELECTED, weight: 7 }).bringToFront();
        }

        updateUI();
    }

    // Gestore per l'evento di click su un tratto
    function handleTrattoClick(e) {
        const clickedPoly = e.target;
        const nomeTratto = clickedPoly.options.nome;

        // Resetta lo stile del tratto precedentemente selezionato
        if (selectedTratto && polylines[selectedTratto]) {
            polylines[selectedTratto].setStyle({ color: COLORS.DEFAULT, weight: 5 });
        }
        // Imposta il nuovo tratto selezionato e ne cambia lo stile
        selectedTratto = nomeTratto;
        clickedPoly.setStyle({ color: COLORS.SELECTED, weight: 7 });
        clickedPoly.bringToFront();
        kmSearch.value = nomeTratto;

        updateUI();

        // Ottiene le date dai campi di input
        const startDate = document.getElementById('startDate').value;
        const endDate = document.getElementById('endDate').value;

        // Prepara i parametri URL per il reindirizzamento alla pagina dei grafici
        const params = new URLSearchParams();
        params.append('tratto', nomeTratto);
        params.append('modalita', 'storico');

        if (startDate) {
            params.append('start_date', startDate);
        }
        if (endDate) {
            params.append('end_date', endDate);
        }

        // Apre la pagina dei grafici in una nuova scheda
        window.open(`/grafico?${params.toString()}`, '_blank');
    }

    // Aggiorna l'interfaccia utente in base al tratto selezionato
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

    // Gestisce il cambio di strada nel selettore a tendina
    stradaSelect.onchange = async function () {
        currentStrada = this.value;
        kmSearch.value = '';
        selectedTratto = null;
        segmentListContainer.style.display = 'none';
        await fetchSegmentsData();
        displaySegments();
    };

    // Ascolta l'input di ricerca con un debounce per evitare chiamate troppo frequenti
    kmSearch.addEventListener('input', debounce(() => {
        segmentListContainer.style.display = kmSearch.value.length > 0 ? 'block' : 'none';
        displaySegments();
    }, 300));

    // Funzione asincrona di avvio che viene eseguita al caricamento della pagina
    (async () => {
        await fetchSegmentsData();
        displaySegments();
        updateUI();
    })();
});