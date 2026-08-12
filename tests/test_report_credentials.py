import base64
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from report_credentials import decode_lime_password, encode_lime_password


class TestLimeReportCredentials(unittest.TestCase):
    def test_empty_password_is_empty(self):
        self.assertEqual(encode_lime_password(""), "")

    def test_encoded_password_is_base64_in_complete_rc5_blocks(self):
        encoded = encode_lime_password("temporary test password")
        decoded = base64.b64decode(encoded)
        self.assertEqual(len(decoded) % 8, 0)
        self.assertNotIn(b"temporary test password", decoded)

    def test_encoding_is_deterministic_for_lime_report(self):
        self.assertEqual(
            encode_lime_password("temporary test password"),
            encode_lime_password("temporary test password"),
        )

    def test_historical_lime_value_round_trips(self):
        historical = "dJlfSRL7RII="
        self.assertEqual(encode_lime_password(decode_lime_password(historical)), historical)


if __name__ == "__main__":
    unittest.main()
