"""Select and display a CSV file using a Tkinter file dialog."""

from __future__ import annotations

import sys
from pathlib import Path
from tkinter import Tk, filedialog

import pandas as pd


def select_csv_file() -> Path:
    """Open a file dialog to select a CSV file and return the path.

    Raises
    ------
    SystemExit
        If no file is selected or the chosen file is not a CSV.
    """

    root = Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select a CSV file",
        filetypes=[("CSV files", "*.csv")],
        defaultextension=".csv",
    )

    # Ensure the root window is properly cleaned up regardless of selection outcome.
    root.update()
    root.destroy()

    if not file_path:
        print("No file selected. Exiting.")
        sys.exit(1)

    selected_path = Path(file_path)
    if selected_path.suffix.lower() != ".csv":
        print("Selected file is not a CSV. Exiting.")
        sys.exit(1)

    return selected_path


def main() -> None:
    """Run the CSV selection and display the file contents."""

    script_dir = Path(__file__).resolve().parent
    default_csv = script_dir / "input.csv"

    if not default_csv.exists():
        print("The default input.csv file could not be found. Exiting.")
        sys.exit(1)

    expected_headers = list(pd.read_csv(default_csv, nrows=0).columns)

    csv_path = select_csv_file()
    selected_headers = list(pd.read_csv(csv_path, nrows=0).columns)

    missing_headers = [header for header in expected_headers if header not in selected_headers]
    additional_headers = [header for header in selected_headers if header not in expected_headers]

    if missing_headers or additional_headers:
        print("The selected CSV file headers do not match the expected format.")
        if missing_headers:
            print(f"Missing headers: {missing_headers}")
        if additional_headers:
            print(f"Unexpected headers: {additional_headers}")
        sys.exit(1)

    dataframe = pd.read_csv(csv_path)
    print(dataframe)


if __name__ == "__main__":
    main()
