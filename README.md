# Cronometro per lo studio — macOS

Una piccola applicazione da terminale, senza librerie esterne. Richiede **Python 3.9 o successivo**, verificabile con `python3 --version`. Se manca, installa Python 3 per macOS da [python.org](https://www.python.org/downloads/macos/).

## Esecuzione

Apri Terminale nella cartella che contiene `cronometro.py`, quindi esegui:

```sh
python3 cronometro.py "$HOME/Documents/studio.txt"
```

Puoi scegliere qualsiasi file: usa le virgolette se il percorso contiene spazi. Il file viene creato al primo salvataggio, ma la cartella deve già esistere. I percorsi relativi partono dalla cartella corrente del terminale.

## Comandi

Scrivi ciascun comando e premi **Invio**:

| Comando | Effetto |
| --- | --- |
| `start` | Avvia il conteggio. |
| `pausa` | Sospende il conteggio. |
| `riprendi` | Riprende dalla durata accumulata. |
| `stato` | Mostra durata in `hh:mm:ss` e stato attuale. |
| `stop` | Salva la sessione e rimane pronto per un nuovo avvio. |
| `completa` | Chiude la giornata, aggiunge i totali ed esce. |
| `aiuto` | Mostra i comandi disponibili. |

Sono accettati anche `avvia`, `pause`, `resume`, `status`, `complete` e `help`. Il cronometro attende `start`: il tempo impiegato prima di quel comando non conta. Lo stato viene mostrato su richiesta, senza aggiornamento continuo del display.

`stop` può essere usato più volte per registrare diverse sessioni senza riavviare
il programma. Se usi `completa` mentre una sessione è in corso o in pausa, questa
viene prima fermata e salvata. **Ctrl+C** viene ignorato per evitare chiusure
accidentali; **Ctrl+D** equivale a `completa`.

## Visualizzazione in tempo reale

Dopo `start`, il cronometro mostra sopra al prompt una riga che si aggiorna
automaticamente:

```text
Durata: 00:42:18 | Pause: 00:05:31 | Stato: in pausa
> riprendi
```

Durante una pausa la durata effettiva rimane ferma e il valore `Pause` continua
ad aumentare; dopo `riprendi` ricomincia ad avanzare la durata. Dopo ogni comando
di controllo il terminale viene ripulito, lasciando visibili i tre valori e il
prompt. `aiuto`, `stato` ed eventuali errori mantengono invece il proprio
messaggio fino al comando successivo. Dopo `stop` rimangono visibili i valori
della sessione appena salvata; un nuovo `start` li azzera e avvia una nuova
sessione.

La visualizzazione dinamica viene attivata solo in un terminale interattivo,
quindi non aggiunge sequenze di controllo quando l'output viene reindirizzato in
un file o usato da uno script.

## File salvato

Le sessioni vengono raggruppate per giorno. Se l'intestazione della data corrente
non è ancora presente, il programma la aggiunge e la sottolinea con un simbolo `=`
per ogni carattere:

```text
Lunedì 14 Settembre 2026
========================

Inizio   | Durata   | Pause    | Fine
---------+----------+----------+---------
17:20:45 | 03:00:00 | 00:30:00 | 20:50:45
21:10:00 | 00:25:30 | 00:05:00 | 21:40:30
=========+==========+==========+=========
Totale   | 03:25:30 | 00:35:00 |
```

La tabella riporta ora di partenza, durata effettiva, pause totali e ora di fine,
sempre con ore, minuti e secondi (`hh:mm:ss`). La durata effettiva esclude tutte
le pause, mentre la colonna `Pause` ne riporta la durata complessiva. Le frazioni
di secondo vengono troncate e le ore delle durate possono superare 99. L'ora di
partenza e quella di fine sono invece orari del giorno, rilevati dal computer.

Il comando `completa` somma tutte le sessioni della data corrente e chiude la
tabella con il totale del lavoro effettivo e delle pause. Se la giornata è già
stata completata, il totale non viene duplicato.

Se il file contiene in apertura il riepilogo `Somma totale delle ore lavorate`,
`completa` lo ricostruisce usando i totali delle singole giornate. Il riepilogo
mostra ogni data e aggiorna automaticamente il valore complessivo:

```text
Giorno                       | Durata
-----------------------------+----------
Domenica 13 Settembre 2026   | 05:58:00
Lunedì 14 Settembre 2026     | 04:00:00
Martedì 15 Settembre 2026    | 01:26:17
=============================+==========
Totale complessivo           | 29:18:17
```

I dati creati dalle versioni precedenti restano invariati. Quando il programma
trova una giornata già presente nel vecchio formato, aggiunge sotto di essa
l'intestazione della tabella prima della nuova sessione.

L'intestazione viene scritta una sola volta per ogni data già presente nel file.
Il programma conserva tutto il contenuto esistente e aggiunge le nuove sessioni
in fondo.

Se il salvataggio fallisce, il tempo rimane fermo e puoi indicare un altro file o riprovare. Lascia il programma aperto durante la sessione: la chiusura forzata del Terminale, un arresto del computer o la terminazione forzata del processo non salvano la sessione. Usa un solo cronometro alla volta per lo stesso file.

## Installazione facoltativa

Per richiamarlo come `cronometro`, dalla cartella del programma:

```sh
mkdir -p "$HOME/.local/bin"
install -m 755 cronometro.py "$HOME/.local/bin/cronometro"
```

Poi puoi avviarlo con:

```sh
"$HOME/.local/bin/cronometro" "$HOME/Documents/studio.txt"
```

Per usare il nome breve, aggiungi questa riga a `~/.zshrc` e riapri il Terminale:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

Ora basta `cronometro "$HOME/Documents/studio.txt"`. L'installazione sostituisce un eventuale comando `cronometro` già presente in `~/.local/bin`.

## Test

Il progetto usa esclusivamente la libreria standard di Python. Per eseguire i
test automatici dalla cartella del repository:

```sh
python3 -m unittest discover -s tests
```

I test verificano il conteggio e la somma delle pause, la visualizzazione in
tempo reale, il formato delle date e delle durate, la struttura e la chiusura
della tabella, il riepilogo complessivo, il flusso dei comandi e l'assenza di
intestazioni o totali duplicati.

## Licenza

Distribuito con licenza [MIT](LICENSE).
