# MUSA - Software Synthesizer

MUSA is a desktop sample-based instrument built with Python, PyQt6, NumPy, and sounddevice. It plays WAV samples across the keyboard, with ADSR, filters, LFO, chords, recording, and presets.

## Stato attuale dell'app

L'applicazione è ora completa per l'uso di base e include:

- caricamento di campioni WAV PCM mono/stereo
- trasposizione cromatica regolabile tramite nota MIDI radice
- fino a 32 voci polifoniche contemporanee
- motore audio in tempo reale a 44.1 kHz con stream audio stabile
- controlli ADSR per attack, decay, sustain e release
- filtri low-pass, high-pass e band-pass
- modulazione LFO su pitch, volume e cutoff del filtro
- modalità armoniche singola, dyad e triad
- supporto per tastiera QWERTY su 4 ottave (da C3 a B6)
- salvataggio e caricamento preset
- visualizzazione live con oscilloscopio e monitor di stato
- registrazione audio in formato WAV
- pulizia di startup/shutdown per evitare residui di stato

## Requisiti

- Python 3.9+
- PyQt6
- NumPy
- sounddevice

## Installazione

```bash
python -m venv venv
.
\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Esecuzione

```bash
python main.py
```

## Struttura del progetto

```text
synthwave-exp/
├── main.py
├── requirements.txt
├── README.md
├── audio/           # engine, mixer, WAV sample voices, envelope, filter, LFO
├── core/            # keyboard listener, note mapper, chord engine, preset manager
├── gui/             # main window, oscilloscope widget
└── recordings/      # file WAV generati dalla funzione Record
```

## Funzionalità principali

### Campioni

- Premi **Load WAV sample…** e scegli un file WAV PCM.
- Imposta la nota MIDI radice corrispondente alla nota registrata nel WAV (A4/MIDI 69 per impostazione predefinita).
- Le note vengono trasposte rispetto alla radice; ADSR, filtro, LFO e polifonia continuano ad agire sul campione.
- Il campione non viene ripetuto in loop: al termine del file la voce resta silenziosa fino al rilascio dell'inviluppo.
- I preset memorizzano il percorso del campione e la nota radice; il file deve restare allo stesso percorso per poterlo ricaricare.

### Controlli del suono

- ADSR: modella il profilo dinamico di ogni nota
- Filter: definisce il colore timbrico e la brillantezza del suono
- LFO: aggiunge movimento, vibrato, tremolo o sweep del filtro
- Harmonic mode e chord type: trasformano una singola nota in accordi o arpeggi

### Interfaccia e controllo

- Pulsanti Start/Stop Audio e Record
- Slider master volume, ADSR, filtro, LFO e monitor live
- Preset per salvare e caricare stati completi dell'app
- Oscilloscopio per vedere il waveform in tempo reale

## Sezione effetti delle singole feature implementate

Di seguito i principali effetti sonori e visivi delle feature regolabili dalla GUI:

- Waveform: cambia il timbro di base della sintesi, da un suono caldo e puro a uno più brillante o aggressivo.
- Master Volume: regola il livello generale dell'uscita audio.
- Attack: controlla quanto rapidamente la nota sale al massimo volume.
- Decay: determina quanto rapidamente il suono scende dal picco al livello di sustain.
- Sustain: imposta il livello mantenuto mentre la nota resta premuta.
- Release: definisce il tempo con cui il suono si spegne quando la nota viene rilasciata.
- Filter Type: sceglie il tipo di filtraggio, modificando lo spettro sonoro in modo diverso a seconda del tipo selezionato.
- Cutoff: decide quali frequenze vengono lasciate passare o tagliate.
- Resonance: enfatizza la zona attorno al cutoff, creando un suono più caratteristico o più "sibilante".
- LFO Target: decide se il movimento modulante interessa pitch, volume o filtro.
- LFO Rate: aumenta o diminuisce la velocità della modulazione.
- LFO Depth: controlla l'intensità della modulazione applicata.
- Harmonic Mode / Chord Type: trasforma una singola nota in una sonorità più ricca, da una nota singola a accordi.
- Presets: permettono di salvare e richiamare rapidamente configurazioni complete di suono.
- Record: cattura l'output audio corrente in un file WAV per ascolto o condivisione.
- Oscilloscope: mostra visivamente il waveform in tempo reale, utile per monitorare il segnale e capire il comportamento del synth.

## Sviluppi futuri possibili

- MIDI input esterno
- effetti aggiuntivi (delay, reverb, chorus)
- sintetizzatori additivi o FM
- supporto per preset più avanzati e import/export

## Licenza

MIT
