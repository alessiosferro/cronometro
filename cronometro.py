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
SESSION_DETAILS_RE = re.compile(
    r"^[ \t]*\| Obiettivo: (?P<objective>.+)\n"
    r"^[ \t]*\| Esito: (?P<outcome>raggiunto|non raggiunto)$",
    re.MULTILINE,
)
COMPLETION_BLOCK_RE = re.compile(
    rf"^{re.escape(TABLE_TOTAL_SEPARATOR)}\n"
    r"Totale\s+\| \d+:\d{2}:\d{2} \| \d+:\d{2}:\d{2} \|\n?"
    r"[\s\S]*\Z",
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
ASCII_ART = r"""
   ___ ___  ___  _  _  ___  __  __ ___ _____ ___  ___
  / __| _ \/ _ \| \| |/ _ \|  \/  | __|_   _| _ \/ _ \
 | (__|   / (_) | .` | (_) | |\/| | _|  | | |   / (_) |
  \___|_|_\___/|_|\_|\___/|_|  |_|___| |_| |_|_\___/
""".strip("\n")

START_COMMANDS = ("start", "avvia", "a")
PAUSE_COMMANDS = ("pause", "pausa", "p")
RESUME_COMMANDS = ("resume", "riprendi", "r")
STOP_COMMANDS = ("stop", "s")
STATUS_COMMANDS = ("status", "stato", "st")
TODAY_COMMANDS = ("oggi", "giornata", "o")
COMPLETE_COMMANDS = ("complete", "completa", "c")
EXIT_COMMANDS = ("exit", "esci", "e", "q")
HELP_COMMANDS = ("help", "aiuto", "h", "?")


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
        self.objective = ""
        self.goal_achieved = None
        self.pause_reasons = []
        self.state = "pronto"

    def start(self, objective=""):
        if self.state != "pronto":
            return False
        self.since = self.clock()
        self.started_at = self.wall_clock()
        self.objective = objective
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
    return (
        f"Durata: {format_duration(timer.elapsed())} | "
        f"Pause: {format_duration(timer.pause_elapsed())} | "
        f"Stato: {timer.state}"
    )


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


def append_duration(
    path,
    started_at,
    seconds,
    pause_seconds,
    ended_at,
    objective="",
    goal_achieved=None,
    pause_reasons=(),
):
    date_heading = format_date(ended_at)
    heading_block = f"{date_heading}\n{'=' * len(date_heading)}"
    time_entry = (
        f"{started_at:%H:%M:%S} | {format_duration(seconds)} | "
        f"{format_duration(pause_seconds)} | {ended_at:%H:%M:%S}"
    )
    outcome = (
        "raggiunto"
        if goal_achieved is True
        else "non raggiunto"
        if goal_achieved is False
        else "non specificato"
    )
    detail_lines = [
        f"          | Obiettivo: {objective or 'Non specificato'}",
        f"          | Esito: {outcome}",
    ]
    detail_lines.extend(
        f"          | Motivo pausa: {reason}" for reason in pause_reasons
    )
    session_entry = "\n".join((time_entry, *detail_lines))

    mode = "r+b" if path.exists() else "w+b"
    with path.open(mode) as stream:
        stream.seek(0)
        existing = stream.read().decode("utf-8", errors="replace")
        addition = ""

        heading_position = existing.rfind(heading_block)
        if heading_position != -1:
            current_section = existing[heading_position:]
            previous_completion = COMPLETION_BLOCK_RE.search(current_section)
            if previous_completion:
                existing = (
                    existing[:heading_position]
                    + current_section[:previous_completion.start()]
                    + current_section[previous_completion.end():]
                )
                stream.seek(0)
                stream.write(existing.encode("utf-8"))
                stream.truncate()

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
        stream.write((addition + session_entry + "\n").encode("utf-8"))


def sum_session_entries(section):
    work_seconds = 0
    pause_seconds = 0
    entry_count = 0
    for pattern in (TABLE_ENTRY_RE, LEGACY_ENTRY_RE):
        for entry in pattern.finditer(section):
            work_seconds += duration_to_seconds(entry.group("work"))
            pause_seconds += duration_to_seconds(entry.group("pause"))
            entry_count += 1
    for entry in LEGACY_ENTRY_WITHOUT_PAUSE_RE.finditer(section):
        work_seconds += duration_to_seconds(entry.group("work"))
        entry_count += 1
    return entry_count, work_seconds, pause_seconds


def day_totals(path, moment):
    if not path.exists():
        return 0, 0
    existing = path.read_text(encoding="utf-8")
    date_heading = format_date(moment)
    heading_block = f"{date_heading}\n{'=' * len(date_heading)}"
    heading_position = existing.rfind(heading_block)
    if heading_position == -1:
        return 0, 0
    _, work_seconds, pause_seconds = sum_session_entries(
        existing[heading_position:]
    )
    return work_seconds, pause_seconds


def session_goals(section):
    reached = []
    not_reached = []
    for details in SESSION_DETAILS_RE.finditer(section):
        destination = (
            reached
            if details.group("outcome") == "raggiunto"
            else not_reached
        )
        destination.append(details.group("objective"))
    return reached, not_reached


def format_goal_summary(reached_goals, missed_goals, final_summary):
    lines = ["Obiettivi raggiunti:"]
    lines.extend(
        (f"  - {objective}" for objective in reached_goals),
    )
    if not reached_goals:
        lines.append("  - Nessuno")
    lines.append("Obiettivi non raggiunti:")
    lines.extend(
        (f"  - {objective}" for objective in missed_goals),
    )
    if not missed_goals:
        lines.append("  - Nessuno")
    lines.append(f"Riepilogo finale: {final_summary or '—'}")
    return "\n".join(lines) + "\n"


def complete_day(path, moment, final_summary=""):
    if not path.exists():
        return "no_sessions", 0, 0

    date_heading = format_date(moment)
    heading_block = f"{date_heading}\n{'=' * len(date_heading)}"

    with path.open("r+b") as stream:
        stream.seek(0)
        existing = stream.read().decode("utf-8", errors="replace")
        heading_position = existing.rfind(heading_block)
        if heading_position == -1:
            return "no_sessions", 0, 0

        current_section = existing[heading_position:]
        previous_total = TOTAL_ENTRY_RE.search(current_section)
        if previous_total:
            if "Obiettivi raggiunti:" in current_section and not final_summary:
                return (
                    "already_complete",
                    duration_to_seconds(previous_total.group("work")),
                    duration_to_seconds(previous_total.group("pause")),
                )
            reached_goals, missed_goals = session_goals(current_section)
            goal_summary = format_goal_summary(
                reached_goals, missed_goals, final_summary
            )
            summary_position = current_section.find("Obiettivi raggiunti:")
            if summary_position == -1:
                separator = "" if current_section.endswith("\n\n") else "\n"
                updated_section = current_section + separator + goal_summary
            else:
                updated_section = (
                    current_section[:summary_position] + goal_summary
                )
            stream.seek(0)
            stream.write(
                (existing[:heading_position] + updated_section).encode("utf-8")
            )
            stream.truncate()
            return (
                "already_complete",
                duration_to_seconds(previous_total.group("work")),
                duration_to_seconds(previous_total.group("pause")),
            )

        entry_count, work_seconds, pause_seconds = sum_session_entries(
            current_section
        )
        reached_goals, missed_goals = session_goals(current_section)

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
            f"{format_duration(pause_seconds)} |\n\n"
            + format_goal_summary(
                reached_goals, missed_goals, final_summary
            )
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
  start / avvia / a        Avvia la sessione.
  pausa / pause / p        Mette in pausa.
  riprendi / resume / r    Riprende la sessione.
  stato / status / st      Mostra durata effettiva e stato.
  oggi / giornata / o      Mostra il totale della giornata in corso.
  stop / s                 Ferma e salva, poi resta aperto.
  completa / complete / c  Chiude la giornata con i totali ed esce.
  esci / exit / e / q      Salva l'eventuale sessione ed esce.
  aiuto / help / h / ?     Mostra questi comandi.
Ctrl+C non interrompe il programma; Ctrl+D equivale a completa."""


def normalize_note(value):
    return " ".join(value.split())


def ask_objective():
    while True:
        try:
            objective = normalize_note(input("Obiettivo della sessione: "))
        except KeyboardInterrupt:
            print("\nAvvio annullato.")
            return None
        except EOFError:
            print("\nAvvio annullato.")
            return None
        if objective:
            return objective
        print("L'obiettivo è obbligatorio.")


def ask_optional(prompt):
    try:
        return normalize_note(input(prompt))
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


def ask_goal_outcome():
    while True:
        try:
            answer = input("Obiettivo raggiunto? [s/n]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        if answer in ("s", "si", "sì", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Rispondi con s oppure n.")


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
                timer.objective,
                timer.goal_achieved,
                timer.pause_reasons,
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
    print(
        f"{ASCII_ART}\n\nFile: {path}\n{HELP}\n"
        "Pronto. Digita start per cominciare."
    )
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

        if command in STOP_COMMANDS:
            if not timer.stop():
                print("Nessuna sessione avviata: nessuna riga salvata.")
                clear_before_prompt = False
                continue
            timer.goal_achieved = ask_goal_outcome()
            path, saved = save_timer(path, timer)
            if not saved:
                return 1
        elif command in COMPLETE_COMMANDS:
            clear_terminal()
            if timer.state in ("in corso", "in pausa"):
                timer.stop()
                timer.goal_achieved = ask_goal_outcome()
                path, saved = save_timer(path, timer)
                if not saved:
                    return 1
            final_summary = ask_optional(
                "Riepilogo finale delle attività (facoltativo): "
            )
            try:
                result, work_seconds, pause_seconds = complete_day(
                    path, datetime.now(), final_summary
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
        elif command in EXIT_COMMANDS:
            clear_terminal()
            if timer.state in ("in corso", "in pausa"):
                timer.stop()
                timer.goal_achieved = ask_goal_outcome()
                path, saved = save_timer(path, timer)
                if not saved:
                    return 1
            print("Cronometro chiuso senza completare la giornata.")
            return 0
        elif command in START_COMMANDS:
            if timer.state == "terminato":
                timer = Stopwatch()
            if timer.state != "pronto":
                print("Sessione già avviata. Usa riprendi se è in pausa.")
                clear_before_prompt = False
                continue
            objective = ask_objective()
            if objective is None:
                clear_before_prompt = False
                continue
            if timer.start(objective):
                print("Sessione avviata.")
        elif command in PAUSE_COMMANDS:
            if timer.pause():
                reason = ask_optional("Motivo della pausa (facoltativo): ")
                if reason:
                    timer.pause_reasons.append(reason)
                print("In pausa.")
            else:
                print("La sessione non è in corso.")
                clear_before_prompt = False
        elif command in RESUME_COMMANDS:
            if timer.resume():
                print("Sessione ripresa.")
            else:
                print("La sessione non è in pausa.")
                clear_before_prompt = False
        elif command in STATUS_COMMANDS:
            seconds = math.floor(timer.elapsed())
            print(f"{hhmm(seconds)}:{seconds % 60:02d} — {timer.state}")
            clear_before_prompt = False
        elif command in TODAY_COMMANDS:
            try:
                work_seconds, pause_seconds = day_totals(path, datetime.now())
            except OSError as error:
                print(f"Lettura del totale giornaliero non riuscita: {error}")
                clear_before_prompt = False
                continue
            if timer.state in ("in corso", "in pausa"):
                work_seconds += timer.elapsed()
                pause_seconds += timer.pause_elapsed()
            print(
                f"Oggi — lavoro: {format_duration(work_seconds)} | "
                f"pause: {format_duration(pause_seconds)}"
            )
            clear_before_prompt = False
        elif command in HELP_COMMANDS:
            print(HELP)
            clear_before_prompt = False
        elif command:
            print("Comando sconosciuto. Digita aiuto per l'elenco.")
            clear_before_prompt = False


if __name__ == "__main__":
    raise SystemExit(main())
