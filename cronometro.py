#!/usr/bin/env python3
"""Cronometro da terminale per macOS. Richiede Python 3.9 o successivo."""

import argparse
from datetime import datetime
import math
from pathlib import Path
import re
import sys
import threading
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
TABLE_TOTAL_SEPARATOR = "=========+==========+==========+========="
TABLE_ENTRY_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2} \| (?P<work>\d+:\d{2}:\d{2}) \| "
    r"(?P<pause>\d+:\d{2}:\d{2}) \| \d{2}:\d{2}:\d{2}$",
    re.MULTILINE,
)
LEGACY_ENTRY_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2} - (?P<work>\d+:\d{2}:\d{2}) - "
    r"(?P<pause>\d+:\d{2}:\d{2}) - \d{2}:\d{2}:\d{2}$",
    re.MULTILINE,
)
LEGACY_ENTRY_WITHOUT_PAUSE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2} - (?P<work>\d+:\d{2}:\d{2}) - "
    r"\d{2}:\d{2}:\d{2}$",
    re.MULTILINE,
)
TOTAL_ENTRY_RE = re.compile(
    r"^Totale\s+\| (?P<work>\d+:\d{2}:\d{2}) \| "
    r"(?P<pause>\d+:\d{2}:\d{2}) \|$",
    re.MULTILINE,
)
DAILY_WORK_TOTAL_RE = re.compile(
    r"^Totale\s+\| (?P<work>\d+:\d{2}:\d{2}) \|",
    re.MULTILINE,
)
DAILY_HEADING_RE = re.compile(
    r"^(?P<date>[^\n]+ \d{1,2} [^\n]+ \d{4})\n=+$",
    re.MULTILINE,
)
LEGACY_DAILY_TOTAL_RE = re.compile(
    r"^Totale:\s*(?P<work>\d+:\d{2}(?::\d{2})?)$",
    re.MULTILINE,
)
SUMMARY_TITLE = "Somma totale delle ore lavorate"


def format_date(moment):
    return f"{WEEKDAYS[moment.weekday()]} {moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def duration_to_seconds(value):
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        parts.append(0)
    hours, minutes, seconds = parts
    return hours * 3600 + minutes * 60 + seconds


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
        if self.state not in ("in corso", "in pausa"):
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


def format_live_status(timer):
    return f"Durata: {format_duration(timer.elapsed())}"


def clear_terminal(stream=None):
    stream = stream if stream is not None else sys.stdout
    if not stream.isatty():
        return False
    stream.write("\033[2J\033[H")
    stream.flush()
    return True


class LiveDisplay:
    def __init__(self, timer, refresh_interval=0.2, stream=None, input_stream=None):
        self.timer = timer
        self.refresh_interval = refresh_interval
        self.stream = stream if stream is not None else sys.stdout
        self.input_stream = input_stream if input_stream is not None else sys.stdin
        self.stop_event = threading.Event()
        self.thread = None
        self.enabled = (
            timer.state != "pronto"
            and self.stream.isatty()
            and self.input_stream.isatty()
        )

    def __enter__(self):
        if not self.enabled:
            return self
        self.stream.write(format_live_status(self.timer) + "\n")
        self.stream.flush()
        self.thread = threading.Thread(target=self._refresh, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, _exception_type, _exception, _traceback):
        if self.thread is not None:
            self.stop_event.set()
            self.thread.join()

    def _refresh(self):
        while not self.stop_event.wait(self.refresh_interval):
            # Save the prompt cursor, update the status line above it, then
            # restore the cursor without disturbing the command being typed.
            self.stream.write(
                "\0337\033[1A\r\033[2K"
                + format_live_status(self.timer)
                + "\0338"
            )
            self.stream.flush()


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


def complete_day(path, moment):
    if not path.exists():
        return "no_sessions", 0, 0

    date_heading = format_date(moment)
    heading_block = f"{date_heading}\n{'=' * len(date_heading)}"

    with path.open("a+b") as stream:
        stream.seek(0)
        existing = stream.read().decode("utf-8", errors="replace")
        heading_position = existing.rfind(heading_block)
        if heading_position == -1:
            return "no_sessions", 0, 0

        current_section = existing[heading_position:]
        previous_total = TOTAL_ENTRY_RE.search(current_section)
        if previous_total:
            return (
                "already_complete",
                duration_to_seconds(previous_total.group("work")),
                duration_to_seconds(previous_total.group("pause")),
            )

        work_seconds = 0
        pause_seconds = 0
        entry_count = 0
        for pattern in (TABLE_ENTRY_RE, LEGACY_ENTRY_RE):
            for entry in pattern.finditer(current_section):
                work_seconds += duration_to_seconds(entry.group("work"))
                pause_seconds += duration_to_seconds(entry.group("pause"))
                entry_count += 1
        for entry in LEGACY_ENTRY_WITHOUT_PAUSE_RE.finditer(current_section):
            work_seconds += duration_to_seconds(entry.group("work"))
            entry_count += 1

        if entry_count == 0:
            return "no_sessions", 0, 0

        addition = ""
        if existing and not existing.endswith("\n"):
            addition += "\n"
        if TABLE_HEADER not in current_section:
            if existing and not (existing + addition).endswith("\n\n"):
                addition += "\n"
            addition += f"{TABLE_HEADER}\n{TABLE_SEPARATOR}\n"
        addition += (
            f"{TABLE_TOTAL_SEPARATOR}\n"
            f"Totale   | {format_duration(work_seconds)} | "
            f"{format_duration(pause_seconds)} |\n"
        )

        stream.seek(0, 2)
        stream.write(addition.encode("utf-8"))
        return "completed", work_seconds, pause_seconds


def update_overall_summary(path):
    existing = path.read_text(encoding="utf-8")
    headings = list(DAILY_HEADING_RE.finditer(existing))
    if not headings:
        return None

    daily_totals = []
    for index, heading in enumerate(headings):
        section_end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(existing)
        )
        section = existing[heading.end():section_end]
        total = DAILY_WORK_TOTAL_RE.search(section)
        if total:
            work_seconds = duration_to_seconds(total.group("work"))
        else:
            legacy_total = LEGACY_DAILY_TOTAL_RE.search(section)
            if not legacy_total:
                continue
            work_seconds = duration_to_seconds(legacy_total.group("work"))
        daily_totals.append((heading.group("date"), work_seconds))

    if not daily_totals:
        return None

    first_heading_position = headings[0].start()
    if first_heading_position and not existing.startswith(SUMMARY_TITLE):
        return None

    label_width = max(
        28,
        len("Totale complessivo"),
        *(len(date) for date, _ in daily_totals),
    )
    summary_lines = [
        SUMMARY_TITLE,
        "=" * len(SUMMARY_TITLE),
        "",
        f"{'Giorno':<{label_width}} | Durata",
        f"{'-' * (label_width + 1)}+----------",
    ]
    summary_lines.extend(
        f"{date:<{label_width}} | {format_duration(seconds)}"
        for date, seconds in daily_totals
    )
    overall_seconds = sum(seconds for _, seconds in daily_totals)
    summary_lines.extend(
        (
            f"{'=' * (label_width + 1)}+==========",
            f"{'Totale complessivo':<{label_width}} | "
            f"{format_duration(overall_seconds)}",
            "",
        )
    )

    body = existing[first_heading_position:]
    path.write_text("\n".join(summary_lines) + "\n" + body, encoding="utf-8")
    return overall_seconds


HELP = """Comandi (premi Invio dopo ogni comando):
  start / avvia       Avvia la sessione.
  pausa / pause       Mette in pausa.
  riprendi / resume   Riprende la sessione.
  stato / status      Mostra durata effettiva e stato.
  stop               Ferma e salva la sessione, poi resta aperto.
  completa / complete Chiude la giornata con i totali ed esce.
  aiuto / help       Mostra questi comandi.
Ctrl+C non interrompe il programma; Ctrl+D equivale a completa."""


def save_timer(path, timer):
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
                new_path = input(
                    "Nuovo file (Invio per riprovare, Ctrl+C per continuare): "
                ).strip()
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                print("\nDurata NON salvata.")
                return path, False
            if new_path:
                path = Path(new_path).expanduser().absolute()
            continue

        print(
            f"Salvato {format_duration(duration)} "
            f"(pause: {format_duration(pause_duration)}) in {path}"
        )
        return path, True


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
    clear_before_prompt = False
    while True:
        if clear_before_prompt:
            clear_terminal()
        clear_before_prompt = True
        try:
            with LiveDisplay(timer):
                command = input("> ").strip().lower()
        except KeyboardInterrupt:
            print("\nInterruzione ignorata. Digita completa per terminare.")
            clear_before_prompt = False
            continue
        except EOFError:
            print()
            command = "completa"

        if command == "stop":
            if not timer.stop():
                print("Nessuna sessione avviata: nessuna riga salvata.")
                clear_before_prompt = False
                continue
            path, saved = save_timer(path, timer)
            if not saved:
                return 1
        elif command in ("completa", "complete"):
            clear_terminal()
            if timer.state in ("in corso", "in pausa"):
                timer.stop()
                path, saved = save_timer(path, timer)
                if not saved:
                    return 1
            try:
                result, work_seconds, pause_seconds = complete_day(
                    path, datetime.now()
                )
                overall_seconds = update_overall_summary(path)
            except OSError as error:
                print(f"Chiusura della giornata non riuscita: {error}")
                continue
            if result == "completed":
                print(
                    f"Giornata completata: {format_duration(work_seconds)} "
                    f"di lavoro, {format_duration(pause_seconds)} di pausa."
                )
            elif result == "already_complete":
                print(
                    f"Giornata già completata: {format_duration(work_seconds)} "
                    f"di lavoro, {format_duration(pause_seconds)} di pausa."
                )
            else:
                print("Nessuna sessione da totalizzare per la giornata corrente.")
            if overall_seconds is not None:
                print(
                    f"Totale complessivo aggiornato: "
                    f"{format_duration(overall_seconds)}."
                )
            return 0
        elif command in ("start", "avvia"):
            if timer.state == "terminato":
                timer = Stopwatch()
            if timer.start():
                print("Sessione avviata.")
            else:
                print("Sessione già avviata. Usa riprendi se è in pausa.")
                clear_before_prompt = False
        elif command in ("pause", "pausa"):
            if timer.pause():
                print("In pausa.")
            else:
                print("La sessione non è in corso.")
                clear_before_prompt = False
        elif command in ("resume", "riprendi"):
            if timer.resume():
                print("Sessione ripresa.")
            else:
                print("La sessione non è in pausa.")
                clear_before_prompt = False
        elif command in ("status", "stato"):
            seconds = math.floor(timer.elapsed())
            print(f"{hhmm(seconds)}:{seconds % 60:02d} — {timer.state}")
            clear_before_prompt = False
        elif command in ("help", "aiuto", "?"):
            print(HELP)
            clear_before_prompt = False
        elif command:
            print("Comando sconosciuto. Digita aiuto per l'elenco.")
            clear_before_prompt = False


if __name__ == "__main__":
    raise SystemExit(main())
