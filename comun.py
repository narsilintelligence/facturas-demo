"""Piezas comunes a todos los scripts: hablar con Ollama, leer el texto de una factura, leer la verdad."""
import base64, csv, json, os, re, subprocess, tempfile, time
from pathlib import Path
import requests

RAIZ = Path(__file__).parent
# Configurables por variables de entorno; sin ellas, estos son los valores con los que se grabó el vídeo.
OLLAMA = (os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
if "://" not in OLLAMA:   # Ollama admite OLLAMA_HOST sin esquema (127.0.0.1:11434); aquí hace falta la URL completa
    OLLAMA = "http://" + OLLAMA
MODELO_POR_DEFECTO = os.environ.get("FACTURAS_MODELO", "qwen3.6:35b-a3b")
MODELO_OCR = os.environ.get("FACTURAS_MODELO_OCR", "glm-ocr:latest")
MODELO_EMBEDDINGS = os.environ.get("FACTURAS_MODELO_EMBEDDINGS", "qwen3-embedding:4b")


def _post(ruta, cuerpo, intentos=4):
    """POST a Ollama con reintentos: el servidor local da algún error 500 suelto (CUDA) que se cura repitiendo."""
    for i in range(intentos):
        r = requests.post(f"{OLLAMA}{ruta}", json=cuerpo, timeout=900)
        if r.status_code < 500 or i == intentos - 1:
            r.raise_for_status()
            return r.json()
        print(f"   (Ollama devolvió {r.status_code}, reintento {i + 1})")
        # En algunas GPU, Ollama 0.33.x falla con ciertas longitudes exactas de entrada («CUDA illegal memory access»)
        # y falla siempre igual. Un salto de línea más al final cambia la longitud y no el contenido.
        if "illegal memory access" in r.text and cuerpo.get("messages"):
            cuerpo["messages"][-1] = dict(cuerpo["messages"][-1], content=cuerpo["messages"][-1]["content"] + "\n")
        time.sleep(3)


def chat(modelo, mensajes, formato=None, herramientas=None):
    """Una llamada a /api/chat con temperatura 0 y el razonamiento apagado (más rápido y repetible)."""
    cuerpo = {"model": modelo, "messages": mensajes, "stream": False, "think": False,
              "options": {"temperature": 0}}
    if formato:
        cuerpo["format"] = formato
    if herramientas:
        cuerpo["tools"] = herramientas
    d = _post("/api/chat", cuerpo)
    return d["message"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)


def embeddings(textos):
    return _post("/api/embed", {"model": MODELO_EMBEDDINGS, "input": textos})["embeddings"]


def texto_pdf(ruta):
    return subprocess.run(["pdftotext", "-layout", str(ruta), "-"], capture_output=True, text=True).stdout


def ocr_pdf(ruta):
    """Factura escaneada: la página es una imagen, así que se la leemos con glm-ocr. Devuelve (texto, tokens_in, tokens_out)."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "150", "-png", "-f", "1", "-l", "1", str(ruta), f"{tmp}/p"], check=True)
        png = sorted(Path(tmp).glob("p*.png"))[0]
        imagen = base64.b64encode(png.read_bytes()).decode()
    d = _post("/api/generate", {"model": MODELO_OCR, "prompt": "Text Recognition:", "images": [imagen],
                                "stream": False, "options": {"temperature": 0}})
    return d["response"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)


def leer_texto(ruta):
    """Devuelve (texto, tokens_in, tokens_out, usó_ocr). Si pdftotext no saca nada, es un escaneado: OCR."""
    t = texto_pdf(ruta)
    if len(t.strip()) >= 20:
        return t, 0, 0, False
    t, ti, to = ocr_pdf(ruta)
    return t, ti, to, True


def texto_cacheado(ruta):
    """Para preguntar/agente: usa el texto que dejó extraer.py si existe; si no, lo lee ahora."""
    c = RAIZ / "salida" / "texto" / (Path(ruta).stem + ".txt")
    if c.exists():
        return c.read_text()
    return leer_texto(ruta)[0]


def importes_en(texto):
    """Todos los importes con formato español (1.234,56) que aparecen en un texto, como números."""
    return [float(m.replace(".", "").replace(",", ".")) for m in re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}", texto)]


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
