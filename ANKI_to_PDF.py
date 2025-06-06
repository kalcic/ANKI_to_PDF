# -*- coding: utf-8 -*-
import requests # Pro komunikaci s AnkiConnect
import json
import base64 # Pro dekódování mediálních souborů
import argparse
import os
import io
import re
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                PageBreak, Flowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import navy, black, red
# Importy pro registraci TTF fontu
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Konfigurace ---
ANKICONNECT_URL = "http://127.0.0.1:8765" # Standardní adresa AnkiConnect
ANKICONNECT_VERSION = 6

# Seznamy názvů polí
QUESTION_FIELD_NAMES = ["front", "question", "otázka", "q", "term", "text"]
ANSWER_FIELD_NAMES = ["back", "answer", "odpověď", "a", "definition", "back extra"]

# --- Pomocné Třídy a Funkce ---

class ResizableImage(Flowable):
    """ Vlastní Flowable pro obrázek, který se přizpůsobí šířce stránky. """
    def __init__(self, img_data, max_width, max_height=None):
        self.img_data = img_data
        self.max_width = max_width
        self.max_height = max_height
        self._img_width = 0
        self._img_height = 0
        self.drawWidth = 0
        self.drawHeight = 0
        try:
            img_reader = ImageReader(io.BytesIO(self.img_data))
            self._img_width, self._img_height = img_reader.getSize()
        except Exception as e:
            print(f"   WARN: Nelze načíst rozměry obrázku: {e}")
        if self._img_width > 0 and self._img_height > 0:
            aspect_ratio = self._img_height / float(self._img_width)
            self.drawWidth = min(self.max_width, self._img_width)
            self.drawHeight = self.drawWidth * aspect_ratio
            if self.max_height and self.drawHeight > self.max_height:
                self.drawHeight = self.max_height
                self.drawWidth = self.drawHeight / aspect_ratio
            if self.drawHeight > A4[1] * 0.8: # Max 80% výšky A4
                 scale_factor = (A4[1] * 0.8) / self.drawHeight
                 self.drawHeight *= scale_factor
                 self.drawWidth *= scale_factor
        self.width = self.drawWidth
        self.height = self.drawHeight

    def draw(self):
        """ Vykreslí obrázek na plátno. """
        if self.width > 0 and self.height > 0:
            try:
                img = Image(io.BytesIO(self.img_data), width=self.drawWidth, height=self.drawHeight)
                img.drawOn(self.canv, 0, 0)
            except Exception as e:
                print(f"   ERROR: Chyba při vykreslování obrázku: {e}")

def parse_html_content(html_text):
    """Analyzuje HTML obsah pole, extrahuje text a názvy obrázkových souborů."""
    if not html_text:
        return "", []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'html.parser')
    except Exception as e:
        print(f"   WARN: Chyba při parsování HTML: {e}. Obsah pole: {html_text[:100]}...")
        return html_text, []
    img_filenames = []
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src')
        if src:
            img_filenames.append(src)
        img_tag.decompose()
    placeholder = "||NEWLINE||"
    for br in soup.find_all('br'):
        br.insert_after(placeholder)
        br.decompose()
    text_content = soup.get_text(separator='\n', strip=True)
    text_content = text_content.replace(placeholder, '\n')
    lines = (line.strip() for line in text_content.splitlines())
    cleaned_text = '\n'.join(line for line in lines if line)
    cleaned_text = re.sub(r' +', ' ', cleaned_text)
    return cleaned_text, img_filenames

# --- Funkce pro AnkiConnect ---

def anki_request(action, **params):
    """ Odešle požadavek na AnkiConnect a vrátí výsledek. """
    payload = json.dumps({"action": action, "version": ANKICONNECT_VERSION, "params": params})
    try:
        response = requests.post(ANKICONNECT_URL, data=payload)
        response.raise_for_status()
        response_json = response.json()
        if 'error' in response_json and response_json['error'] is not None:
            print(f"ERROR: Chyba AnkiConnect API ({action}): {response_json['error']}")
            return None
        return response_json.get('result')
    except requests.exceptions.ConnectionError:
        print(f"ERROR: Nepodařilo se připojit k AnkiConnect na {ANKICONNECT_URL}.")
        print("       Ujistěte se, že Anki běží a doplněk AnkiConnect je nainstalován a aktivní.")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Chyba při komunikaci s AnkiConnect ({action}): {e}")
        return None
    except json.JSONDecodeError:
        print(f"ERROR: AnkiConnect vrátil neplatnou JSON odpověď pro akci '{action}'. Obsah: {response.text[:200]}...")
        return None

def get_media_data(filename):
    """ Získá binární data mediálního souboru přes AnkiConnect. """
    result = anki_request('retrieveMediaFile', filename=filename)
    if result:
        try:
            return base64.b64decode(result)
        except (TypeError, ValueError) as e:
            print(f"   ERROR: Chyba při dekódování base64 dat pro soubor '{filename}': {e}")
            return None
    return None

# --- Hlavní Logika ---

def extract_anki_data_connect(deck_name):
    """ Extrahuje data kartiček pro daný balíček pomocí AnkiConnect. """
    print(f"INFO: Získávám data pro balíček '{deck_name}' pomocí AnkiConnect...")
    query = f'deck:"{deck_name}"'
    print(f"INFO: Hledám karty pro dotaz: {query}")
    card_ids = anki_request('findCards', query=query)
    if card_ids is None:
        print("ERROR: Nepodařilo se získat ID karet z AnkiConnect.")
        return None
    if not card_ids:
        print(f"INFO: V balíčku '{deck_name}' nebyly nalezeny žádné karty.")
        return []
    print(f"INFO: Nalezeno {len(card_ids)} karet v balíčku.")
    batch_size = 100
    extracted_notes = {}
    for i in range(0, len(card_ids), batch_size):
        batch_ids = card_ids[i:i+batch_size]
        print(f"INFO: Zpracovávám dávku karet {i+1}-{min(i+batch_size, len(card_ids))}...")
        cards_info = anki_request('cardsInfo', cards=batch_ids)
        if not cards_info:
            print(f"WARN: Nepodařilo se získat informace pro dávku karet ID: {batch_ids[:5]}...")
            continue
        for card_info in cards_info:
            note_id = card_info.get('note')
            fields_data = card_info.get('fields', {})
            if not note_id or not fields_data:
                print(f"WARN: Chybí note ID nebo data polí pro kartu ID {card_info.get('cardId')}")
                continue
            if note_id not in extracted_notes:
                 q_field_name = None
                 a_field_name = None
                 field_names_lower = {name.lower(): name for name in fields_data.keys()}
                 for name in QUESTION_FIELD_NAMES:
                     if name in field_names_lower:
                         q_field_name = field_names_lower[name]
                         break
                 for name in ANSWER_FIELD_NAMES:
                      if name in field_names_lower:
                         a_field_name = field_names_lower[name]
                         break
                 if q_field_name and a_field_name:
                     q_html = fields_data.get(q_field_name, {}).get('value', '')
                     a_html = fields_data.get(a_field_name, {}).get('value', '')
                     q_text, q_img_files = parse_html_content(q_html)
                     a_text, a_img_files = parse_html_content(a_html)
                     extracted_notes[note_id] = {
                         "note_id": note_id,
                         "model_name": card_info.get('modelName', 'Neznámý model'),
                         "q_text": q_text,
                         "q_images": q_img_files,
                         "a_text": a_text,
                         "a_images": a_img_files,
                     }
                 else:
                     print(f"   WARN: Pro poznámku ID {note_id} (model '{card_info.get('modelName')}') se nepodařilo najít pole pro Otázku/Odpověď.")
                     print(f"         Dostupná pole: {list(fields_data.keys())}")
    print(f"INFO: Načtena data pro {len(extracted_notes)} unikátních poznámek.")
    return list(extracted_notes.values())

def create_pdf_connect(cards_data, output_pdf_path):
    """ Vytvoří PDF soubor z extrahovaných dat kartiček (verze pro AnkiConnect). """
    if not cards_data:
        print("INFO: Nebyla nalezena žádná data kartiček pro generování PDF.")
        return

    print(f"INFO: Generuji PDF: {output_pdf_path}")
    try:
        # --- Registrace TTF fontu s podporou UTF-8 ---
        font_path = 'DejaVuSans.ttf'  # Předpokládáme, že DejaVuSans.ttf je ve stejné složce
        font_name = 'DejaVu'        # Jméno, pod kterým budeme font používat

        default_font = 'Helvetica' # Výchozí, pokud se registrace nepodaří
        try:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                print(f"INFO: Úspěšně zaregistrován font '{font_name}' z '{font_path}'.")
                default_font = font_name # Nastavíme DejaVu jako výchozí
            else:
                print(f"ERROR: Soubor fontu '{font_path}' nebyl nalezen ve stejné složce jako skript.")
                print("       Ujistěte se, že 'DejaVuSans.ttf' je přítomen.")
                print("       PDF bude použito s výchozím fontem (může mít problémy s diakritikou).")
        except Exception as e:
            print(f"ERROR: Nepodařilo se zaregistrovat font z '{font_path}': {e}")
            print("       PDF bude použito s výchozím fontem (může mít problémy s diakritikou).")
        # --- Konec registrace fontu ---

        doc = SimpleDocTemplate(output_pdf_path, pagesize=A4,
                                leftMargin=1.5*cm, rightMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        story = []

        # Vlastní styly - NASTAVÍME NÁŠ FONT (nebo výchozí, pokud selhalo)
        title_style = ParagraphStyle(name='CardTitle', parent=styles['h2'], alignment=TA_LEFT, textColor=navy, spaceAfter=8, fontName=default_font)
        text_style = ParagraphStyle(name='CardText', parent=styles['Normal'], spaceAfter=8, leading=14, fontName=default_font)
        text_style_error = ParagraphStyle(name='CardTextError', parent=styles['Italic'], spaceAfter=4, textColor=red, fontName=default_font)

        available_width = doc.width

        for i, card in enumerate(cards_data):
            # --- Otázka ---
            story.append(Paragraph("Otázka:", title_style))
            if card['q_text']:
                text_with_br = card['q_text'].replace('\n', '<br/>')
                try:
                    # Správné escapování pro XML v ReportLab
                    safe_text = text_with_br.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_text, text_style))
                except ValueError as e:
                     print(f"   ERROR: Chyba ReportLab při zpracování odstavce (otázka) ID {card.get('note_id')}: {e}")
                     print(f"          Původní text (zkráceno): {text_with_br[:200]}...")
                     story.append(Paragraph("[Chyba formátování textu otázky]", text_style_error))
            else:
                story.append(Paragraph("[Prázdná otázka]", text_style_error))

            # Obrázky k otázce
            for img_filename in card['q_images']:
                print(f"   INFO: Načítám médium (Q): {img_filename}")
                img_data = get_media_data(img_filename)
                if img_data:
                    res_img = ResizableImage(img_data, max_width=available_width * 0.9)
                    if res_img.width > 0 :
                         story.append(res_img)
                         story.append(Spacer(1, 0.2*cm))
                    else:
                         story.append(Paragraph(f"[Obrázek '{img_filename}' nelze zobrazit]", text_style_error))
                else:
                     print(f"   WARN: Nepodařilo se načíst data pro obrázek '{img_filename}' přes AnkiConnect.")
                     story.append(Paragraph(f"[Obrázek '{img_filename}' se nepodařilo načíst]", text_style_error))

            story.append(Spacer(1, 0.6*cm))

            # --- Odpověď ---
            story.append(Paragraph("Odpověď:", title_style))
            if card['a_text']:
                text_with_br = card['a_text'].replace('\n', '<br/>')
                try:
                    # Správné escapování pro XML v ReportLab
                    safe_text = text_with_br.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_text, text_style))
                except ValueError as e:
                     print(f"   ERROR: Chyba ReportLab při zpracování odstavce (odpověď) ID {card.get('note_id')}: {e}")
                     print(f"          Původní text (zkráceno): {text_with_br[:200]}...")
                     story.append(Paragraph("[Chyba formátování textu odpovědi]", text_style_error))
            else:
                 story.append(Paragraph("[Prázdná odpověď]", text_style_error))

             # Obrázky k odpovědi
            for img_filename in card['a_images']:
                print(f"   INFO: Načítám médium (A): {img_filename}")
                img_data = get_media_data(img_filename)
                if img_data:
                    res_img = ResizableImage(img_data, max_width=available_width * 0.9)
                    if res_img.width > 0:
                         story.append(res_img)
                         story.append(Spacer(1, 0.2*cm))
                    else:
                         story.append(Paragraph(f"[Obrázek '{img_filename}' nelze zobrazit]", text_style_error))
                else:
                     print(f"   WARN: Nepodařilo se načíst data pro obrázek '{img_filename}' přes AnkiConnect.")
                     story.append(Paragraph(f"[Obrázek '{img_filename}' se nepodařilo načíst]", text_style_error))

            # Oddělovač
            if i < len(cards_data) - 1:
                 story.append(PageBreak())

        # Sestavení PDF
        doc.build(story)
        print(f"INFO: PDF úspěšně vygenerováno: {output_pdf_path}")

        # Spustit OCR v českém jazyce, pokud je dostupná knihovna ocrmypdf
        apply_ocr_to_pdf(output_pdf_path, lang="ces")

    except Exception as e:
        print(f"ERROR: Neočekávaná chyba při generování PDF: {e}")
        import traceback
        traceback.print_exc()


def apply_ocr_to_pdf(pdf_path, lang="ces"):
    """Spustí OCR nad zadaným PDF a výsledek uloží zpět."""
    try:
        import ocrmypdf
    except ImportError:
        print("WARN: Knihovna 'ocrmypdf' není nainstalována. OCR bude přeskočeno.")
        return

    temp_output = pdf_path + ".ocr.tmp.pdf"
    try:
        # Avoid PDF/A conversion which can fail on very large documents
        ocrmypdf.ocr(pdf_path, temp_output, language=lang, force_ocr=True,
                     output_type="pdf")
        os.replace(temp_output, pdf_path)
        print(f"INFO: OCR dokončeno: {pdf_path}")
    except Exception as e:
        print(f"ERROR: Chyba při provádění OCR: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)


def main():
    """ Hlavní funkce - verze pro AnkiConnect. """
    parser = argparse.ArgumentParser(description="Extrahuje data z Anki pomocí AnkiConnect a exportuje je do PDF.")
    parser.add_argument("deck_name", help="Přesný název Anki balíčku, který chcete exportovat.")
    parser.add_argument("output_pdf", help="Cesta pro výstupní PDF soubor.")

    args = parser.parse_args()

    # Zkontrolujeme, zda je nainstalována BeautifulSoup
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("ERROR: Knihovna 'BeautifulSoup4' není nainstalována.")
        print("       Spusťte: pip install beautifulsoup4")
        return

    # Krok 1: Zkusit se připojit a získat data
    cards_data = extract_anki_data_connect(args.deck_name)

    # Krok 2: Vytvořit PDF, pokud máme data
    if cards_data:
        create_pdf_connect(cards_data, args.output_pdf)
    elif cards_data is None:
         print("INFO: Generování PDF přeskočeno kvůli chybám při komunikaci s AnkiConnect.")
    else:
         print("INFO: Generování PDF přeskočeno, protože v balíčku nebyly nalezeny žádné zpracovatelné karty.")


if __name__ == "__main__":
    main()
