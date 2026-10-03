import unittest
from unittest.mock import MagicMock, patch

from plex.routes import (
    TRANSPORT_MODES,
    calculate_buffered_minutes,
    compute_route_duration,
    parse_daily_commute_plan,
    serialize_daily_commute_plan,
)


class TestRoutesEngine(unittest.TestCase):
    def test_calculate_buffered_minutes(self):
        # 10m * 1.25 = 12.5 -> ceil(12.5/5)*5 = 15
        self.assertEqual(calculate_buffered_minutes(10, 1.25), 15)
        # 20m * 1.25 = 25 -> 25
        self.assertEqual(calculate_buffered_minutes(20, 1.25), 25)
        # 2m * 1.0 = 2 -> min 5
        self.assertEqual(calculate_buffered_minutes(2, 1.0), 5)
        # 30m * 1.35 = 40.5 -> 45
        self.assertEqual(calculate_buffered_minutes(30, 1.35), 45)

    def test_parse_and_serialize_idempotent(self):
        sample_ans = [
            "lecture [1h30] (10am) @Campus\n",
            "@Campus → @Office [30] 🚗 //{::commute::}\n",
            "lab [2h] (14:00) @Office\n",
            "workout [1h] @Gym\n",
            "-------------\n",
        ]
        parsed = parse_daily_commute_plan(sample_ans)
        self.assertEqual(len(parsed["tasks"]), 3)
        self.assertEqual(len(parsed["commutes"]), 1)

        commute = parsed["commutes"][0]
        self.assertEqual(commute["fromLoc"], "@Campus")
        self.assertEqual(commute["toLoc"], "@Office")
        self.assertEqual(commute["mode"], "drive")
        self.assertEqual(commute["duration"], "30")

        serialized = serialize_daily_commute_plan(parsed["tasks"], parsed["commutes"])
        # Second parse
        second_parsed = parse_daily_commute_plan(serialized.splitlines(keepends=True))
        self.assertEqual(len(second_parsed["tasks"]), 3)
        self.assertEqual(len(second_parsed["commutes"]), 1)
        self.assertEqual(second_parsed["commutes"][0]["fromLoc"], "@Campus")
        self.assertEqual(second_parsed["commutes"][0]["toLoc"], "@Office")

    def test_compute_route_duration_mock_google(self):
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"routes": [{"duration": "1200s", "distanceMeters": 15000}]}'
        )
        mock_response.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", return_value=mock_response):
            buffered, raw, is_live = compute_route_duration(
                "742 Evergreen Terr",
                "500 Corporate Way",
                mode="drive",
                buffer_multiplier=1.25,
                api_key="mock_key_12345",
            )
            self.assertEqual(raw, 20)  # 1200s = 20 mins
            self.assertEqual(buffered, 25)  # 20 * 1.25 = 25
            self.assertTrue(is_live)


if __name__ == "__main__":
    unittest.main()
