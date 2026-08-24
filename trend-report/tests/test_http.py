from __future__ import annotations

import unittest
from unittest.mock import Mock

from src.http import HttpClient, HttpError


class HttpTests(unittest.TestCase):
    def test_http_no_exitoso_se_expone_como_error(self) -> None:
        response = Mock()
        response.ok = False
        response.status_code = 404
        response.url = "https://example.test/missing"
        response.headers = {}
        session = Mock()
        session.get.return_value = response

        client = HttpClient("TestAgent/0.1", retries=0, session=session)
        with self.assertRaises(HttpError):
            client.get_json("https://example.test/missing")


if __name__ == "__main__":
    unittest.main()
