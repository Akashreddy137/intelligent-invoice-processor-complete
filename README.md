# InvoiceIQ - Intelligent Invoice and Receipt Processing

A Flask web application for invoice and receipt image processing.

## Included features

- Login and account registration
- Login/sign-up switching
- Client-side form validation
- Password show/hide
- Smooth authentication and dashboard transitions
- Animated buttons, inputs and feedback messages
- Responsive desktop, tablet and mobile interface
- Banking-style dashboard layout
- Invoice/receipt image upload with drag and drop
- OCR using Tesseract
- Field extraction for vendor, invoice number, date, address, tax and total
- Missing-field validation
- Category classification
- Duplicate detection
- Editable extracted fields and Save Correction
- Document search and deletion
- Per-user SQLite workspace
- Dockerfile with Tesseract for Linux deployment

## Run on Windows

1. Install Python 3.11 or 3.12.
2. Install Tesseract OCR and ensure it is available at:
   `C:\Program Files\Tesseract-OCR\tesseract.exe`
3. Open a terminal in this project folder.
4. Create a virtual environment:
   `python -m venv .venv`
5. Activate it:
   `.venv\Scripts\activate`
6. Install packages:
   `pip install -r requirements.txt`
7. Start:
   `python app.py`
8. Open:
   `http://127.0.0.1:5000`

## Render / Docker

The included Dockerfile installs Tesseract automatically and starts Gunicorn.

For a Render Docker deployment, use the repository containing:
- `app.py`
- `requirements.txt`
- `Dockerfile`
- `templates/index.html`
- `static/app.js`
- `static/style.css`
- `uploads/.gitkeep`

## Important project note

The current processing pipeline is an OCR + deterministic extraction foundation. It does not yet contain a trained LayoutLM/Donut model. If the academic project requires the deep-learning component to be demonstrated, that model layer should be integrated and evaluated separately rather than claiming it is already implemented.
