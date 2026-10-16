#!/usr/bin/env python3
"""Comparación A/B de prompts con medición fiable.

Hace: test A/A (ruido), comparación emparejada caso a caso con criterios
binarios, juez por pares en los dos órdenes, bootstrap (IC 95 %) e informe
frente al ruido A/A. Con --dry-run usa datos simulados y no llama a la API.

Ejemplos:
  python3 evaluar.py --dry-run
  python3 evaluar.py --casos casos.jsonl --prompt-a v1.txt --prompt-b v2.txt
  python3 evaluar.py --casos casos.jsonl --salidas-a a1.jsonl a2.jsonl a3.jsonl --salidas-b b.jsonl

Requisitos para llamadas reales: `pip install anthropic` y ANTHROPIC_API_KEY.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

# USD por millón de tokens (entrada, salida). Caché del 2026-10-06.
PRECIOS = {
    "claude-fable-5-1": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}

INSTR_CRITERIOS = (
    "Eres un evaluador estricto. Recibes una entrada, la salida de un sistema y una lista "
    "numerada de criterios binarios. Decide para cada criterio si la salida lo cumple (true) "
    "o no (false), leyendo solo la salida y la entrada. Ante la duda, false. "
    'Responde solo con JSON: {"cumple": [true, false, ...]} con un valor por criterio, en orden.'
)

INSTR_PARES = (
    "Eres un evaluador estricto. Recibes una entrada, unos criterios y dos salidas (1 y 2). "
    "Decide cuál cumple mejor los criterios. Ignora la longitud y el estilo si no afectan a "
    "los criterios. Si son equivalentes, di empate. "
    'Responde solo con JSON: {"mejor": "1"} o {"mejor": "2"} o {"mejor": "empate"}.'
)


class LimiteAlcanzado(Exception):
    pass


class Contador:
    def __init__(self, maximo):
        self.maximo = maximo
        self.llamadas = 0
        self.tokens = {}  # modelo -> [entrada, salida, cache_lectura, cache_escritura]
        self.fallos_parseo = 0
        self._lock = threading.Lock()

    def reservar(self):
        with self._lock:
            if self.maximo is not None and self.llamadas >= self.maximo:
                raise LimiteAlcanzado()
            self.llamadas += 1

    def sumar(self, modelo, usage):
        with self._lock:
            t = self.tokens.setdefault(modelo, [0, 0, 0, 0])
            t[0] += getattr(usage, "input_tokens", 0) or 0
            t[1] += getattr(usage, "output_tokens", 0) or 0
            t[2] += getattr(usage, "cache_read_input_tokens", 0) or 0
            t[3] += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def coste_usd(self):
        total = 0.0
        for modelo, (ent, sal, cl, ce) in self.tokens.items():
            pe, ps = PRECIOS.get(modelo, (0.0, 0.0))
            total += (ent * pe + cl * pe * 0.1 + ce * pe * 1.25 + sal * ps) / 1e6
        return total


def extraer_json(texto):
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError("sin JSON")
    return json.loads(m.group(0))


# ---------------------------------------------------------------- backends

class BackendReal:
    def __init__(self, args, contador):
        try:
            import anthropic
        except ImportError:
            sys.exit("Falta el SDK: pip install anthropic (o usa --dry-run).")
        if not os.environ.get("ANTHROPIC_API_KEY"):
            sys.exit("Falta ANTHROPIC_API_KEY en el entorno. No la escribas en el código.")
        self.cliente = anthropic.Anthropic()  # lee ANTHROPIC_API_KEY
        self.args = args
        self.contador = contador

    def _llamar(self, modelo, system, usuario, max_tokens, esfuerzo=None):
        self.contador.reservar()
        kwargs = dict(model=modelo, max_tokens=max_tokens,
                      messages=[{"role": "user", "content": usuario}])
        if system:
            # El system va primero y estable para aprovechar la caché de prompts.
            kwargs["system"] = [{"type": "text", "text": system,
                                 "cache_control": {"type": "ephemeral"}}]
        if esfuerzo:
            kwargs["output_config"] = {"effort": esfuerzo}
        resp = self.cliente.messages.create(**kwargs)
        self.contador.sumar(modelo, resp.usage)
        return "".join(b.text for b in resp.content if b.type == "text")

    def generar(self, prompt, caso, version, rep):
        if "{entrada}" in prompt:
            return self._llamar(self.args.modelo, None, prompt.replace("{entrada}", caso["entrada"]),
                                self.args.max_tokens)
        return self._llamar(self.args.modelo, prompt, caso["entrada"], self.args.max_tokens)

    def _juez(self, instr, usuario):
        for intento in range(2):
            texto = self._llamar(self.args.juez, instr, usuario, 2000, esfuerzo="low")
            try:
                return extraer_json(texto)
            except (ValueError, json.JSONDecodeError):
                continue
        self.contador.fallos_parseo += 1
        return None

    def juez_criterios(self, caso, salida):
        crit = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(caso["criterios"]))
        r = self._juez(INSTR_CRITERIOS,
                       f"<entrada>\n{caso['entrada']}\n</entrada>\n<salida>\n{salida}\n</salida>\n"
                       f"<criterios>\n{crit}\n</criterios>")
        valores = (r or {}).get("cumple", [])
        if len(valores) != len(caso["criterios"]):
            return [False] * len(caso["criterios"])
        return [bool(v) for v in valores]

    def juez_pares(self, caso, s1, s2):
        crit = "\n".join(f"- {c}" for c in caso["criterios"])
        r = self._juez(INSTR_PARES,
                       f"<entrada>\n{caso['entrada']}\n</entrada>\n<criterios>\n{crit}\n</criterios>\n"
                       f"<salida_1>\n{s1}\n</salida_1>\n<salida_2>\n{s2}\n</salida_2>")
        return str((r or {}).get("mejor", "empate"))


class BackendSimulado:
    """Datos de juguete: B es algo mejor que A y el juez tiene sesgo de posición."""

    def __init__(self, args, contador, ventaja_b):
        self.contador = contador
        self.ventaja_b = ventaja_b

    @staticmethod
    def _rng(*partes):
        h = hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()
        return random.Random(int(h[:16], 16))

    def _calidad(self, salida):
        _, version, cid = salida.split("|")[:3]
        base = 0.55 + self._rng("dif", cid).uniform(-0.25, 0.25)
        if version == "B":
            base += self.ventaja_b
        return min(0.95, max(0.05, base + self._rng("ruido", salida).gauss(0, 0.08)))

    def generar(self, prompt, caso, version, rep):
        self.contador.reservar()
        self.contador.sumar("claude-sonnet-5-5", _UsoFalso(400, 150))
        return f"SIM|{version}|{caso['id']}|{rep}|{prompt}"

    def juez_criterios(self, caso, salida):
        self.contador.reservar()
        self.contador.sumar("claude-haiku-5-5", _UsoFalso(500, 30))
        q = self._calidad(salida)
        rng = self._rng("crit", salida)
        return [rng.random() < q for _ in caso["criterios"]]

    def juez_pares(self, caso, s1, s2):
        self.contador.reservar()
        self.contador.sumar("claude-haiku-5-5", _UsoFalso(900, 15))
        d = self._calidad(s1) - self._calidad(s2) + 0.06  # sesgo hacia la primera
        d += self._rng("par", s1, s2).gauss(0, 0.05)
        return "empate" if abs(d) < 0.04 else ("1" if d > 0 else "2")


class _UsoFalso:
    def __init__(self, ent, sal):
        self.input_tokens, self.output_tokens = ent, sal
        self.cache_read_input_tokens = self.cache_creation_input_tokens = 0


# ---------------------------------------------------------------- datos

def leer_jsonl(ruta):
    with open(ruta, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def casos_simulados(n=30):
    rng = random.Random(7)
    casos = []
    for i in range(n):
        casos.append({"id": f"c{i + 1:02d}", "entrada": f"mensaje de cliente {i + 1}",
                      "criterios": ["Etiqueta correcta", "Formato JSON válido", "No inventa datos"],
                      "reservado": rng.random() < 0.2})
    return casos


def cargar_salidas(rutas):
    """Cada archivo es una ejecución: id -> lista de salidas (varias líneas = repeticiones)."""
    ejecuciones = []
    for ruta in rutas:
        ej = {}
        for fila in leer_jsonl(ruta):
            ej.setdefault(fila["id"], []).append(fila["salida"])
        ejecuciones.append(ej)
    return ejecuciones


def generar_ejecucion(backend, prompt, casos, version, run, k, paralelo):
    tareas = [(c, r) for c in casos for r in range(k)]
    with ThreadPoolExecutor(paralelo) as ex:
        res = list(ex.map(lambda t: backend.generar(prompt, t[0], version, f"{t[1]}|{run}"), tareas))
    ej = {}
    for (c, _), s in zip(tareas, res):
        ej.setdefault(c["id"], []).append(s)
    return ej


def puntuar(backend, casos, ejecucion, paralelo):
    """Puntuación por caso = fracción media de criterios cumplidos en sus repeticiones."""
    tareas = [(c, s) for c in casos for s in ejecucion.get(c["id"], [])]
    with ThreadPoolExecutor(paralelo) as ex:
        res = list(ex.map(lambda t: backend.juez_criterios(*t), tareas))
    acum = {}
    for (c, _), v in zip(tareas, res):
        acum.setdefault(c["id"], []).append(sum(v) / len(v))
    return {cid: sum(x) / len(x) for cid, x in acum.items()}


def pares_dos_ordenes(backend, casos, ej1, ej2, paralelo):
    """+1 si gana la segunda versión en los dos órdenes, -1 si gana la primera, 0 si no."""
    def uno(c):
        a, b = ej1[c["id"]][0], ej2[c["id"]][0]
        r1 = backend.juez_pares(c, a, b)  # a en posición 1
        r2 = backend.juez_pares(c, b, a)  # b en posición 1
        if r1 == "2" and r2 == "1":
            return 1
        if r1 == "1" and r2 == "2":
            return -1
        return 0
    validos = [c for c in casos if c["id"] in ej1 and c["id"] in ej2]
    with ThreadPoolExecutor(paralelo) as ex:
        return list(ex.map(uno, validos))


# ---------------------------------------------------------------- estadística

def media(x):
    return sum(x) / len(x) if x else 0.0


def bootstrap(x, n=1000, semilla=1):
    rng = random.Random(semilla)
    medias = sorted(media([rng.choice(x) for _ in x]) for _ in range(n))
    return medias[int(0.025 * n)], medias[int(0.975 * n) - 1]


def veredicto(dif, ic, ruido):
    if ruido is None:
        return "sin A/A: no se puede afirmar nada (usa --aa 3 o más)"
    if ic[0] > 0 and dif > ruido:
        return "MEJORA REAL (el IC excluye el 0 y supera el ruido A/A)"
    if ic[1] < 0 and -dif > ruido:
        return "EMPEORA (el IC excluye el 0 y supera el ruido A/A)"
    return "SIN EVIDENCIA DE MEJORA (no supera el ruido o el IC incluye el 0)"


# ---------------------------------------------------------------- principal

def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--casos", help="JSONL con id, entrada, criterios y reservado")
    p.add_argument("--prompt-a", help="prompt actual (archivo de texto)")
    p.add_argument("--prompt-b", help="prompt nuevo (archivo de texto)")
    p.add_argument("--salidas-a", nargs="+", help="salidas ya generadas de A; varios archivos = A/A")
    p.add_argument("--salidas-b", nargs="+", help="salidas ya generadas de B")
    p.add_argument("--modelo", default="claude-sonnet-5-5", help="modelo generador")
    p.add_argument("--juez", default="claude-haiku-5-5", help="modelo juez (valida haiku antes)")
    p.add_argument("--aa", type=int, default=3, help="ejecuciones de A para el test A/A")
    p.add_argument("--repeticiones", type=int, default=1, help="salidas por caso y versión")
    p.add_argument("--ids", nargs="+", help="evaluar solo estos casos")
    p.add_argument("--solo-reservado", action="store_true", help="usar solo el conjunto reservado")
    p.add_argument("--incluir-reservado", action="store_true", help="no apartar el reservado (no recomendado)")
    p.add_argument("--max-llamadas", type=int, help="límite duro de llamadas a la API")
    p.add_argument("--max-tokens", type=int, default=4000)
    p.add_argument("--paralelo", type=int, default=4)
    p.add_argument("--eur-por-usd", type=float, help="tipo de cambio para dar el coste en euros")
    p.add_argument("--json", help="guardar el resultado en este archivo")
    p.add_argument("--dry-run", action="store_true", help="datos simulados, sin llamadas")
    p.add_argument("--ventaja-simulada", type=float, default=0.08, help="solo --dry-run")
    a = p.parse_args()

    contador = Contador(a.max_llamadas)
    if a.dry_run:
        casos = casos_simulados()
        backend = BackendSimulado(a, contador, a.ventaja_simulada)
        prompt_a, prompt_b = "A", "B"
    else:
        if not a.casos or not ((a.prompt_a and a.prompt_b) or (a.salidas_a and a.salidas_b)):
            p.error("necesitas --casos y (--prompt-a y --prompt-b) o (--salidas-a y --salidas-b)")
        casos = leer_jsonl(a.casos)
        backend = BackendReal(a, contador)
        prompt_a = open(a.prompt_a, encoding="utf-8").read() if a.prompt_a else None
        prompt_b = open(a.prompt_b, encoding="utf-8").read() if a.prompt_b else None

    if a.solo_reservado:
        casos = [c for c in casos if c.get("reservado")]
        conjunto = "reservado"
    elif not a.incluir_reservado:
        casos = [c for c in casos if not c.get("reservado")]
        conjunto = "iteración (sin reservado)"
    else:
        conjunto = "completo"
    if a.ids:
        casos = [c for c in casos if c["id"] in set(a.ids)]
    n, k = len(casos), a.repeticiones
    if n < 10:
        print(f"Aviso: solo {n} casos. El resultado será muy ruidoso.")

    generar = a.dry_run or prompt_a is not None
    runs_a = a.aa if generar else len(a.salidas_a)
    estimadas = (runs_a + 1) * n * k * (2 if generar else 1) + 2 * n + (2 * n if runs_a >= 2 else 0)
    print(f"Conjunto: {conjunto} · {n} casos · {runs_a} ejecuciones de A · {k} rep/caso")
    print(f"Llamadas estimadas: {estimadas}")
    if a.max_llamadas is not None and estimadas > a.max_llamadas:
        sys.exit(f"Supera --max-llamadas={a.max_llamadas}. Reduce casos, --aa o --repeticiones.")

    try:
        if generar:
            ejs_a = [generar_ejecucion(backend, prompt_a, casos, "A", i, k, a.paralelo) for i in range(runs_a)]
            ej_b = generar_ejecucion(backend, prompt_b, casos, "B", 0, k, a.paralelo)
        else:
            ejs_a, ej_b = cargar_salidas(a.salidas_a), cargar_salidas(a.salidas_b)[0]
        punt_a = [puntuar(backend, casos, ej, a.paralelo) for ej in ejs_a]
        punt_b = puntuar(backend, casos, ej_b, a.paralelo)
        pref_ab = pares_dos_ordenes(backend, casos, ejs_a[0], ej_b, a.paralelo)
        pref_aa = pares_dos_ordenes(backend, casos, ejs_a[0], ejs_a[1], a.paralelo) if runs_a >= 2 else []
    except LimiteAlcanzado:
        sys.exit(f"Límite de {a.max_llamadas} llamadas alcanzado. Coste hasta ahora: {contador.coste_usd():.4f} USD")

    ids = [c["id"] for c in casos if c["id"] in punt_b and all(c["id"] in pa for pa in punt_a)]
    base = {i: media([pa[i] for pa in punt_a]) for i in ids}
    difs = [punt_b[i] - base[i] for i in ids]
    dif, ic = media(difs), bootstrap(difs)

    ruidos = [abs(media([pa[i] - pb[i] for i in ids])) for pa, pb in itertools.combinations(punt_a, 2)]
    ruido = max(ruidos) if ruidos else None
    mde = max(ruido or 0.0, (ic[1] - ic[0]) / 2)

    print("\n== Criterios binarios (métrica principal) ==")
    for j, pa in enumerate(punt_a):
        print(f"A ejecución {j + 1}: {media([pa[i] for i in ids]):.3f}")
    print(f"A (media de ejecuciones): {media(list(base.values())):.3f}")
    print(f"B: {media([punt_b[i] for i in ids]):.3f}")
    print(f"Diferencia emparejada B−A: {dif:+.3f}  IC95% bootstrap [{ic[0]:+.3f}, {ic[1]:+.3f}]  (n={len(ids)})")
    print(f"Ruido A/A (máx. |dif| entre ejecuciones de A): {'—' if ruido is None else f'{ruido:.3f}'}")
    print(f"Efecto mínimo detectable aprox.: {mde:.3f}")
    print(f"Casos donde B gana / pierde / empata: {sum(d > 0 for d in difs)} / {sum(d < 0 for d in difs)} / {sum(d == 0 for d in difs)}")

    print("\n== Juez por pares, dos órdenes ==")
    ic_p = bootstrap(pref_ab, semilla=2) if pref_ab else (0, 0)
    print(f"B gana {pref_ab.count(1)} · A gana {pref_ab.count(-1)} · empate/inconsistente {pref_ab.count(0)}"
          f"  → preferencia media {media(pref_ab):+.3f} IC95% [{ic_p[0]:+.3f}, {ic_p[1]:+.3f}]")
    if pref_aa:
        print(f"A/A por pares: preferencia media {media(pref_aa):+.3f} (cerca de 0 = juez sin sesgo)")

    v = veredicto(dif, ic, ruido)
    print(f"\n== Veredicto: {v} ==")
    if "SIN EVIDENCIA" in v and mde > abs(dif):
        print("Con este ruido no se distinguen efectos menores que el MDE: añade casos o --repeticiones.")

    coste = contador.coste_usd()
    eur = f" ≈ {coste * a.eur_por_usd:.4f} EUR" if a.eur_por_usd else ""
    print(f"\nLlamadas: {contador.llamadas} · coste {'simulado ' if a.dry_run else ''}{coste:.4f} USD{eur}"
          + (f" · fallos de parseo del juez: {contador.fallos_parseo}" if contador.fallos_parseo else ""))

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"conjunto": conjunto, "n": len(ids), "diferencia": dif, "ic95": ic,
                       "ruido_aa": ruido, "mde": mde, "veredicto": v,
                       "pares": {"b_gana": pref_ab.count(1), "a_gana": pref_ab.count(-1),
                                 "empate": pref_ab.count(0)},
                       "llamadas": contador.llamadas, "coste_usd": coste}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
