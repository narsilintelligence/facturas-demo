"""Banco de pruebas: pasa las facturas de banco.txt por uno o dos modelos y compara con verdad.csv.
Cuatro números por modelo: acierto por campo, invención, coste en tokens por caso y segundos por caso.
Uso: python banco.py [--modelos qwen3.6:35b-a3b,qwen3.8:27b]"""
import argparse, datetime as dt
from comun import RAIZ, MODELO_POR_DEFECTO, leer_csv, importes_en
from extraer import extraer_factura, CAMPOS

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
NUMERICOS = ("base", "tipo_iva", "iva", "total")


def acierta(campo, dado, real):
    if dado is None:
        return False
    if campo == "proveedor":
        return str(dado).strip().casefold() == real.strip().casefold()
    if campo in ("fecha", "vencimiento"):
        return dado == real
    return abs(float(dado) - float(real)) < 0.005


def esta_en_texto(campo, dado, texto):
    """¿El valor que dio el modelo aparece de verdad en la factura? (si no, es una invención)"""
    t = texto.casefold()
    if campo == "proveedor":
        return str(dado).casefold() in t
    if campo in ("fecha", "vencimiento"):
        try:
            d = dt.date.fromisoformat(dado)
        except (ValueError, TypeError):
            return False
        formas = [d.isoformat(), d.strftime("%d/%m/%Y"), d.strftime("%d-%m-%Y"), f"{d.day} de {MESES[d.month - 1]} de {d.year}"]
        return any(f in t for f in formas)
    if campo == "tipo_iva":
        n = int(dado) if float(dado) == int(dado) else dado
        return f"{n} %" in t or f"{n}%" in t
    return any(abs(x - float(dado)) <= 0.005 for x in importes_en(texto))


def evaluar(modelo, ids, verdad):
    aciertos = {c: 0 for c in CAMPOS}
    inventados = tokens = 0
    segundos = 0.0
    fallos = []
    for n, i in enumerate(ids, 1):
        campos, ti, to, seg, esc, texto = extraer_factura(modelo, RAIZ / "facturas" / f"{i}.pdf")
        campos = campos or {}
        tokens += ti + to
        segundos += seg
        malos = []
        for c in CAMPOS:
            dado = campos.get(c)
            inventado = dado is not None and not esta_en_texto(c, dado, texto)
            inventados += inventado
            if dado is None or not acierta(c, dado, verdad[i][c]):
                malos.append(f"{c}: dio {dado!r}, verdad {verdad[i][c]!r}" + ("  [INVENTADO: no está en la factura]" if inventado else ""))
            else:
                aciertos[c] += 1
        print(f"  [{n:>2}/{len(ids)}] {i}{' (escaneada)' if esc else ''}{' (IVA erróneo)' if verdad[i]['iva_erroneo'] == '1' else ''}: "
              f"{'todo bien' if not malos else str(len(malos)) + ' fallo(s)'}  ({ti + to} tokens, {seg:.1f} s)")
        for m in malos:
            print(f"        - {m}")
        fallos += malos
    n = len(ids)
    return {"modelo": modelo, "acierto": {c: 100 * aciertos[c] / n for c in CAMPOS}, "inventados": inventados,
            "campos_total": n * len(CAMPOS), "tokens_caso": tokens / n, "seg_caso": segundos / n}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelos", default=MODELO_POR_DEFECTO, help="uno o dos modelos separados por comas")
    a = ap.parse_args()
    ids = [l.strip() for l in (RAIZ / "banco.txt").read_text().split() if l.strip()]
    verdad = {f["id"]: f for f in leer_csv(RAIZ / "verdad.csv")}
    resultados = []
    for m in a.modelos.split(","):
        print(f"\n== Modelo {m}: {len(ids)} facturas ==")
        resultados.append(evaluar(m, ids, verdad))

    print("\n" + "=" * 78 + f"\nBANCO DE PRUEBAS · {len(ids)} facturas · {len(CAMPOS)} campos cada una\n" + "=" * 78)
    print("1) Acierto por campo (%)")
    print(f"{'modelo':<20}" + "".join(f"{c:>12}" for c in CAMPOS) + f"{'GLOBAL':>9}")
    for r in resultados:
        print(f"{r['modelo']:<20}" + "".join(f"{r['acierto'][c]:>12.0f}" for c in CAMPOS) + f"{sum(r['acierto'].values()) / len(CAMPOS):>9.1f}")
    print("\n2) Invención (campos con un valor que NO está en la factura; dejarlo vacío no cuenta)")
    print("3) Coste: tokens (entrada + salida) por caso   |   4) Tiempo: segundos por caso")
    print(f"{'modelo':<20}{'invención':>22}{'tokens/caso':>14}{'seg/caso':>11}")
    for r in resultados:
        print(f"{r['modelo']:<20}{str(r['inventados']) + ' de ' + str(r['campos_total']):>22}{r['tokens_caso']:>14.0f}{r['seg_caso']:>11.1f}")


if __name__ == "__main__":
    main()
