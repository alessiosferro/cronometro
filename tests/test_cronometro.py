import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import cronometro


class StopwatchTests(unittest.TestCase):
    def test_pause_time_is_excluded(self):
        monotonic_values = iter((10.0, 20.0, 30.0, 50.0))
        wall_values = iter(
            (
                datetime(2026, 9, 14, 17, 20, 45),
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

    def test_stop_while_paused_counts_the_current_pause(self):
        monotonic_values = iter((10.0, 20.0, 35.0))
        wall_values = iter(
            (
                datetime(2026, 9, 14, 17, 20, 45),
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


class FormattingTests(unittest.TestCase):
    def test_duration_uses_hours_minutes_and_seconds(self):
        self.assertEqual(cronometro.format_duration(10800.9), "03:00:00")
        self.assertEqual(cronometro.format_duration(360061), "100:01:01")

    def test_date_is_written_in_italian(self):
        moment = datetime(2026, 9, 14)
        self.assertEqual(cronometro.format_date(moment), "Lunedì 14 Settembre 2026")


class FileOutputTests(unittest.TestCase):
    def test_sessions_are_grouped_under_one_daily_heading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            first_start = datetime(2026, 9, 14, 17, 20, 45)
            first_end = datetime(2026, 9, 14, 20, 20, 45)
            second_start = datetime(2026, 9, 14, 21, 10, 0)
            second_end = datetime(2026, 9, 14, 21, 35, 30)

            cronometro.append_duration(path, first_start, 10800, 1800, first_end)
            cronometro.append_duration(path, second_start, 1530, 300, second_end)

            heading = "Lunedì 14 Settembre 2026"
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                f"{heading}\n"
                f"{'=' * len(heading)}\n\n"
                "17:20:45 - 03:00:00 - 00:30:00 - 20:20:45\n"
                "21:10:00 - 00:25:30 - 00:05:00 - 21:35:30\n",
            )

    def test_existing_content_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "studio.txt"
            path.write_text("Appunti precedenti", encoding="utf-8")
            start = datetime(2026, 9, 15, 9, 0, 0)
            end = datetime(2026, 9, 15, 9, 1, 0)

            cronometro.append_duration(path, start, 60, 0, end)

            self.assertTrue(path.read_text(encoding="utf-8").startswith("Appunti precedenti\n\n"))


if __name__ == "__main__":
    unittest.main()
