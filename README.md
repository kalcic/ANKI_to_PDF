# ANKI to PDF

This repository contains a script to export Anki decks to PDF via AnkiConnect. If the optional `ocrmypdf` package is installed, the script can run OCR on the generated PDF. Pages that already contain text are skipped to avoid unnecessary rasterization.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

The `ocrmypdf` package is listed in `requirements.txt`. It enables optional OCR when the script generates the PDF. Pages that already contain text are skipped by default, so OCR typically does not inflate the file size. If `ocrmypdf` is not installed, the script simply skips this step.

## Usage

Run the script with the deck name and desired output file:

```bash
python ANKI_to_PDF.py "My Deck" output.pdf
```

The script will connect to Anki using AnkiConnect, export the selected deck and save it to `output.pdf`.
