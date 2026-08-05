import unittest

from servicepilot import __version__, check_health


class SmokeTest(unittest.TestCase):
    def test_package_health(self) -> None:
        report = check_health()

        self.assertEqual(report.service, "servicepilot")
        self.assertEqual(report.version, __version__)
        self.assertEqual(report.status, "ok")
        self.assertTrue(report.python_version)


if __name__ == "__main__":
    unittest.main()

