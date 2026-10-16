# Evaluación

Sirve para no confundir suerte con mejora. Orden: conjunto fijo → A/A → A/B emparejado → juez por pares en los dos órdenes → bootstrap → comparación con el ruido → reservado al final.

## 1. Conjunto de prueba

Guárdalo en `.desatascar/casos.jsonl`, un caso por línea:

```json
{"id": "c01", "entrada": "texto de entrada", "criterios": ["La etiqueta es 'queja'", "No inventa datos"], "reservado": false}
```

- Criterios **binarios** (sí/no) y verificables leyendo solo la salida. "Es de buena calidad" no vale; "menciona el número de pedido" sí.
- Al menos 20 casos en profundo (mejor 30 o más) y al menos 10 en rápido. Incluye casos frontera reales, no solo fáciles.
- Marca un 20-30 % con `"reservado": true`. Esos casos no se miran mientras se itera; solo se usan al final para comprobar que la mejora no es sobreajuste.
- Si los casos son inventados, el usuario los valida antes de medir.

## 2. Test A/A (ruido)

Ejecuta la versión actual contra sí misma al menos 3 veces sobre el mismo conjunto. Las diferencias entre esas ejecuciones son puro azar (temperatura, muestreo del juez).

- **Ruido A/A** = la mayor diferencia media absoluta entre dos ejecuciones de A.
- También se pasa el juez por pares A frente a A: debería salir cerca del 0. Si sale lejos, el juez tiene sesgo.
- Sin este dato no se puede saber si una mejora es real.

## 3. Comparación emparejada

Compara A y B **caso a caso** (diferencia de puntuación en el mismo caso), no medias sueltas. Así se quita la variación entre casos fáciles y difíciles, y con pocos casos se detectan diferencias menores.

- Prompts: conjunto de iteración completo, porque un cambio de prompt puede afectar a cualquier caso.
- Código: los tests de lo que toca el cambio, más la suite completa al final.
- Si el ruido es alto, usa `--repeticiones k` para generar k salidas por caso y promediar.

## 4. Juez por pares en los dos órdenes

- El juez ve la entrada, los criterios y dos salidas, y elige cuál cumple mejor (o empate).
- Se pasa dos veces: (A, B) y (B, A). Solo cuenta como victoria si gana en los dos órdenes; si cambia de opinión al cambiar el orden, es empate (sesgo de posición).
- Además, el juez marca cada criterio binario de cada salida por separado. Esa es la métrica principal; el juez por pares la confirma.
- **Juez barato:** antes de fiarte de haiku como juez, compara su veredicto con el del usuario en 10 casos. Si coincide en 9 o más, úsalo; si no, usa sonnet.

## 5. Bootstrap e informe

- Remuestrea con reemplazo las diferencias por caso 1000 veces; el intervalo del 95 % va del percentil 2,5 al 97,5.
- Veredicto:
  - **Mejora real:** el IC no incluye el 0 **y** la diferencia supera el ruido A/A.
  - **Empeora:** igual, en negativo.
  - **Sin evidencia de mejora:** cualquier otro caso. No digas "mejora pequeña".
- **Efecto mínimo detectable:** el mayor entre el ruido A/A y la semianchura del IC. Si es mayor que la mejora que se busca, faltan casos o repeticiones.

## 6. Conjunto reservado

Al terminar (sobre todo en el bucle iterativo), mide la versión ganadora frente a la base solo en los casos reservados (`--solo-reservado`). Si la mejora desaparece, era sobreajuste: registra el intento como descartado.

## 7. Coste

Precios de la API de Anthropic en USD por millón de tokens (caché del 2026-10-06; compruébalos si ha pasado tiempo):

| Modelo | ID | Entrada | Salida |
|---|---|---|---|
| Fable 5.1 | `claude-fable-5-1` | 10 | 50 |
| Opus 5.5 | `claude-opus-5-5` | 4 | 20 |
| Sonnet 5.5 | `claude-sonnet-5-5` | 2 | 10 |
| Haiku 5.5 | `claude-haiku-5-5` | 0,10 | 0,50 |

- Llamadas por medición profunda con N casos, A/A de 3 ejecuciones y una versión B: generación 4·N; juez de criterios 4·N; juez por pares 2·N (A/B) + 2·N (A/A). En total, unas **12·N** llamadas (360 con 30 casos).
- El script estima el coste en USD con los tokens reales y lo pasa a euros con `--eur-por-usd`.
- Ahorro: caché de prompts (el script la activa en el prompt del sistema), juez haiku si está validado, Batch API (50 % más barato, pero asíncrono: solo para conjuntos grandes sin prisa) y parar en cuanto el resultado sea claro.

## 8. Uso del script

```bash
# Prueba sin gastar
python3 scripts/evaluar.py --dry-run

# Generar con dos prompts y comparar
python3 scripts/evaluar.py --casos .desatascar/casos.jsonl \
  --prompt-a .desatascar/prompt_v1.txt --prompt-b .desatascar/prompt_v2.txt \
  --modelo claude-sonnet-5-5 --juez claude-haiku-5-5 --aa 3 --max-llamadas 400

# Comparar salidas ya generadas (A/A con varios archivos de A)
python3 scripts/evaluar.py --casos .desatascar/casos.jsonl \
  --salidas-a a1.jsonl a2.jsonl a3.jsonl --salidas-b b.jsonl

# Comprobación final en el reservado
python3 scripts/evaluar.py ... --solo-reservado
```

Los archivos de salidas tienen una línea por caso: `{"id": "c01", "salida": "..."}`. Si el prompt contiene `{entrada}`, se sustituye y se envía como mensaje de usuario; si no, el prompt va como system y la entrada como mensaje de usuario.

Requisitos para llamadas reales: `pip install anthropic` (el SDK 1.x pide Python 3.10 o superior) y `ANTHROPIC_API_KEY` en el entorno.
