# MUSA - Software Synthesizer

MUSA is a desktop synthesizer and sample-based instrument built with Python, PyQt6, NumPy, and sounddevice. It generates waveform, additive, and FM sounds, and plays WAV samples across the keyboard with ADSR, filters, LFO, chords, recording, and presets.

[Apri il manuale d'uso](./MANUALE.md) per istruzioni dettagliate su avvio, tastiera, MIDI, sintesi, preset, campioni WAV, registrazione e risoluzione dei problemi.

## Stato attuale dell'app

L'applicazione è ora completa per l'uso di base e include:

- caricamento di campioni WAV PCM mono/stereo
- trasposizione cromatica regolabile tramite nota MIDI radice
- fino a 32 voci polifoniche contemporanee
- sintesi a forme d'onda, additiva (1–16 parziali) e FM (rapporto e indice modulabili)
- Unison regolabile da 1 a 7 copie della sorgente per nota (oscillatore o WAV) e detune fino a 50 centesimi
- motore audio in tempo reale a 44.1 kHz con stream audio stabile
- controlli ADSR per attack, decay, sustain e release
- filtri low-pass, high-pass e band-pass
- modulazione LFO su pitch, volume e cutoff del filtro
- distorsione master selezionabile: soft clip, overdrive, hard clip, fuzz e bitcrusher
- controlli drive e mix dry/wet, salvati nei preset
- effetti master delay, chorus e riverbero con parametri salvati nei preset
- modalità armoniche singola, dyad e triad
- supporto per tastiera QWERTY su 4 ottave (da C3 a B6)
- ingresso MIDI da controller esterni con velocity, CC, pitch bend e aftertouch
- salvataggio e caricamento preset
- visualizzazione live con oscilloscopio e monitor di stato
- registrazione audio in formato WAV
- pulizia di startup/shutdown per evitare residui di stato

## Requisiti

- Python 3.9+
- PyQt6
- NumPy
- sounddevice
- mido
- python-rtmidi

## Installazione

```bash
python -m venv venv
.\venv\Scripts\Activate.ps1
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
├── audio/           # engine, mixer, oscillators, WAV samples, envelope, filter, effects
├── core/            # keyboard listener, MIDI input, note mapper, chord engine, preset manager
├── gui/             # main window, oscilloscope widget
└── recordings/      # file WAV generati dalla funzione Record
```

## Funzionalità principali

### Scale MIDI

Ottava 3 (48–59): 48 C3, 49 C#3, 50 D3, 51 D#3, 52 E3, 53 F3, 54 F#3, 55 G3, 56 G#3, 57 A3, 58 A#3, 59 B3

Ottava 4 (60–71): 60 C4, 61 C#4, 62 D4, 63 D#4, 64 E4, 65 F4, 66 F#4, 67 G4, 68 G#4, 69 A4, 70 A#4, 71 B4

Ottava 5 (72–83): 72 C5, 73 C#5, 74 D5, 75 D#5, 76 E5, 77 F5, 78 F#5, 79 G5, 80 G#5, 81 A5, 82 A#5, 83 B5

Ottava 6 (84–95): 84 C6, 85 C#6, 86 D6, 87 D#6, 88 E6, 89 F6, 90 F#6, 91 G6, 92 G#6, 93 A6, 94 A#6, 95 B6

### Campioni

- Premi **Load WAV sample…** e scegli un file WAV PCM.
- Imposta la nota MIDI radice corrispondente alla nota registrata nel WAV (A4/MIDI 69 per impostazione predefinita).
- Le note vengono trasposte rispetto alla radice; ADSR, filtro, LFO e polifonia continuano ad agire sul campione.
- Il campione non viene ripetuto in loop: al termine del file la voce resta silenziosa fino al rilascio dell'inviluppo.
- I preset memorizzano il percorso del campione e la nota radice; il file deve restare allo stesso percorso per poterlo ricaricare.

### Ingresso MIDI

- Note On/Off usa la velocity del controller e rispetta Harmonic Mode e Chord Type: una nota può quindi attivare una dyad o una triad.
- CC 1 (Modulation Wheel) controlla la profondità LFO; CC 7 il volume master; CC 74 il cutoff del filtro.
- Pitch bend agisce sulle note MIDI attive del canale, con un'escursione di ±2 semitoni.
- Channel Aftertouch agisce sulle note MIDI tenute del canale; Poly Aftertouch limita l'effetto alla nota indicata.
- Seleziona la porta MIDI nella scheda Engine / MIDI; premi Refresh per aggiornare i dispositivi disponibili.

### Controlli del suono

- ADSR: modella il profilo dinamico di ogni nota
- Filter: definisce il colore timbrico e la brillantezza del suono
- LFO: aggiunge movimento, vibrato, tremolo o sweep del filtro
- Distortion: modifica il timbro complessivo dopo la somma delle voci; drive regola l'intensità e mix bilancia segnale originale e distorto
- Delay master: aggiunge echi con tempo, feedback e mix regolabili; le impostazioni sono salvate nei preset
- Chorus master: arricchisce il suono con un ritardo modulato; rate, depth e mix sono regolabili e salvati nei preset
- Reverb master: aggiunge una coda ambientale; decay e mix sono regolabili e salvati nei preset
- Harmonic mode e chord type: trasformano una singola nota in accordi o arpeggi
- Engine, Waveform, parametri Additive/FM e Unison/Detune sono sempre visibili sotto le schede Audio Controls per modifiche live; Unison sovrappone fino a 7 sorgenti con livello normalizzato

### Interfaccia e controllo

- Pulsanti Start/Stop Audio e Record, selezione controller MIDI
- Slider master volume, ADSR, filtro, LFO, distorsione e monitor live; i controlli Engine, Waveform, Additive/FM e Unison/Detune restano sempre visibili sotto le schede Audio Controls
- Preset per salvare e caricare stati completi dell'app
- Nella finestra Hex, usa le frecce sinistra/destra per caricare il preset precedente o successivo.
- Oscilloscopio per vedere il waveform in tempo reale

## Sezione effetti delle singole feature implementate

Le seguenti funzioni modellano il suono dalla generazione delle oscillazioni fino agli effetti master e al monitoraggio:

- **Waveform:** definisce il contenuto armonico di partenza. Sine produce un tono essenziale; triangle aggiunge poche armoniche; square e sawtooth hanno più armoniche e risultano più brillanti. Il selettore cambia la forma d'onda delle nuove note.
- **Sintesi additiva:** somma da 1 a 16 parziali armoniche. Harmonic tilt attenua progressivamente le armoniche alte; a zero tutte le parziali hanno lo stesso peso.
- **Sintesi FM:** modula la frequenza della portante con un operatore sinusoidale. FM ratio regola il rapporto tra modulatore e portante; FM index controlla la profondità e la complessità delle bande laterali.
- **Unison e detune:** Unison voices imposta quante copie della sorgente suonano per ogni nota (1–7); Detune regola la massima differenza di intonazione in centesimi, distribuita simmetricamente tra le copie. Vale per oscillatori sintetici e campioni WAV, anche per le note ricevute via MIDI; le copie WAV hanno posizioni di lettura indipendenti. Il livello delle copie è normalizzato per non aumentare il volume quando si aggiungono voci; con Unison a 1 o detune a 0 il timbro resta neutro. I parametri sono salvati nei preset.
- **Distortion:** agisce sul segnale complessivo dopo la somma delle voci. Soft Clip e Overdrive saturano gradualmente, Hard Clip taglia i picchi, Fuzz crea una saturazione più aspra e Bitcrusher riduce la risoluzione digitale. Drive aumenta la quantità di saturazione; Mix bilancia segnale originale ed elaborato.
- **Delay:** aggiunge ripetizioni temporizzate del segnale. Time stabilisce l'intervallo tra gli echi, Feedback quanta parte dell'eco viene rimandata in ingresso e quindi quante ripetizioni si odono; Mix regola il livello degli echi rispetto al suono diretto.
- **Chorus:** miscela al suono copie con ritardo e intonazione leggermente variabili, dando una sensazione di maggiore ampiezza e densità. Rate imposta la velocità della modulazione, Depth la variazione del ritardo e Mix la quantità di chorus.
- **Reverb:** aggiunge una coda diffusa che simula le riflessioni di un ambiente. Decay controlla quanto a lungo permane la coda; Mix ne regola il livello rispetto al segnale diretto.
- **Master Volume:** controlla il livello complessivo in uscita senza cambiare il bilanciamento delle singole note.
- **Attack:** determina il tempo necessario perché una nota raggiunga il livello iniziale. Valori brevi rendono l'attacco immediato; valori lunghi producono un ingresso graduale.
- **Decay:** imposta il tempo con cui il volume scende dal picco iniziale al livello di sustain, dopo la fase di attack.
- **Sustain:** stabilisce il livello mantenuto finché il tasto resta premuto. A differenza di attack, decay e release, è un livello e non una durata.
- **Release:** definisce quanto impiega la nota a spegnersi dopo il rilascio del tasto. Un release lungo prolunga la coda dell'inviluppo.
- **Filter Type:** seleziona un filtro low-pass (attenua le frequenze sopra il cutoff), high-pass (attenua quelle sotto) o band-pass (lascia passare soprattutto la zona attorno al cutoff).
- **Cutoff:** sposta la frequenza di taglio o il centro della banda; aumentarlo rende il low-pass più brillante, ma rende più sottile l'high-pass.
- **Resonance:** enfatizza la zona vicina al cutoff. La scala 0–100 corrisponde a Q circa 0,71–10; valori alti creano un picco più stretto e possono aumentare sensibilmente il livello vicino al cutoff.
- **LFO Target:** sceglie il parametro modulato periodicamente: pitch per il vibrato, volume per il tremolo o cutoff per un movimento del filtro.
- **LFO Rate:** controlla la velocità della modulazione. Rate bassi creano variazioni lente; rate alti producono oscillazioni più rapide.
- **LFO Depth:** regola l'ampiezza della variazione applicata al parametro selezionato; a zero l'effetto del LFO è assente.
- **Harmonic Mode / Chord Type:** decide quante note vengono generate da un singolo tasto. Single suona la nota originale; dyad e triad aggiungono intervalli per formare accordi, con qualità selezionabile tramite Chord Type. Vale anche per le note ricevute via MIDI.
- **MIDI Velocity e controlli espressivi:** la velocity determina l'intensità iniziale della nota. CC 1 controlla la profondità LFO, CC 7 il volume master e CC 74 il cutoff. Pitch bend varia l'intonazione delle note MIDI attive fino a ±2 semitoni; channel aftertouch agisce sulle note tenute del canale e poly aftertouch sulla singola nota indicata.
- **Presets:** salvano e ripristinano i parametri sonori, inclusi effetti master e impostazioni di modulazione, per richiamare rapidamente configurazioni coerenti.
- **Record:** registra l'uscita audio del motore in un file WAV. La registrazione include le note e gli effetti prodotti durante la cattura.
- **Oscilloscope:** visualizza il segnale audio nel tempo per osservare forma d'onda, variazioni di livello e attività durante l'esecuzione.

## Sviluppi futuri possibili

### Miglioramenti a breve termine

- MIDI Learn per associare CC personalizzati ai controlli e salvare le mappature nei preset.
- Aggiungere riproduzione suono in loop con registrazione
- Permettere di caricare più suoni da preset con switch 
- Aggiungere griglia 4x3 con suoni diversificati per 6 gruppi  

### Evoluzioni del motore sonoro

- Portamento e legato per transizioni fluide tra le note e modalità monofonica.

## Roadmap ottimizzazione audio

Priorità: ridurre underrun e ritardi dell'audio in uscita, verificando ogni intervento con misure ripetibili prima e dopo.

Il mixer applica inoltre un limite di picco al segnale finale, dopo delay, chorus e riverbero. Questo evita il clipping digitale quando più voci si sommano in fase o gli effetti aumentano il livello; il recupero del guadagno è graduale.

1. **Misurazione del callback (implementata):** misura il tempo completo di elaborazione del callback (inclusi effetti, copia per l'oscilloscopio e registrazione, se attiva), raccoglie media, P95 e massimo e confronta la durata con il budget nominale dei frame richiesti. Conta separatamente i callback oltre budget e gli underrun segnalati dal dispositivo. Il monitor mostra P95/budget, carico percentuale, media/massimo e superamenti; la finestra P95 è limitata a 512 callback e il calcolo statistico avviene fuori dal thread audio.
2. **Baseline ripetibile (implementata):** eseguire `python benchmark_audio.py` per confrontare il percorso waveform storico a Unison=1 (1 e 8 voci) con Unison 3/7, additiva/FM, effetti e registrazione on/off. Usa sample rate 44,1 kHz, buffer 128, warmup e riporta media, P95, massimo e deadline miss rispetto al budget. Per misure più stabili, aumentare `--iterations` (per esempio 512) e `--repeats` (per esempio 3).
3. **Registrazione WAV fuori dal callback (implementata):** il callback converte e accoda i blocchi in una coda limitata, mentre un worker dedicato scrive il file e lo chiude. Se la coda si satura, la registrazione si interrompe senza bloccare l'audio e l'errore viene mostrato nella barra di stato al termine della registrazione.
4. **Ottimizzazione del DSP misurato (in corso):** profilare filtro per-voce, sintesi additiva/FM, Unison e delay/chorus/reverb; intervenire prima sul percorso con maggior costo effettivo, riducendo cicli Python e allocazioni solo dove le misure confermano un beneficio. Primo intervento sul filtro per-voce: il dispatch LP/HP è stato spostato fuori dal ciclo per campione, mantenendo la ricorrenza esistente. Nel microbenchmark locale con 8 filtri, blocchi da 128 campioni e 1000 iterazioni, il tempo mediano è sceso da 5,73 s a 3,37 s (circa -41%; dato indicativo e dipendente dall'hardware).
5. **Verifica comparativa e qualità:** ripetere la baseline, controllare che P95 e deadline migliorino nelle configurazioni pesanti e verificare che forma d'onda, inviluppi, effetti, MIDI e recording restino corretti.

## Licenza

MIT
