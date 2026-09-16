import contextlib
import io
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import cronometro


class StopwatchTests(unittest.TestCase):
    def test_pause_time_is_excluded(self):
        monotonic_values = iter((10.0, 20.0, 30.0, 50.0))
        wall_values = iter(
            (
                datetime(2026, 9, 14, 17, 20, 45),
                datetime(2026, 9, 14, 17, 20, 55),
                datetime(2026, 9, 14, 17, 21, 5),
                datetime(2026, 9, 14, 18, 20, 45),
            )
        )
        timer = cronometro.Stopwatch(
            clock=lambda: next(monotonic_values),
            wall_clock=lambda: next(wall_values),
        )

        self.assertTrue(timer.start())
        self.assertTrue(timer.pause())
        self.assertTrue(timer.resume())
        self.assertTrue(timer.stop())

        self.assertEqual(timer.elapsed(), 30.0)
        self.assertEqual(timer.pause_elapsed(), 10.0)
        self.assertEqual(timer.started_at, datetime(2026, 9, 14, 17, 20, 45))
        self.assertEqual(timer.ended_at, datetime(2026, 9, 14, 18, 20, 45))
        self.assertEqual(len(timer.pauses), 1)
        self.assertEqual(timer.pauses[0].started_at, datetime(2026, 9, 14, 17, 20, 55))
        self.assertEqual(timer.pauses[0].ended_at, datetime(2026, 9, 14, 17, 21, 5))
        self.assertEqual(timer.pauses[0].seconds, 10.0)

    def test_stop_while_paused_counts_the_current_pause(self):
        monotonic_values = iter((10.0, 20.0, 35.0))
        wall_values = iter(
            (
                datetime(2026, 9, 14, 17, 20, 45),
                datetime(2026, 9, 14, 17, 20, 55),
                datetime(2026, 9, 14, 17, 21, 10),
            )
        )
        timer = cronometro.Stopwatch(
            clock=lambda: next(monotonic_values),
            wall_clock=lambda: next(wall_values),
        )

        timer.start()
        timer.pause()
        timer.stop()

        self.assertEqual(timer.elapsed(), 10.0)
        self.assertEqual(timer.pause_elapsed(), 15.0)
        self.assertEqual(timer.pauses[0].ended_at, datetime(2026, 9, 14, 17, 21, 10))
        self.assertEqual(timer.pauses[0].seconds, 15.0)

    def test_pause_reason_is_stored_with_start_and_end_times(self):
        monotonic_values = iter((10.0, 20.0, 35.0, 40.0))
        wall_values = iter(
            (
                datetime(2026, 9, 14, 9, 0, 0),
                datetime(2026, 9, 14, 9, 10, 0),
                datetime(2026, 9, 14, 9, 25, 0),
                datetime(2026, 9, 14, 9, 30, 0),
            )
        )
        timer = cronometro.Stopwatch(
            clock=lambda: next(monotonic_values),
            wall_clock=lambda: next(wall_values),
        )

        timer.start("Studiare")
        timer.pause()
        timer.set_pause_reason("Caffè")
        timer.resume()
        timer.stop()

        self.assertEqual(
            timer.pauses,
            [
                cronometro.PauseRecord(
                    datetime(2026, 9, 14, 9, 10, 0),
                    datetime(2026, 9, 14, 9, 25, 0),
                    15.0,
                    "Caffè",
                )
            ],
        )


class FormattingTests(unittest.TestCase):
    def test_duration_uses_hours_minutes_and_seconds(self):
        self.assertEqual(cronometro.format_duration(10800.9), "03:00:00")
        self.assertEqual(cronometro.format_duration(360061), "100:01:01")

    def test_date_is_written_in_italian(self):
        moment = datetime(2026, 9, 14)
        self.assertEqual(cronometro.format_date(moment), "Lunedì 14 Settembre 2026")

    def test_live_status_shows_duration_pauses_and_state(self):
        timer = mock.Mock()
        timer.elapsed.return_value = 3661.9
        timer.pause_elapsed.return_value = 65.2
        timer.state = "in pausa"

        self.assertEqual(
            cronometro.format_live_status(timer),
            "Durata: 01:01:01 | Pause: 00:01:05 | Stato: in pausa",
        )


class FileOutputTests(unittest.TestCase):
    def test_sessions_are_grouped_under_one_daily_heading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            first_start = datetime(2026, 9, 14, 17, 20, 45)
            first_end = datetime(2026, 9, 14, 20, 50, 45)
            second_start = datetime(2026, 9, 14, 21, 10, 0)
            second_end = datetime(2026, 9, 14, 21, 40, 30)

            cronometro.append_duration(
                path,
                first_start,
                10800,
                1800,
                first_end,
                "Completare il capitolo",
                True,
                (
                    cronometro.PauseRecord(
                        datetime(2026, 9, 14, 18, 10, 0),
                        datetime(2026, 9, 14, 18, 25, 0),
                        900,
                        "Telefonata",
                    ),
                    cronometro.PauseRecord(
                        datetime(2026, 9, 14, 19, 30, 0),
                        datetime(2026, 9, 14, 19, 45, 0),
                        900,
                    ),
                ),
            )
            cronometro.append_duration(
                path,
                second_start,
                1530,
                300,
                second_end,
                "Finire gli esercizi",
                False,
                (
                    cronometro.PauseRecord(
                        datetime(2026, 9, 14, 21, 20, 0),
                        datetime(2026, 9, 14, 21, 25, 0),
                        300,
                        "Acqua",
                    ),
                ),
            )

            self.assertEqual(
                cronometro.day_totals(path, first_end),
                (12330, 2100),
            )

            result, work_seconds, pause_seconds = cronometro.complete_day(
                path, first_end, "Capitolo completato, esercizi da continuare."
            )

            heading = "Lunedì 14 Settembre 2026"
            self.assertEqual(result, "completed")
            self.assertEqual(work_seconds, 12330)
            self.assertEqual(pause_seconds, 2100)
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                f"{heading}\n"
                f"{'=' * len(heading)}\n\n"
                "Sessione | Inizio   | Fine     | Lavoro   | Pause\n"
                "---------+----------+----------+----------+----------\n"
                "       1 | 17:20:45 | 20:50:45 | 03:00:00 | 00:30:00\n"
                "          Obiettivo : Completare il capitolo\n"
                "          Esito     : raggiunto\n"
                "          Pause:\n"
                "            # | Inizio   | Fine     | Durata   | Motivo\n"
                "          ----+----------+----------+----------+------------------------------\n"
                "            1 | 18:10:00 | 18:25:00 | 00:15:00 | Telefonata\n"
                "            2 | 19:30:00 | 19:45:00 | 00:15:00 | —\n\n"
                "       2 | 21:10:00 | 21:40:30 | 00:25:30 | 00:05:00\n"
                "          Obiettivo : Finire gli esercizi\n"
                "          Esito     : non raggiunto\n"
                "          Pause:\n"
                "            # | Inizio   | Fine     | Durata   | Motivo\n"
                "          ----+----------+----------+----------+------------------------------\n"
                "            1 | 21:20:00 | 21:25:00 | 00:05:00 | Acqua\n\n"
                "=========+==========+==========+==========+==========\n"
                "Totale   |          |          | 03:25:30 | 00:35:00\n\n"
                "Obiettivi raggiunti:\n"
                "  - Completare il capitolo\n"
                "Obiettivi non raggiunti:\n"
                "  - Finire gli esercizi\n"
                "Riepilogo finale: Capitolo completato, esercizi da continuare.\n",
            )

            repeated_result = cronometro.complete_day(path, first_end)
            self.assertEqual(repeated_result, ("already_complete", 12330, 2100))
            self.assertEqual(
                path.read_text(encoding="utf-8").count("Totale   |"), 1
            )

            cronometro.append_duration(
                path,
                datetime(2026, 9, 14, 22, 0, 0),
                1800,
                300,
                datetime(2026, 9, 14, 22, 35, 0),
                "Ripassare gli appunti",
                True,
            )
            self.assertNotIn(
                "Totale   |", path.read_text(encoding="utf-8")
            )
            self.assertEqual(
                cronometro.complete_day(
                    path, datetime(2026, 9, 14, 22, 35, 0)
                ),
                ("completed", 14130, 2400),
            )

    def test_table_header_is_added_after_entries_from_the_old_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            heading = "Lunedì 14 Settembre 2026"
            path.write_text(
                f"{heading}\n"
                f"{'=' * len(heading)}\n\n"
                "09:00:00 - 01:00:00 - 00:10:00 - 10:10:00\n",
                encoding="utf-8",
            )

            cronometro.append_duration(
                path,
                datetime(2026, 9, 14, 11, 0, 0),
                3600,
                600,
                datetime(2026, 9, 14, 12, 10, 0),
            )

            contents = path.read_text(encoding="utf-8")
            self.assertEqual(contents.count(cronometro.TABLE_HEADER), 1)
            self.assertTrue(
                contents.endswith(
                    "          Pause     : dettaglio non disponibile\n\n"
                )
            )

            result = cronometro.complete_day(
                path, datetime(2026, 9, 14, 12, 10, 0)
            )
            self.assertEqual(result, ("completed", 7200, 1200))

    def test_existing_content_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            path.write_text("Appunti precedenti", encoding="utf-8")
            start = datetime(2026, 9, 15, 9, 0, 0)
            end = datetime(2026, 9, 15, 9, 1, 0)

            cronometro.append_duration(path, start, 60, 0, end)

            self.assertTrue(path.read_text(encoding="utf-8").startswith("Appunti precedenti\n\n"))


class CommandFlowTests(unittest.TestCase):
    def test_stop_saves_and_complete_exits_with_daily_total(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            commands = mock.patch(
                "builtins.input",
                side_effect=(
                    "a",
                    "Scrivere il capitolo",
                    "p",
                    "Caffè",
                    "r",
                    "s",
                    "s",
                    "a",
                    "Correggere gli esercizi",
                    "s",
                    "n",
                    "c",
                    "Capitolo scritto; esercizi da rivedere.",
                ),
            )
            arguments = mock.patch.object(
                sys, "argv", ["cronometro.py", str(path)]
            )

            with commands, arguments, contextlib.redirect_stdout(io.StringIO()):
                result = cronometro.main()

            self.assertEqual(result, 0)
            contents = path.read_text(encoding="utf-8")
            self.assertIn("Totale   |", contents)
            self.assertIn("Totale complessivo", contents)
            self.assertIn("| Caffè", contents)
            self.assertRegex(
                contents,
                r"\d{2}:\d{2}:\d{2} \| \d{2}:\d{2}:\d{2} \| "
                r"\d+:\d{2}:\d{2} \| Caffè",
            )
            self.assertIn("  - Scrivere il capitolo", contents)
            self.assertIn("  - Correggere gli esercizi", contents)
            self.assertIn(
                "Riepilogo finale: Capitolo scritto; esercizi da rivedere.",
                contents,
            )
            self.assertEqual(len(cronometro.TABLE_ENTRY_RE.findall(contents)), 2)

    def test_exit_alias_saves_active_session_without_daily_total(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            output = io.StringIO()
            commands = mock.patch(
                "builtins.input",
                side_effect=("a", "Sessione temporanea", "e", "s"),
            )
            arguments = mock.patch.object(
                sys, "argv", ["cronometro.py", str(path)]
            )

            with commands, arguments, contextlib.redirect_stdout(output):
                result = cronometro.main()

            contents = path.read_text(encoding="utf-8")
            self.assertEqual(result, 0)
            self.assertIn(cronometro.ASCII_ART, output.getvalue())
            self.assertEqual(len(cronometro.TABLE_ENTRY_RE.findall(contents)), 1)
            self.assertNotIn("Totale   |", contents)

    def test_today_alias_displays_the_current_total(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            output = io.StringIO()
            commands = mock.patch("builtins.input", side_effect=("o", "e"))
            arguments = mock.patch.object(
                sys, "argv", ["cronometro.py", str(path)]
            )

            with commands, arguments, contextlib.redirect_stdout(output):
                result = cronometro.main()

            self.assertEqual(result, 0)
            self.assertIn(
                "Oggi — lavoro: 00:00:00 | pause: 00:00:00",
                output.getvalue(),
            )


class OverallSummaryTests(unittest.TestCase):
    def test_summary_is_rebuilt_from_daily_totals(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            path.write_text(
                "Somma totale delle ore lavorate\n"
                "===============================\n\n"
                "01:30\n\n"
                "Totale ore: 01:30\n"
                "================================\n\n"
                "Domenica 13 Settembre 2026\n"
                "==========================\n\n"
                "Totale: 01:30\n\n"
                "Lunedì 14 Settembre 2026\n"
                "========================\n\n"
                "Inizio   | Durata   | Pause    | Fine\n"
                "---------+----------+----------+---------\n"
                "09:00:00 | 00:45:00 | 00:05:00 | 09:50:00\n"
                "=========+==========+==========+=========\n"
                "Totale   | 00:45:00 | 00:05:00 |\n",
                encoding="utf-8",
            )

            overall_seconds = cronometro.update_overall_summary(path)

            contents = path.read_text(encoding="utf-8")
            self.assertEqual(overall_seconds, 8100)
            self.assertIn(
                "Domenica 13 Settembre 2026   | 01:30:00", contents
            )
            self.assertIn(
                "Lunedì 14 Settembre 2026     | 00:45:00", contents
            )
            self.assertIn(
                "Totale complessivo           | 02:15:00", contents
            )
            self.assertEqual(contents.count("Domenica 13 Settembre 2026"), 2)


if __name__ == "__main__":
    unittest.main()
