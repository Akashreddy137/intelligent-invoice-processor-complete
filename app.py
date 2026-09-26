import os, re, sqlite3, hashlib, secrets
from datetime import datetime
from pathlib import Path
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps, ImageEnhance
import pytesseract

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)
DB = BASE / "invoice.db"

if os.name == "nt":
    tesseract_path = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if tesseract_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
ALLOWED = {"png","jpg","jpeg","webp","bmp","tif","tiff"}

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        vendor TEXT,
        invoice_no TEXT,
        doc_date TEXT,
        address TEXT,
        tax REAL DEFAULT 0,
        total REAL DEFAULT 0,
        category TEXT,
        raw_text TEXT,
        file_hash TEXT NOT NULL,
        status TEXT,
        created_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        UNIQUE(user_id, file_hash)
    )""")
    con.commit()
    con.close()

def clean(s):
    return re.sub(r"\s+", " ", s or "").strip(" :\t\r\n")

def money(s):
    if not s: return 0.0
    vals = re.findall(r"\d+(?:\.\d{1,2})?", str(s).replace(",", ""))
    return float(vals[-1]) if vals else 0.0

def extract(text):
    lines = [clean(x) for x in text.splitlines() if clean(x)]
    vendor = ""
    for line in lines[:8]:
        if not re.search(r"(invoice|receipt|tax invoice|bill|gst|date|total|amount|phone|email)", line, re.I) and len(line) >= 3:
            vendor = line[:120]; break

    inv = ""
    for p in [
        r"(?:invoice\s*(?:no|number|#)|inv\s*(?:no|#))\s*[:\-]?\s*([A-Z0-9][A-Z0-9\/\-_\.]+)",
        r"(?:receipt\s*(?:no|number|#))\s*[:\-]?\s*([A-Z0-9][A-Z0-9\/\-_\.]+)"
    ]:
        m = re.search(p, text, re.I)
        if m: inv = m.group(1); break

    date = ""
    for p in [
        r"\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b",
        r"\b\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}\b",
        r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}\b"
    ]:
        m = re.search(p, text, re.I)
        if m: date = m.group(0); break

    tax = 0.0
    for p in [
        r"(?:GST|tax|vat)[^\d]{0,20}[₹$]?\s*([\d,]+(?:\.\d{1,2})?)",
        r"(?:GST|tax|vat)[^\d]{0,20}([\d,]+(?:\.\d{1,2})?)"
    ]:
        m = re.search(p, text, re.I)
        if m: tax = money(m.group(1)); break

    total = 0.0
    for p in [r"(?:grand\s*total|total\s*amount|net\s*amount|amount\s*payable|total)[^\d]{0,25}[₹$]?\s*([\d,]+(?:\.\d{1,2})?)"]:
        matches = re.findall(p, text, re.I)
        if matches:
            total = money(matches[-1]); break
    if not total:
        amounts = re.findall(r"(?:₹|Rs\.?|INR|\$)\s*([\d,]+(?:\.\d{1,2})?)", text, re.I)
        if amounts: total = money(amounts[-1])

    address = ""
    for line in lines:
        if re.search(r"\b(address|road|street|st\.|hyderabad|telangana|india|pincode|pin)\b", line, re.I):
            address = line[:200]; break

    blob = (vendor + " " + text).lower()
    if any(x in blob for x in ["restaurant","food","cafe","bakery","hotel"]): category = "Food"
    elif any(x in blob for x in ["uber","ola","flight","airline","bus","transport","fuel","petrol"]): category = "Travel"
    elif any(x in blob for x in ["electricity","water bill","internet","utility"]): category = "Utilities"
    elif any(x in blob for x in ["office","stationery","printer","software"]): category = "Office"
    elif any(x in blob for x in ["shirt","clothing","mall","store","fashion"]): category = "Shopping"
    else: category = "Other"

    missing = []
    if not vendor: missing.append("Company/Vendor")
    if not inv: missing.append("Invoice Number")
    if not date: missing.append("Date")
    if not total: missing.append("Total Amount")
    return dict(vendor=vendor, invoice_no=inv, doc_date=date, address=address,
                tax=tax, total=total, category=category, missing=missing)

def ocr_image(path):
    im = Image.open(path).convert("RGB")
    im = ImageOps.exif_transpose(im)
    gray = ImageOps.grayscale(im)
    gray = ImageEnhance.Contrast(gray).enhance(1.6)
    gray = gray.resize((gray.width * 2, gray.height * 2))
    return pytesseract.image_to_string(gray, config="--psm 6")

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify(error="Please log in to continue.", auth_required=True), 401
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = clean(data.get("name"))
    email = clean(data.get("email")).lower()
    password = str(data.get("password") or "")
    if len(name) < 2: return jsonify(error="Enter your full name."), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email): return jsonify(error="Enter a valid email address."), 400
    if len(password) < 8: return jsonify(error="Password must contain at least 8 characters."), 400
    con = db()
    try:
        cur = con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
                          (name,email,generate_password_hash(password),datetime.now().isoformat(timespec="seconds")))
        con.commit()
        uid = cur.lastrowid
    except sqlite3.IntegrityError:
        con.close()
        return jsonify(error="An account with this email already exists."), 409
    con.close()
    session.clear(); session["user_id"] = uid
    return jsonify(ok=True, user={"name":name,"email":email})

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = clean(data.get("email")).lower()
    password = str(data.get("password") or "")
    con = db()
    user = con.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    con.close()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Email or password is incorrect."), 401
    session.clear(); session["user_id"] = user["id"]
    return jsonify(ok=True, user={"name":user["name"],"email":user["email"]})

@app.post("/api/auth/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/auth/me")
def me():
    if "user_id" not in session: return jsonify(authenticated=False)
    con=db(); user=con.execute("SELECT id,name,email FROM users WHERE id=?", (session["user_id"],)).fetchone(); con.close()
    if not user:
        session.clear(); return jsonify(authenticated=False)
    return jsonify(authenticated=True,user=dict(user))

@app.get("/api/stats")
@login_required
def stats():
    uid=session["user_id"]; con=db()
    docs=con.execute("SELECT COUNT(*) c FROM documents WHERE user_id=?", (uid,)).fetchone()["c"]
    total=con.execute("SELECT COALESCE(SUM(total),0) s FROM documents WHERE user_id=?", (uid,)).fetchone()["s"]
    tax=con.execute("SELECT COALESCE(SUM(tax),0) s FROM documents WHERE user_id=?", (uid,)).fetchone()["s"]
    dup=con.execute("SELECT COUNT(*) c FROM documents WHERE user_id=? AND status LIKE '%Duplicate%'", (uid,)).fetchone()["c"]
    cats=con.execute("SELECT category,COALESCE(SUM(total),0) amount FROM documents WHERE user_id=? GROUP BY category ORDER BY amount DESC",(uid,)).fetchall()
    con.close()
    return jsonify(documents=docs,total=round(total,2),tax=round(tax,2),duplicates=dup,categories=[dict(x) for x in cats])

@app.get("/api/documents")
@login_required
def documents():
    q=clean(request.args.get("q","")); uid=session["user_id"]; con=db()
    if q:
        rows=con.execute("""SELECT * FROM documents WHERE user_id=? AND
            (filename LIKE ? OR vendor LIKE ? OR invoice_no LIKE ? OR category LIKE ?)
            ORDER BY id DESC""",(uid,*([f"%{q}%"]*4))).fetchall()
    else:
        rows=con.execute("SELECT * FROM documents WHERE user_id=? ORDER BY id DESC",(uid,)).fetchall()
    con.close(); return jsonify([dict(x) for x in rows])

@app.post("/api/process")
@login_required
def process():
    f=request.files.get("file")
    if not f or not f.filename: return jsonify(error="Please choose an invoice or receipt image."),400
    ext=f.filename.rsplit(".",1)[-1].lower() if "." in f.filename else ""
    if ext not in ALLOWED: return jsonify(error="Supported files: PNG, JPG, JPEG, WEBP, BMP, TIF, TIFF"),400
    raw=f.read(); h=hashlib.sha256(raw).hexdigest(); uid=session["user_id"]; con=db()
    existing=con.execute("SELECT * FROM documents WHERE user_id=? AND file_hash=?",(uid,h)).fetchone()
    if existing:
        con.close(); return jsonify(error="This exact file was already processed.",duplicate=True,document=dict(existing)),409
    safe=re.sub(r"[^A-Za-z0-9._-]","_",f.filename)
    filename=f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{safe}"
    path=UPLOADS/filename; path.write_bytes(raw)
    try: text=ocr_image(path)
    except Exception as e:
        path.unlink(missing_ok=True); con.close()
        return jsonify(error="OCR could not start. Install Tesseract OCR and make sure it is available.",detail=str(e)),500
    data=extract(text)
    possible=con.execute("""SELECT id FROM documents WHERE user_id=? AND
        lower(COALESCE(vendor,''))=lower(?) AND COALESCE(total,0)=? AND COALESCE(doc_date,'')=?""",
        (uid,data["vendor"],data["total"],data["doc_date"])).fetchone()
    status="Needs Review" if data["missing"] else "Processed"
    if possible: status="Possible Duplicate"
    con.execute("""INSERT INTO documents(user_id,filename,vendor,invoice_no,doc_date,address,tax,total,category,raw_text,file_hash,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",(uid,filename,data["vendor"],data["invoice_no"],data["doc_date"],data["address"],data["tax"],data["total"],data["category"],text,h,status,datetime.now().isoformat(timespec="seconds")))
    con.commit(); row=con.execute("SELECT * FROM documents WHERE id=last_insert_rowid()").fetchone(); con.close()
    return jsonify(document=dict(row),missing=data["missing"],raw_text=text)

@app.put("/api/documents/<int:doc_id>")
@login_required
def update_doc(doc_id):
    data=request.get_json(silent=True) or {}; uid=session["user_id"]
    def num(v,label):
        try: return float(str(v or "0").replace(",","").replace("₹","").replace("Rs.","").strip() or 0)
        except ValueError: raise ValueError(f"{label} must be a valid number")
    try:
        tax=num(data.get("tax"),"Tax"); total=num(data.get("total"),"Total")
        vendor=clean(data.get("vendor")); inv=clean(data.get("invoice_no")); date=clean(data.get("doc_date")); address=clean(data.get("address")); category=clean(data.get("category")) or "Other"
        missing=[x for x,v in [("Company/Vendor",vendor),("Invoice Number",inv),("Date",date)] if not v]
        if total<=0: missing.append("Total Amount")
        status="Needs Review" if missing else "Processed"
        con=db(); exists=con.execute("SELECT id FROM documents WHERE id=? AND user_id=?",(doc_id,uid)).fetchone()
        if not exists: con.close(); return jsonify(error="Document not found."),404
        con.execute("""UPDATE documents SET vendor=?,invoice_no=?,doc_date=?,address=?,tax=?,total=?,category=?,status=? WHERE id=? AND user_id=?""",
                    (vendor,inv,date,address,tax,total,category,status,doc_id,uid)); con.commit()
        row=con.execute("SELECT * FROM documents WHERE id=?",(doc_id,)).fetchone(); con.close()
        return jsonify(document=dict(row),missing=missing)
    except ValueError as e: return jsonify(error=str(e)),400
    except Exception as e: return jsonify(error="Could not save corrections.",detail=str(e)),500

@app.delete("/api/documents/<int:doc_id>")
@login_required
def delete_doc(doc_id):
    uid=session["user_id"]; con=db(); row=con.execute("SELECT filename FROM documents WHERE id=? AND user_id=?",(doc_id,uid)).fetchone()
    con.execute("DELETE FROM documents WHERE id=? AND user_id=?",(doc_id,uid)); con.commit(); con.close()
    if row: (UPLOADS/row["filename"]).unlink(missing_ok=True)
    return jsonify(ok=True)

init_db()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
