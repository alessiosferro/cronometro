#!/usr/bin/env python3
"""Cronometro da terminale per macOS. Richiede Python 3.9 o successivo."""

import argparse
from datetime import datetime
import math
from pathlib import Path
import time


def hhmm(seconds):
    minutes = math.floor(seconds / 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def format_duration(seconds):
    return f"{hhmm(seconds)}:{math.floor(seconds) % 60:02d}"


WEEKDAYS = (
    "Lunedì", "Martedì", "Mercoledì", "Giovedì",
    "Venerdì", "Sabato", "Domenica",
)
MONTHS = (
    "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
)
TABLE_HEADER = "Inizio   | Durata   | Pause    | Fine"
TABLE_SEPARATOR = "---------+----------+----------+---------"


def format_date(moment):
    return f"{WEEKDAYS[moment.weekday()]} {moment.day} {MONTHS[moment.month - 1]} {moment.year}"


class Stopwatch:
    def __init__(self, clock=time.monotonic, wall_clock=datetime.now):
        self.clock = clock
        self.wall_clock = wall_clock
        self.total = 0.0
        self.paused_total = 0.0
        self.since = None
        self.paused_since = None
        self.started_at = None
        self.ended_at = None
        self.state = "pronto"

    def start(self):
        if self.state != "pronto":
            return False
        self.since = self.clock()
        self.started_at = self.wall_clock()
        self.state = "in corso"
        return True

    def pause(self):
        if self.state != "in corso":
            return False
        now = self.clock()
        self.total += now - self.since
        self.since = None
        self.paused_since = now
        self.state = "in pausa"
        return True

    def resume(self):
        if self.state != "in pausa":
            return False
        now = self.clock()
        self.paused_total += now - self.paused_since
        self.paused_since = None
        self.since = now
        self.state = "in corso"
        return True

    def elapsed(self):
        return self.total + (self.clock() - self.since if self.since is not None else 0)

    def pause_elapsed(self):
        current_pause = (
            self.clock() - self.paused_since
            if self.paused_since is not None
            else 0
        )
        return self.paused_total + current_pause

    def stop(self):
        if self.state == "pronto":
            return False
        now = self.clock()
        if self.state == "in corso":
            self.total += now - self.since
        else:
            self.paused_total += now - self.paused_since
        self.since = None
        self.paused_since = None
        self.ended_at = self.wall_clock()
        self.state = "terminato"
        return True


def append_duration(path, started_at, seconds, pause_seconds, ended_at):
    date_heading = format_date(ended_at)
    heading_block = f"{date_heading}\n{'=' * len(date_heading)}"
    time_entry = (
        f"{started_at:%H:%M:%S} | {format_duration(seconds)} | "
        f"{format_duration(pause_seconds)} | {ended_at:%H:%M:%S}"
    )

    with path.open("a+b") as stream:
        stream.seek(0)
        existing = stream.read().decode("utf-8", errors="replace")
        addition = ""

        if heading_block not in existing:
            if existing and not existing.endswith("\n"):
                addition += "\n"
            if existing and not (existing + addition).endswith("\n\n"):
                addition += "\n"
            addition += (
                f"{heading_block}\n\n{TABLE_HEADER}\n{TABLE_SEPARATOR}\n"
            )
        else:
            current_section = existing[existing.rfind(heading_block):]
            if existing and not existing.endswith("\n"):
                addition += "\n"
            if TABLE_HEADER not in current_section:
                if existing and not (existing + addition).endswith("\n\n"):
                    addition += "\n"
                addition += f"{TABLE_HEADER}\n{TABLE_SEPARATOR}\n"

        stream.seek(0, 2)
        stream.write((addition + time_entry + "\n").encode("utf-8"))


HELP = """Comandi (premi Invio dopo ogni comando):
  start / avvia       Avvia la sessione.
  pausa / pause       Mette in pausa.
  riprendi / resume   Riprende la sessione.
  stato / status      Mostra durata effettiva e stato.
  stop               Ferma, salva la durata ed esce.
  aiuto / help       Mostra questi comandi.
Ctrl+C o Ctrl+D equivalgono a stop. Prima di start escono senza salvare."""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="File di testo a cui aggiungere le sessioni del cronometro")
    args = parser.parse_args()
    path = Path(args.file).expanduser().absolute()
    if not path.parent.is_dir():
        parser.error(f"La cartella non esiste: {path.parent}")
    if path.exists() and not path.is_file():
        parser.error(f"Il percorso non è un file: {path}")

    timer = Stopwatch()
    print(f"File: {path}\n{HELP}\nPronto. Digita start per cominciare.")
    while True:
        try:
            command = input("> ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            command = "stop"

        if command == "stop":
            if not timer.stop():
                print("Nessuna sessione avviata: nessuna riga salvata.")
                return 0
            duration = timer.elapsed()
            pause_duration = timer.pause_elapsed()
            while True:
                try:
                    append_duration(
                        path,
                        timer.started_at,
                        duration,
                        pause_duration,
                        timer.ended_at,
                    )
                except OSError as error:
                    print(f"Salvataggio non riuscito: {error}")
                    print(
                        f"Durata da conservare: {format_duration(duration)}; "
                        f"pause: {format_duration(pause_duration)}"
                    )
                    try:
                        new_path = input("Nuovo file (Invio per riprovare, Ctrl+C per uscire): ").strip()
                    except (KeyboardInterrupt, EOFError):
                        print("\nDurata NON salvata.")
                        return 1
                    if new_path:
                        path = Path(new_path).expanduser().absolute()
                    continue
                print(
                    f"Salvato {format_duration(duration)} "
                    f"(pause: {format_duration(pause_duration)}) in {path}"
                )
                return 0
        elif command in ("start", "avvia"):
            print("Sessione avviata." if timer.start() else "Sessione già avviata. Usa riprendi se è in pausa.")
        elif command in ("pause", "pausa"):
            print("In pausa." if timer.pause() else "La sessione non è in corso.")
        elif command in ("resume", "riprendi"):
            print("Sessione ripresa." if timer.resume() else "La sessione non è in pausa.")
        elif command in ("status", "stato"):
            seconds = math.floor(timer.elapsed())
            print(f"{hhmm(seconds)}:{seconds % 60:02d} — {timer.state}")
        elif command in ("help", "aiuto", "?"):
            print(HELP)
        elif command:
            print("Comando sconosciuto. Digita aiuto per l'elenco.")


if __name__ == "__main__":
    raise SystemExit(main())
