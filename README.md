# ANKI to PDF

This repository contains a script to export Anki decks to PDF via AnkiConnect. If the optional `ocrmypdf` package is installed, OCR will be performed on the generated PDF.

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

The `ocrmypdf` package is listed in `requirements.txt`. It enables OCR when the script generates the PDF. If it is not installed, the script skips the OCR step.

## Usage

Run the script with the deck name and desired output file:

```bash
python ANKI_to_PDF.py "My Deck" output.pdf
```

The script will connect to Anki using AnkiConnect, export the selected deck and save it to `output.pdf`.
