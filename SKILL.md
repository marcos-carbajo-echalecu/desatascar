---
name: desatascar
description: Saca un problema atascado (prompt o código que no mejora tras varios intentos) del marco mental en el que se ha quedado. Genera ideas divergentes con subagentes de contexto limpio y otro modelo, registra los intentos para no repetirlos y obliga a medir cada idea frente al ruido. Úsala solo cuando el usuario la invoque con /desatascar.
disable-model-invocation: true
argument-hint: "[profundo|iterativo] [descripción opcional del problema]"
---

# Desatascar

Argumentos recibidos: `$ARGUMENTS`

El bloqueo rara vez es falta de esfuerzo: es que la sesión sigue dentro del mismo marco mental. Esta skill sirve para dos cosas: romper ese marco y no confundir suerte con mejora. Si una idea no se puede medir, no ayuda a salir del bloqueo.

Responde siempre en español, conciso y directo.

## 0. Modo y arranque

Lee solo la **primera palabra** de los argumentos:

| Primera palabra | Modo | Fases |
|---|---|---|
| `profundo` | profundo | 1 → 2 → 3 → 4 → 5 (medición completa) |
| `iterativo` | iterativo | igual que profundo + bucle iterativo |
| vacío u otra | rápido | 1 → 3 → 5 (medición ligera), 3 alternativas |

El texto restante (o todo, si la primera palabra no es un modo) es una descripción adicional del problema.

**Registro de intentos.** Lee `.desatascar/intentos.md` en la raíz del proyecto. Si no existe, créalo con un título `# Intentos`. Si el proyecto usa git y `.desatascar/` no está en `.gitignore`, sugiere añadirlo una sola vez, salvo que el usuario quiera versionarlo. Plantilla de cada entrada:

```
## [AAAA-MM-DD] Intento N – título corto
- Tipo de bloqueo: prompt | lógica de código | rendimiento | librería/API | diseño
- Enfoque de origen: (p. ej. Munger, primeros principios, few-shot…)
- Mecanismo: qué cambia en una frase (sirve para detectar repeticiones)
- Qué se cambió:
- Resultado: (con números si los hay: diferencia, IC, ruido A/A)
- Motivo del fallo o del descarte:
- Estado: probado | descartado | aceptado
```

Antes de proponer algo, compáralo por **mecanismo**, no por redacción, con lo registrado. Una variación mínima (mismo mecanismo con otros parámetros o redactado de otra forma) cuenta como repetición. Si una idea se parece a una registrada, di en una línea en qué se diferencia de verdad.

## Fase 1 – Diagnóstico

1. Resume qué se ha probado (conversación + intentos.md), por qué falló cada intento y qué **supuestos** se están dando por buenos sin comprobarlos. Esta lista de supuestos es lo más valioso de la fase.
2. Explica el problema como a un niño de colegio, con una analogía sencilla (p. ej. el modelo es un alumno con un examen de instrucciones confusas: ¿le falta información, le sobra, no sabe qué nota se espera?). Sirve para que salga a la luz lo obvio que se ha pasado por alto.
3. Clasifica el bloqueo: prompt, lógica de código, rendimiento, librería/API o diseño.
4. Si falta información crítica que solo puede dar el usuario (contexto de negocio, restricciones), haz **una** pregunta breve y espera. Si no falta, sigue sin preguntar.
5. Redacta el **resumen autocontenido**: objetivo, estado actual, intentos fallidos con su mecanismo, supuestos sin comprobar, restricciones y criterio de éxito. Debe entenderse sin haber visto la conversación, porque es lo único que recibirán los subagentes.

## Fase 2 – Investigación (profundo e iterativo)

- Unas 5 búsquedas como máximo (web, GitHub, issues, papers), centradas en el bloqueo concreto y no en el tema general.
- Cita cada fuente con su enlace. Quédate con lo que aporte un mecanismo nuevo, no con lo que repita lo ya probado.
- Si la skill REA (Reverse Engineer Anything) aparece en las skills disponibles y hay una app que ya resuelve bien el problema, puedes proponer investigar cómo lo hace. Solo con software propio o autorizado.

## Fase 3 – Pensamiento divergente (subagentes de contexto limpio)

Lee `${CLAUDE_SKILL_DIR}/references/subagente.md` (plantilla del encargo) y `${CLAUDE_SKILL_DIR}/references/tecnicas.md` (enfoques con ejemplos).

- Lanza los subagentes con la herramienta Agent, tipo `general-purpose`, pasando el parámetro `model`. **Nunca uses el tipo `fork`**: hereda la conversación, que es justo el sesgo que se quiere evitar. El encargo lleva solo la plantilla rellena con el resumen de la fase 1, lo encontrado en la fase 2 y la lista de mecanismos ya probados.
- **Modelo.** Mira en tu system prompt qué modelo mueve esta sesión:
  - modo rápido: un subagente con `sonnet` si la sesión es Opus; con `opus` en cualquier otro caso;
  - profundo e iterativo: dos subagentes **en paralelo** (mismo mensaje) con modelos distintos entre sí y, si se puede, distintos al de la sesión. Si la sesión es Opus, `sonnet` + `fable`; si no, `opus` + `sonnet` (o `opus` + `fable` si la sesión es Sonnet);
  - para generar muchas variantes rápidas de un prompt (enfoque Edison), `haiku`;
  - si no sabes qué modelo es la sesión, usa `sonnet` y `opus`.
- **Fusión.** Junta las ideas, quita duplicados por mecanismo, descarta las que repitan intentos.md y las que sean relleno ("lo que diría Einstein" no es una idea; "probar el prompt con una entrada de 1 token y otra de 50k para ver dónde se rompe" sí).

## Fase 4 – Del error a la oportunidad (profundo e iterativo)

Lee la sección «Del error a la oportunidad» de `${CLAUDE_SKILL_DIR}/references/tecnicas.md`. Pregúntate qué hace bien el "fallo" y si puede aprovecharse de otra forma. Aplica los 5 porqués hasta la causa raíz y escríbelos en cadena (porqué 1 → … → causa raíz). Si sale una idea nueva, súmala a las de la fase 3.

## Fase 5 – Propuesta, implementación y medición

**Propuesta.** Presenta 3-5 alternativas realmente distintas (3 en modo rápido) en una tabla: idea, enfoque de origen, supuesto que rompe, pros, contras, riesgo y esfuerzo. Recomienda una y explica por qué en dos líneas. Prioriza lo simple y medible. **Espera a que el usuario elija.**

**Conjunto de prueba** (antes de implementar). Lee `${CLAUDE_SKILL_DIR}/references/evaluacion.md`.

- Reutiliza primero lo que exista: tests, benchmark o datasets en `.desatascar/`.
- Prompts, modo rápido: al menos 10 casos con criterios binarios (sí/no). Si no hay datos reales, propón como mucho 10 y pide validación rápida.
- Prompts, profundo e iterativo: al menos 20 casos (recomendado 30 o más) con criterios binarios, y un 20-30 % reservado que **nunca** se usa para iterar. Si los casos son inventados, espera a que el usuario los valide: unos criterios mal definidos invalidan toda la medición.
- Código: tests o benchmark existentes; si no los hay, créalos.
- Datos personales reales: anonimízalos antes de mandarlos a cualquier proveedor externo.

**Medición.**

- Modo rápido: tests existentes o comparación emparejada sobre al menos 10 casos, sin A/A ni bootstrap. Avisa de que el resultado es **orientativo** y ofrece la medición completa.
- Profundo e iterativo: test A/A (3 o más repeticiones), comparación emparejada caso a caso, juez por pares en los dos órdenes con criterios binarios, bootstrap de 1000 remuestreos y comparación con el ruido del A/A. Para prompts, usa el conjunto de iteración completo (un cambio de prompt puede afectar a cualquier caso). Para código, basta con los tests de lo que toca el cambio.
- Script: `python3 ${CLAUDE_SKILL_DIR}/scripts/evaluar.py --help`. Acepta prompts que generar o salidas ya generadas. Prueba primero con `--dry-run`.
- Si la diferencia no supera el ruido del A/A o el IC incluye el 0, el resultado es **"sin evidencia de mejora"**, no "mejora pequeña". Di también el efecto mínimo detectable: si es mayor que la mejora que se busca, el problema es que falta muestra.

**Coste.** Antes de una medición que llame a la API, da el número de llamadas y una estimación en euros (precios en `evaluacion.md`). Para ahorrar:

- juez barato (haiku) solo si coincide con el criterio del usuario en 10 casos que él valide;
- caché de prompts;
- Batch API solo si no hace falta el resultado ya y el conjunto es grande;
- parar en cuanto el resultado sea claro.

Registra el resultado en intentos.md, también cuando falle.

## Bucle iterativo (solo `iterativo`)

Al empezar, pide un límite de coste en algo que se pueda contar (máximo de llamadas al modelo o de tokens), con una estimación en euros como referencia. Pásalo al script con `--max-llamadas`.

1. Parte de la mejor versión actual y su puntuación.
2. Genera 2-3 variantes con los enfoques de la fase 3, sin repetir mecanismos registrados.
3. Evalúalas contra el mismo conjunto de iteración. Solo se acepta una variante si supera a la base por encima del ruido del A/A.
4. Registra cada intento y repite.

Frenos: máximo 5 rondas o el límite de coste, lo que llegue antes; parar si no hay mejora en 2 rondas seguidas. Al terminar, comprueba que la mejora se mantiene en el conjunto reservado (`--solo-reservado`). El usuario aprueba el resultado final antes de llevarlo a producción.

## Fase 6 – Si nada funciona

Solo si ninguna alternativa supera el ruido, pregunta: «¿Cómo lo resolverías tú sin IA?». Usa la respuesta como semilla, añádela al resumen y vuelve a las fases 3-5.

## Reglas

- Lo simple y verificable gana a lo complejo.
- Nada de claves de API en código ni en la conversación: solo variables de entorno (`ANTHROPIC_API_KEY`).
- Nunca envíes datos personales reales a proveedores externos sin anonimizarlos.
- Cada idea que se pruebe, funcione o no, acaba en intentos.md.
