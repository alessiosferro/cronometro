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
| `stop` | Salva la durata e chiude l'applicazione. |
| `aiuto` | Mostra i comandi disponibili. |

Sono accettati anche `avvia`, `pause`, `resume`, `status` e `help`. Il cronometro attende `start`: il tempo impiegato prima di quel comando non conta. Lo stato viene mostrato su richiesta, senza aggiornamento continuo del display.

**Ctrl+C** e **Ctrl+D** fanno stop e salvano; prima di `start` escono senza scrivere. Per una nuova sessione, esegui nuovamente il programma.

## File salvato

Le sessioni vengono raggruppate per giorno. Se l'intestazione della data corrente
non è ancora presente, il programma la aggiunge e la sottolinea con un simbolo `=`
per ogni carattere:

```text
Lunedì 14 Settembre 2026
========================

17:20:45 - 03:00:00 - 20:20:45
21:10:00 - 00:25:30 - 21:35:30
```

Ogni riga usa il formato `ora di partenza - durata totale - ora di fine`, sempre
con ore, minuti e secondi (`hh:mm:ss`). Il tempo in pausa è escluso dalla durata.
Le frazioni di secondo vengono troncate e le ore della durata possono superare 99.
L'ora di partenza e quella di fine sono invece orari del giorno, rilevati dal
computer.

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

I test verificano il conteggio con le pause, il formato delle date e delle
durate, la struttura del file e l'assenza di intestazioni giornaliere duplicate.

## Licenza

Distribuito con licenza [MIT](LICENSE).
