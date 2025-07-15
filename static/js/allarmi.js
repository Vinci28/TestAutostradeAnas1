document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const strada = params.get('strada');
    const stradaNomeEl = document.getElementById('strada-nome');
    const loadingEl = document.getElementById('loading');
    const noAlertsEl = document.getElementById('no-alerts');
    const containerEl = document.getElementById('alerts-container');

    const icons = {
        gelo: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00338D"><path d="M12 2a1 1 0 0 1 .993.883L13 3v1.332a8.999 8.999 0 0 1 3.999 2.515l.09.098.941.942a1 1 0 0 1-1.32 1.497l-.094-.083-.942-.941a7 7 0 0 0-2.673-1.842L13 7.583V10a1 1 0 0 1-.883.993L12 11H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h7zm-1 2H6v4h5V4zm5.536 8.464a1 1 0 0 1 1.497 1.32l-.083.094-1.414 1.414a1 1 0 0 1-1.497-1.32l.083-.094 1.414-1.414zm-10.82-2.142a1 1 0 0 1 1.32-1.497l.094.083L8.5 10.322a7 7 0 0 0-1.842 2.673l-.083.094-.941.942a1 1 0 0 1-1.497-1.32l.083-.094.941-.941zM12 13a1 1 0 0 1 .993.883L13 14v7a1 1 0 0 1-1.993.117L11 21v-7a1 1 0 0 1 1-1z"/></svg>`,
        vento: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00338D"><path d="M12.5 4a1 1 0 0 1 1 1v.5a2.5 2.5 0 1 0 5 0V5a1 1 0 1 1 2 0v.5a4.5 4.5 0 1 1-9 0V5a1 1 0 0 1 1-1zM3 10.5a2.5 2.5 0 1 0 5 0v-.5a1 1 0 1 1 2 0v.5a4.5 4.5 0 1 1-9 0v-.5a1 1 0 1 1 2 0v.5zM11.5 16a1 1 0 0 1 1 1v.5a2.5 2.5 0 1 0 5 0V17a1 1 0 1 1 2 0v.5a4.5 4.5 0 1 1-9 0V17a1 1 0 0 1 1-1z"/></svg>`,
        pioggia: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#00338D"><path d="M12 2.003a9.5 9.5 0 1 1 0 19a9.5 9.5 0 0 1 0-19Zm0 2a7.5 7.5 0 0 0-7.435 6.471l-.053.256-.012.11a1 1 0 0 1-1.993-.117A9.5 9.5 0 0 1 12 2.003Zm2.5 13.5a1 1 0 1 1-1.414 1.414L12 15.832l-1.086 1.085a1 1 0 1 1-1.414-1.414L10.586 14.42l-1.086-1.085a1 1 0 1 1 1.414-1.414L12 12.993l1.086-1.086a1 1 0 1 1 1.414 1.414L13.414 14.42l1.086 1.085Z"/></svg>`
    };

    if (strada) {
        stradaNomeEl.textContent = strada.toUpperCase();
        try {
            const response = await fetch(`/api/allarmi?strada=${strada}`);
            if (!response.ok) throw new Error(`Errore API: ${response.status}`);
            const allarmi = await response.json();

            loadingEl.style.display = 'none';

            if (allarmi.length === 0) {
                noAlertsEl.style.display = 'block';
            } else {
                allarmi.forEach(alert => {
                    const card = document.createElement('div');
                    card.className = `alert-card ${alert.tipo}`;

                    const dataOra = new Date(alert.time).toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });

                    card.innerHTML = `
                        <div class="alert-header">
                            <div class="alert-icon">${icons[alert.tipo] || ''}</div>
                            <span class="alert-title">${alert.variabile}</span>
                        </div>
                        <div class="alert-body">
                            <p><strong>Tratto:</strong> ${alert.tratto}</p>
                            <p><strong>Data e Ora:</strong> ${dataOra}</p>
                            <p><strong>Valore Rilevato:</strong> <span class="alert-value">${alert.valore}</span></p>
                        </div>
                    `;
                    containerEl.appendChild(card);
                });
            }
        } catch (error) {
            loadingEl.textContent = `Errore nel caricamento degli allarmi: ${error.message}`;
        }
    } else {
        loadingEl.style.display = 'none';
        noAlertsEl.textContent = 'Strada non specificata. Torna alla mappa e riprova.';
        noAlertsEl.style.display = 'block';
    }
});