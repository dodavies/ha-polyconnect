"""Tests for the bridge add-on version diagnostic."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
BRIDGE = ROOT / "polyconnect_bridge"


class BridgeVersionTests(unittest.TestCase):
    """Keep the server diagnostic aligned with the add-on manifest."""

    def test_server_reads_bridge_version_from_environment(self) -> None:
        tree = ast.parse((BRIDGE / "server.py").read_text())
        assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "BRIDGE_VERSION"
                for target in node.targets
            )
        )
        expression = compile(
            ast.Expression(assignment.value),
            filename=str(BRIDGE / "server.py"),
            mode="eval",
        )

        with patch.dict(os.environ, {"POLYCONNECT_BRIDGE_VERSION": "test-version"}):
            self.assertEqual(eval(expression, {"os": os}), "test-version")

    def test_run_script_exports_manifest_version(self) -> None:
        manifest_version = next(
            line.split('"')[1]
            for line in (BRIDGE / "config.yaml").read_text().splitlines()
            if line.startswith("version: ")
        )

        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            shutil.copy(BRIDGE / "run.sh", temp / "run.sh")
            shutil.copy(BRIDGE / "config.yaml", temp / "config.yaml")
            fake_bin = temp / "bin"
            fake_bin.mkdir()
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-c\" ]; then exit 0; fi\n"
                "printf 'server-version=%s\\n' \"$POLYCONNECT_BRIDGE_VERSION\"\n"
            )
            fake_python.chmod(0o755)
            fake_mkdir = fake_bin / "mkdir"
            fake_mkdir.write_text("#!/bin/sh\nexit 0\n")
            fake_mkdir.chmod(0o755)
            env = os.environ | {"PATH": f"{fake_bin}:{os.environ['PATH']}"}

            result = subprocess.run(
                ["bash", str(temp / "run.sh")],
                check=False,
                capture_output=True,
                env=env,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            f"Starting Polyconnect Bridge v{manifest_version}...",
            result.stdout,
        )
        self.assertIn(f"server-version={manifest_version}", result.stdout)


if __name__ == "__main__":
    unittest.main()
