"""Piezas comunes a todos los scripts: hablar con Ollama, leer el texto de una factura, leer la verdad."""
import base64, copy, csv, json, os, re, subprocess, sys, tempfile, time
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


class ErrorDeEntorno(Exception):
    """Falta algo para poder trabajar (Ollama apagado, un modelo sin descargar, pdftotext): se para con un mensaje claro."""


class FalloDelModelo(Exception):
    """El modelo no ha podido responder a ESTA petición ni con los reintentos. Las demás facturas pueden seguir."""


SIN_OLLAMA = (f"no hay respuesta de Ollama en {OLLAMA}. Comprueba que está en marcha (abre la aplicación o ejecuta "
              "«ollama serve») o, si está en otra dirección, indícala con la variable OLLAMA_HOST.")

# Si Ollama devuelve un error 500 (el modelo se ha caído en el servidor), la petición se repite cambiando su FORMA,
# no lo que se pide: el tamaño de lote con el que Ollama procesa el texto y, si hace falta, unos tokens más al final.
# Es lo que esquiva el fallo conocido de Ollama «CUDA error: an illegal memory access» (README, «Si algo falla»):
# depende del tamaño exacto del texto que el modelo procesa de una vez, así que con otro lote u otra longitud no aparece.
REINTENTOS = [
    {"lote": 512, "relleno": ""},
    {"lote": 512, "relleno": "\n\n[reintento]"},
    {"lote": 128, "relleno": "\n\n[reintento con otra variante]"},
]
_lote_que_funciona = {}   # modelo -> tamaño de lote que salvó un reintento; se mantiene hasta el final de la ejecución


def _motivo(r):
    """El error que devuelve Ollama, en una línea (p. ej. «CUDA error: an illegal memory access was encountered»)."""
    try:
        texto = r.json().get("error") or r.text
    except ValueError:
        texto = r.text
    lineas = [l.strip() for l in str(texto).splitlines() if l.strip()]
    return lineas[-1][:160] if lineas else f"HTTP {r.status_code}"


def _variante(cuerpo, v):
    """Copia de la petición con el tamaño de lote y el relleno de la variante v (None = la petición tal cual)."""
    c = copy.deepcopy(cuerpo)
    lote = v["lote"] if v else _lote_que_funciona.get(c["model"])
    if lote:
        c["options"] = {**c.get("options", {}), "num_batch": lote}
    if v and v["relleno"]:
        c["messages"][-1]["content"] = (c["messages"][-1].get("content") or "") + v["relleno"]
    return c


def _post(ruta, cuerpo, variar=False):
    """POST a Ollama. Si el modelo se cae (error 500), reintenta: con variar=True, con las variantes de REINTENTOS;
    si no, repitiendo la misma petición. Si nada funciona, FalloDelModelo; si Ollama no está o falta el modelo, ErrorDeEntorno."""
    modelo = cuerpo["model"]
    planes = [None] + (REINTENTOS if variar else [None] * len(REINTENTOS))
    for n, v in enumerate(planes):
        try:
            r = requests.post(f"{OLLAMA}{ruta}", json=_variante(cuerpo, v) if variar else cuerpo, timeout=900)
        except requests.ConnectionError:
            raise ErrorDeEntorno(SIN_OLLAMA) from None
        except requests.Timeout:
            motivo = "Ollama no respondió en 15 minutos"
        except requests.RequestException as e:
            motivo = f"respuesta incompleta de Ollama ({type(e).__name__})"
        else:
            if r.ok:
                if v and _lote_que_funciona.get(modelo) != v["lote"]:
                    _lote_que_funciona[modelo] = v["lote"]
                    print(f"   (funciona: sigo con lote de {v['lote']} para el resto de peticiones a {modelo})")
                return r.json()
            motivo = _motivo(r)
            if r.status_code == 404:
                raise ErrorDeEntorno(f"Ollama no tiene el modelo {modelo}. Descárgalo con:  ollama pull {modelo}")
            if r.status_code < 500:
                raise ErrorDeEntorno(f"Ollama ha rechazado la petición a {modelo}: {motivo}")
        if n + 1 < len(planes):
            s = planes[n + 1]
            como = f"lote de {s['lote']}" + (" y texto algo más largo" if s["relleno"] else "") if s else "la misma petición"
            print(f"   (Ollama ha fallado: {motivo}. Reintento {n + 1} de {len(planes) - 1}, con {como})")
            time.sleep(2)
    raise FalloDelModelo(f"{modelo} no ha respondido tras {len(planes)} intentos (último error de Ollama: {motivo})")


def comprobar_ollama(*modelos):
    """Antes de empezar: ¿responde Ollama y tiene los modelos? Si no, para con un mensaje que dice qué hacer."""
    try:
        r = requests.get(f"{OLLAMA}/api/tags", timeout=15)
        r.raise_for_status()
        hay = {m.get("name") for m in r.json().get("models", [])}
    except (requests.RequestException, ValueError):
        raise ErrorDeEntorno(SIN_OLLAMA) from None
    faltan = [m for m in dict.fromkeys(modelos) if m not in hay and f"{m}:latest" not in hay]
    if faltan:
        raise ErrorDeEntorno("a Ollama le faltan modelos. Descárgalos con:\n" + "\n".join(f"  ollama pull {m}" for m in faltan))


def ejecutar(main):
    """Lanza main(); si falta algo o el modelo no responde, lo explica en una frase en vez de enseñar una traza de Python."""
    try:
        main()
    except ErrorDeEntorno as e:
        sys.exit(f"\nNo se puede continuar: {e}")
    except FalloDelModelo as e:
        sys.exit(f"\nNo se puede continuar: {e}.\nVuelve a intentarlo; si se repite, mira «Si algo falla» en el README.")
    except KeyboardInterrupt:
        sys.exit("\nInterrumpido.")


def chat(modelo, mensajes, formato=None, herramientas=None):
    """Una llamada a /api/chat con temperatura 0 y el razonamiento apagado (más rápido y repetible)."""
    cuerpo = {"model": modelo, "messages": mensajes, "stream": False, "think": False,
              "options": {"temperature": 0}}
    if formato:
        cuerpo["format"] = formato
    if herramientas:
        cuerpo["tools"] = herramientas
    d = _post("/api/chat", cuerpo, variar=True)
    return d["message"], d.get("prompt_eval_count", 0), d.get("eval_count", 0)


def embeddings(textos):
    return _post("/api/embed", {"model": MODELO_EMBEDDINGS, "input": textos})["embeddings"]


def _programa(orden, **kw):
    """Lanza una herramienta de poppler (pdftotext, pdftoppm); si no está instalada, lo dice claro."""
    try:
        return subprocess.run(orden, capture_output=True, text=True, **kw)
    except FileNotFoundError:
        raise ErrorDeEntorno(f"falta {orden[0]}, del paquete poppler (en Debian/Ubuntu: sudo apt install poppler-utils; "
                             "en macOS: brew install poppler).") from None


def texto_pdf(ruta):
    return _programa(["pdftotext", "-layout", str(ruta), "-"]).stdout


def ocr_pdf(ruta):
    """Factura escaneada: la página es una imagen, así que se la leemos con glm-ocr. Devuelve (texto, tokens_in, tokens_out)."""
    with tempfile.TemporaryDirectory() as tmp:
        _programa(["pdftoppm", "-r", "150", "-png", "-f", "1", "-l", "1", str(ruta), f"{tmp}/p"], check=True)
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
