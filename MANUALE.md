# Manuale d'uso MUSA SynthWave

MUSA è un sintetizzatore desktop: genera suoni, riproduce campioni WAV e riceve note da tastiera o da un controller MIDI. Questo manuale descrive l'interfaccia e il comportamento attuali del programma.

## 1. Avvio

### Requisiti

- Python 3.9 o superiore
- Un dispositivo audio disponibile
- Per usare un controller MIDI: una porta MIDI e i pacchetti `mido` e `python-rtmidi`

### Installazione

Aprire PowerShell nella cartella del progetto ed eseguire:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se PowerShell impedisce l'attivazione dello script, è possibile installare i pacchetti usando direttamente `.\venv\Scripts\python.exe -m pip install -r requirements.txt`.

### Avvio

Con l'ambiente attivato:

```powershell
python main.py
```

Si aprono la finestra principale e la finestra **Note Hive**. La prima contiene i controlli; Note Hive offre la griglia delle note, la tastiera visuale e i monitor. Per fermare e chiudere correttamente il programma, chiudere la finestra principale.

## 2. Riprodurre le note

1. Premere **Start Audio** nella scheda **Audio**.
2. Suonare con la tastiera del computer, con la griglia di Note Hive oppure con un controller MIDI configurato.
3. Rilasciare il tasto o il pulsante MIDI per terminare la nota.
4. Premere **Stop Audio** quando si vuole interrompere il motore.

Le note possono essere sovrapposte: il motore supporta fino a 32 voci. L'inviluppo Release e gli effetti possono continuare a sentirsi dopo il rilascio del tasto.

### Tastiera del computer

I tasti corrispondono a quattro ottave, da C3 a B6. La mappatura segue righe consecutive della tastiera:

| Ottava | Tasti, da sinistra a destra | Note |
|---|---|---|
| 3 | `\ < Z X C V B N M , . -` | C3–B3 |
| 4 | `A S D F G H J K L Ò À Ù` | C4–B4 |
| 5 | `Q W E R T Y U I O P È +` | C5–B5 |
| 6 | `1 2 3 4 5 6 7 8 9 0 ' Ì` | C6–B6 |

La tastiera visuale in Note Hive mostra la corrispondenza tra nota e tasto. Il layout della griglia può essere cambiato tra **Alveare** e **Tonnetz**; cliccare una cella avvia la nota e rilasciarla la termina.

### Modalità armoniche

Nella scheda **Audio**, **Mode** seleziona quante note vengono generate da un tasto:

- **single**: la nota premuta;
- **dyad**: la nota e un intervallo;
- **triad**: la nota e due intervalli.

**Chord** sceglie la qualità dell'accordo quando è disponibile. La modalità armonica si applica anche alle note MIDI in ingresso.

## 3. Controller MIDI

1. Collegare il controller e aprire la scheda **Engine / MIDI**.
2. Premere **Refresh** per aggiornare l'elenco delle porte.
3. Selezionare il controller in **MIDI Input**; selezionare **MIDI: Off** per scollegarlo.
4. Avviare l'audio e suonare dal controller.

Il programma usa la velocity per l'intensità iniziale delle note e supporta:

- **CC 1**: profondità LFO;
- **CC 7**: volume master;
- **CC 74**: cutoff del filtro;
- **Pitch bend**: variazione fino a ±2 semitoni sulle note MIDI attive;
- **Aftertouch**: pressione di canale o della singola nota, secondo il messaggio ricevuto.

Se la porta non compare, controllare che il dispositivo sia collegato e riconosciuto dal sistema, quindi premere nuovamente **Refresh**.

## 4. Scegliere e modellare il suono

I controlli di sintesi e Unison sono sempre visibili sotto le schede **Audio Controls**. Cambiandoli si modifica anche il suono delle note già attive, quando applicabile.

### Motore di sintesi e Unison

- **Engine**: `waveform` usa la forma d'onda scelta; `additive` somma armoniche; `fm` modula una portante. Cambiare motore modifica il contenuto armonico, non solo il volume.
- **Waveform**: sine ha un suono puro e morbido; triangle è generalmente più dolce; square e sawtooth hanno più armoniche e risultano più ricche e brillanti. La modifica si applica alla sintesi a oscillatore; con un WAV caricato il selettore è disabilitato.
- **Additive partials**: aumentando da 1 fino a 16 si aggiungono armoniche e il timbro diventa più complesso e brillante; diminuendo si semplifica e si scurisce. Prova 1–3 per toni semplici e 8 o più per suoni più ricchi.
- **Harmonic tilt**: aumentando il valore si attenuano più rapidamente le armoniche alte e il suono diventa più scuro; diminuendolo le armoniche alte restano più presenti. A zero hanno tutte lo stesso peso.
- **FM ratio**: cambia il rapporto tra frequenza modulante e portante, quindi la disposizione delle bande laterali e il carattere del suono. Rapporti semplici e vicini tendono a risultare più armonici; rapporti più alti o non interi possono dare un carattere metallico o dissonante.
- **FM index**: a zero la modulazione FM è assente e resta un tono di portante; aumentando il valore crescono le bande laterali e la complessità, fino a timbri aspri o metallici. Ridurlo se il suono diventa troppo aggressivo.
- **Unison voices**: aumenta il numero di copie sovrapposte per nota, da 1 a 7. Più copie rendono il suono più spesso e largo; il livello è normalizzato, quindi aggiungerne non dovrebbe aumentare da solo il volume. Una sola copia mantiene il timbro più pulito e riduce il carico CPU.
- **Detune**: aumenta la differenza di intonazione tra le copie, da 0 a 50 centesimi. Più detune crea battimenti e un effetto più largo/corposo; ridurlo rende l'intonazione più stabile. Valori estremi possono far percepire le copie come stonate. Con una sola voce Unison non c'è una seconda copia da scordare.

Un esempio per un suono pieno ma controllato: selezionare `waveform`, scegliere triangle o sawtooth, impostare **Unison voices** a 3 e aumentare **Detune** poco alla volta (per esempio 8–15 centesimi). Se l'intonazione oscilla troppo, diminuire prima Detune; se il timbro è ancora troppo denso, riportare Unison a 2 o 1. Questi parametri si applicano anche ai campioni WAV.

### Volume, inviluppo, filtro e LFO

- **Volume** regola il livello master: aumentarlo rende l'uscita più forte, diminuirlo più silenziosa. Non cambia l'inviluppo delle singole note. Se molte voci o effetti producono picchi elevati, il limitatore di uscita può ridurre automaticamente il guadagno.
- **Attack**: aumentarlo fa entrare la nota più lentamente e attenua l'attacco; diminuirlo rende la nota più immediata e incisiva.
- **Decay**: aumentarlo allunga la discesa dal picco al sustain; diminuirlo porta più rapidamente al livello sostenuto.
- **Sustain**: aumentarlo mantiene la nota più forte mentre il tasto è premuto; diminuirlo crea una nota che cala di volume anche se tenuta. A differenza degli altri parametri ADSR, è un livello, non una durata.
- **Release**: aumentarlo prolunga la coda dopo il rilascio; diminuirlo spegne la nota più rapidamente. Per suoni percussivi prova un release breve; per pad e code ambientali prova un valore più lungo.
- **Filter Type**: seleziona il filtro low-pass (attenua le frequenze sopra il cutoff), high-pass (attenua quelle sotto il cutoff) o band-pass (lascia passare soprattutto la zona attorno al cutoff).
- **Cutoff**: sposta la frequenza di taglio o il centro della banda. Nel low-pass, aumentarlo rende il suono più brillante e diminuirlo più scuro; nell'high-pass, aumentarlo elimina più basse frequenze e assottiglia il suono; nel band-pass, spostarlo cambia la zona di frequenze che emerge. Il valore viene limitato automaticamente a una zona sicura rispetto al sample rate.
- **Resonance**: enfatizza la zona vicina al cutoff. Aumentarla rende il picco più stretto e udibile; diminuirla dà una risposta più uniforme. La scala va da 0 (Q circa 0,71, risposta smorzata) a 100 (Q fino a 10, picco marcato). Con valori elevati il filtro può aumentare molto il livello vicino al cutoff: abbassare il Volume se il suono diventa troppo forte o squillante.
- **LFO Target**: pitch produce una variazione periodica dell'intonazione (vibrato); volume una variazione periodica del livello (tremolo); filter modula il cutoff. **Rate** più alto rende il movimento più veloce; **Depth** più alta lo rende più ampio. A depth zero la modulazione è assente.

Per un attacco morbido prova ad aumentare Attack; per un suono pizzicato diminuiscilo e accorcia Decay e Release. Per aggiungere vibrato scegli **pitch**, imposta una Rate lenta o moderata e alza Depth con cautela; se il pitch oscilla troppo, abbassa Depth.

### Effetti

I pannelli **Distortion**, **Delay**, **Chorus** e **Reverb** sono sempre visibili nella finestra principale.

- **Distortion**: seleziona Off, Soft Clip, Overdrive, Hard Clip, Fuzz o Bitcrusher. **Drive** più alto spinge maggiormente il segnale e aumenta la saturazione; **Mix** più alto rende più presente il segnale distorto, mentre più basso conserva il suono originale. Soft Clip e Overdrive sono più graduali; Hard Clip e Fuzz sono più aggressivi; Bitcrusher riduce la risoluzione e aggiunge una grana digitale.
- **Delay**: attivare l'effetto. **Time** più alto distanzia gli echi; **Feedback** più alto aumenta le ripetizioni e la loro durata; **Mix** più alto rende gli echi più evidenti rispetto al suono diretto. Per un eco discreto usare Mix e Feedback bassi; se la coda si accumula, abbassare Feedback o disattivare il delay.
- **Chorus**: attivare l'effetto. **Rate** più alto accelera il movimento; **Depth** più alta amplia la variazione del ritardo; **Mix** più alto rende più udibile l'effetto. Valori moderati aggiungono ampiezza, mentre valori elevati possono far oscillare molto il timbro.
- **Reverb**: attivare l'effetto. **Decay** più alto allunga la coda ambientale; **Mix** più alto aumenta la quantità di riverbero rispetto al suono diretto. Ridurre entrambi se le note si confondono o la coda invade le note successive.

Il mixer applica un limite di sicurezza ai picchi in uscita, dopo gli effetti. Questo contenimento può ridurre temporaneamente il guadagno quando le voci o gli effetti si sommano ad alto livello.

### Esempi rapidi di regolazione

Partire da un preset o da un suono semplice, suonare alcune note e modificare un parametro alla volta:

| Obiettivo | Modifiche da provare | Risultato atteso |
|---|---|---|
| Suono più morbido | Triangle o sine; aumentare Attack; ridurre parziali o FM index | Attacco più graduale e meno armoniche aggressive |
| Suono più brillante | Aumentare parziali; ridurre Harmonic tilt; provare square o sawtooth | Più armoniche alte e maggiore presenza |
| Suono più corposo | Unison 2–3; Detune moderato; Chorus leggero | Maggiore densità e larghezza senza alzare necessariamente il volume |
| Suono percussivo | Attack basso; Decay breve; Sustain basso; Release breve | Attacco rapido e coda contenuta |
| Suono ambientale | Attack più lungo; Release e Reverb Decay più lunghi; Mix reverb moderato | Note più morbide e coda più ampia |
| Eco evidente | Attivare Delay; aumentare Mix; alzare Feedback gradualmente | Ripetizioni più udibili e persistenti |

I risultati dipendono dalla sorgente, dal registro e dalla combinazione dei controlli. Se il suono diventa troppo forte, confuso o instabile, ridurre Mix/Feedback degli effetti, Detune o Volume e confrontare di nuovo.

## 5. Caricare un campione WAV

1. Aprire **Sampler / Presets** nella sezione Audio Controls.
2. Premere **Load WAV** e selezionare un file WAV PCM.
3. Impostare **Sample root MIDI** sulla nota alla quale il campione è stato registrato. Il valore iniziale è 69 (A4). Se si alza la nota radice, a parità di tasto suonato il campione viene riprodotto più lentamente e il pitch scende; abbassando la radice il pitch sale.
4. Suonare: le altre note vengono ottenute trasponendo il campione rispetto alla nota radice.
5. Premere **Remove WAV** per scaricare il campione e tornare agli oscillatori.

Il campione viene riprodotto in loop mentre la nota resta attiva. Inviluppo, filtro, LFO, volume, effetti e Unison continuano ad applicarsi. La sorgente originale non viene modificata. Un preset che usa un campione memorizza il suo percorso: per ritrovarlo, il file deve rimanere disponibile allo stesso percorso.

## 6. Salvare e richiamare preset

1. Aprire **Sampler / Presets**.
2. Selezionare un preset esistente oppure scrivere un nuovo nome nel campo editabile.
3. Premere **Save Preset** per salvare lo stato corrente; il programma crea o aggiorna il relativo file JSON nella cartella `presets`.
4. Selezionare un nome e premere **Load Preset** per applicarlo.

I preset salvano i parametri sonori, la modalità armonica, gli effetti e il percorso del campione. Se un campione salvato non è più disponibile, il preset può essere caricato senza quel WAV; la barra di stato segnala l'eventuale errore.

Quando **Note Hive** è la finestra attiva e non si sta scrivendo in un campo di testo, le frecce **sinistra/destra** caricano il preset precedente/successivo. La lista scorre circolarmente.

## 7. Registrare e monitorare l'audio

### Registrazione

1. Avviare l'audio e premere **Record**.
2. Suonare o riprodurre le note da registrare.
3. Premere **Stop Recording**.

La registrazione produce un WAV mono nella cartella `recordings`, con un nome basato su data e ora. La cattura comprende il segnale generato e gli effetti. La scrittura avviene in background: se il disco non riesce a tenere il passo e la coda si riempie, la registrazione si interrompe e la barra di stato mostra un errore; l'audio continua.

### Oscilloscopio e monitor

In **Note Hive**, premere **Scope Monitors** per mostrare la forma d'onda e le metriche; premere **Keyboard** per tornare alla tastiera visuale. Durante la riproduzione il monitor riporta:

- voci attive e underrun segnalati dal dispositivo;
- media, P95 e massimo del tempo di callback;
- budget temporale del buffer e callback oltre budget.

Il P95 rappresenta il tempo entro cui rientra il 95% dei callback recenti. Se supera il budget o gli underrun aumentano, provare a ridurre Unison, effetti o polifonia; in alternativa aumentare **Buffer size** nella scheda **Engine / MIDI**. Un buffer più grande può aumentare la latenza.

## 8. Impostazioni del motore

Nella scheda **Engine / MIDI**:

- **Buffer size** accetta da 64 a 512 campioni; modificarlo mentre l'audio è fermo.
- **Sample rate** offre 22050, 44100, 48000, 88200 e 96000 Hz; modificarlo mentre l'audio è fermo. Se un campione è caricato viene adattato alla nuova frequenza.
- Un buffer più piccolo riduce la latenza potenziale, ma lascia meno tempo per calcolare ogni blocco. Usare un buffer più grande se si verificano underrun.

## 9. Risoluzione dei problemi

| Problema | Cosa verificare |
|---|---|
| Non si sente audio | Premere **Start Audio**, controllare il dispositivo audio di sistema e verificare che Volume non sia a zero. |
| L'audio gracchia o si interrompe | Ridurre Unison, effetti o note simultanee; provare un buffer più grande e osservare underrun e callback oltre budget. |
| Il controller non compare | Collegarlo, premere **Refresh** e verificare che il sistema operativo lo riconosca. |
| Il preset non ritrova il WAV | Verificare che il file esista ancora al percorso salvato; in alternativa caricarlo manualmente. |
| La nota campionata è stonata | Impostare correttamente **Sample root MIDI** sulla nota originale del WAV. |
| La registrazione si interrompe | Controllare spazio e prestazioni del disco; la barra di stato mostra l'errore restituito dal writer. |

## 10. Note

- I valori di cutoff vengono limitati internamente in base al sample rate, per mantenere stabile il filtro anche quando si selezionano frequenze elevate.
- Le metriche del callback sono indicative del carico software: il risultato dipende da sistema operativo, dispositivo audio, sample rate e buffer.
