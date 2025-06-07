# ANKI to PDF

This repository contains a script to export Anki decks to PDF via AnkiConnect. If the optional `ocrmypdf` package is installed, the script can run OCR on the generated PDF. The script performs OCR on each page so text contained in images is recognized.

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

The `ocrmypdf` package is listed in `requirements.txt`. It enables optional OCR when the script generates the PDF. By processing every page, the script can extract text from screenshots or other images. If `ocrmypdf` is not installed, the script simply skips this step.

## Usage

Run the script with the deck name and desired output file. OCR language and
force options can be provided via flags:

```bash
python ANKI_to_PDF.py "My Deck" output.pdf --ocr-lang "ces+chi_sim" --force-ocr
```

The script will connect to Anki using AnkiConnect, export the selected deck and save it to `output.pdf`. If OCR fails because the PDF already contains text, it automatically retries with the `--force-ocr` option.
