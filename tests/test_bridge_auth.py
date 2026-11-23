"""Tests for the Polyconnect native-login application contract."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
AUTH_PATH = ROOT / "polyconnect_bridge" / "auth.py"
SPEC = importlib.util.spec_from_file_location("polyconnect_bridge_auth", AUTH_PATH)
assert SPEC is not None and SPEC.loader is not None
auth = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = auth
SPEC.loader.exec_module(auth)


class _Response:
    """Minimal requests.Response replacement for login tests."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


class NativeLoginContractTests(unittest.TestCase):
    """Verify the version declaration and server-provided application URL."""

    def test_login_declares_current_android_application_identity(self) -> None:
        token = "t" * 516
        application_url = (
            "https://polytropic.user-app.v2.pool.mytech-connect.io/from-native"
        )
        response = auth._make_terminal_signed(
            {"s": 0, "t": token, "url": application_url},
            "terminal-id",
            "terminal-key",
        )

        with (
            patch.object(auth.requests, "post", return_value=_Response(response)) as post,
            patch.object(auth.log, "info") as log_info,
        ):
            returned_token, returned_url = auth._login_remote(
                "USER@example.com ",
                "password",
                "terminal-id",
                "terminal-key",
            )

        self.assertEqual(returned_token, token)
        self.assertEqual(returned_url, application_url)
        self.assertEqual(
            post.call_args.args[0],
            f"{auth.BASE_URL}/Irc/Application/Login",
        )
        self.assertEqual(
            post.call_args.kwargs["headers"],
            {"Content-Type": "application/json"},
        )

        request_envelope = json.loads(post.call_args.kwargs["data"])
        protected = auth._decode_envelope(request_envelope)
        request_payload = json.loads(protected["sp"])
        args = request_payload["args"]
        self.assertEqual(args["av"], "9.1.3")
        self.assertEqual(args["pn"], "com.ckc_net.polytropic")
        self.assertEqual(args["aeid"], "userApp_polytropic")
        self.assertEqual(args["e"], "user@example.com")
        log_info.assert_called_once_with(
            "Polyconnect client identity: aeid=%s version=%s package=%s",
            "userApp_polytropic",
            "9.1.3",
            "com.ckc_net.polytropic",
        )

    def test_get_app_url_preserves_server_provided_endpoint(self) -> None:
        manager = auth.AuthManager.__new__(auth.AuthManager)
        manager._lock = threading.Lock()
        manager.credentials = auth.Credentials(token="session-token")
        manager._session_url = (
            "https://polytropic.user-app.v2.pool.mytech-connect.io/from-native"
        )

        self.assertEqual(
            manager.get_app_url(),
            "https://polytropic.user-app.v2.pool.mytech-connect.io/"
            "from-native/session-token",
        )

    def test_get_app_url_accepts_future_server_endpoint_without_rewrite(self) -> None:
        manager = auth.AuthManager.__new__(auth.AuthManager)
        manager._lock = threading.Lock()
        manager.credentials = auth.Credentials(token="session-token")
        manager._session_url = "https://future.example/from-native/"

        self.assertEqual(
            manager.get_app_url(),
            "https://future.example/from-native/session-token",
        )


if __name__ == "__main__":
    unittest.main()
