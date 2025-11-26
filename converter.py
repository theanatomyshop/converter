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

    csv_path = select_csv_file()
    dataframe = pd.read_csv(csv_path)
    print(dataframe)


if __name__ == "__main__":
    main()
