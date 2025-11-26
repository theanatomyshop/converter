"""Utilities for running and testing the batch converter script."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path


BATCH_FILE_NAME = "run_converter.bat"


def run_batch_file() -> str:
    """Execute the batch file that launches the converter.

    Returns
    -------
    str
        Combined stdout and stderr from the batch execution.

    Raises
    ------
    FileNotFoundError
        If the batch file does not exist alongside this module.
    RuntimeError
        If the current platform is not Windows or the batch file exits
        with a non-zero return code.
    """

    batch_path = Path(__file__).with_name(BATCH_FILE_NAME)
    if not batch_path.exists():
        raise FileNotFoundError(f"Batch file not found: {batch_path}")

    if platform.system() != "Windows":
        raise RuntimeError(
            "Batch files can only be executed on Windows. "
            "Run this test on a Windows machine to verify the launcher."
        )

    completed = subprocess.run(
        ["cmd", "/c", str(batch_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"Batch file exited with code {completed.returncode}.\n"
            f"stdout: {completed.stdout}\n"
            f"stderr: {completed.stderr}"
        )

    return completed.stdout + completed.stderr


def test_run_batch_file() -> bool:
    """Simple test to verify the converter batch file can run.

    The function executes the batch file and reports success or failure
    via its return value. Detailed errors are printed to help with
    troubleshooting.
    """

    try:
        output = run_batch_file()
    except Exception as exc:  # noqa: BLE001 - intentional broad capture for reporting
        print(f"run_converter.bat failed: {exc}")
        return False

    print("run_converter.bat executed successfully.")
    if output:
        print("--- Batch output start ---")
        print(output.rstrip())
        print("--- Batch output end ---")
    return True


if __name__ == "__main__":
    test_run_batch_file()
