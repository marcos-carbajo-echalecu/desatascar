# Técnicas

Cada técnica lleva un ejemplo aplicado a prompts (P) o a código (C). Usa solo las que encajen con el tipo de bloqueo.

## Índice
1. Pensadores
2. Técnicas específicas de IA
3. Del error a la oportunidad (fase 4)
4. Qué enfoque según el tipo de bloqueo

## 1. Pensadores

**Einstein: experimento mental y caso extremo.** Lleva una variable al límite para ver qué se rompe.
- P: pasa el clasificador por una entrada vacía, una de una sola palabra y otra de 20.000 tokens. Si falla igual en las tres, el problema no está en el contenido sino en las instrucciones.
- C: ejecuta la función con 0, 1 y 10⁶ elementos. Si el error solo sale con 1, es un caso límite, no la lógica general.

**Da Vinci: copiar de otro dominio.** ¿Quién resuelve ya un problema con la misma forma?
- P: un clasificador de intenciones ambiguo se parece al triaje de urgencias: primero una pregunta de descarte ("¿es una queja?") y después la categoría fina.
- C: un problema de deduplicación lenta se parece al de los correctores ortográficos: indexar por n-gramas en lugar de comparar todos contra todos.

**Feynman: si no se puede explicar simple, no se entiende.**
- P: reescribe la tarea en 3 frases para un becario. Si no puedes, el modelo tampoco la entiende; el prompt mezcla dos tareas.
- C: explica en voz alta qué invariante mantiene el bucle. La línea en la que te trabas suele ser la del bug.

**Munger: inversión.** ¿Qué haría que fallase seguro? Evítalo.
- P: "para que el modelo clasifique mal seguro, le daría categorías que se solapan y ningún ejemplo de frontera". Comprueba si el prompt actual hace justo eso.
- C: "para que esto sea lento seguro, haría una consulta por fila". Busca el N+1.

**Edison: muchas variantes rápidas y medir.**
- P: genera 10 variantes del prompt con haiku, cada una con un único cambio, y mide todas en los mismos 10 casos. Quédate con las 2 mejores para la medición completa.
- C: prueba 5 tamaños de lote en un microbenchmark en lugar de razonar cuál es el óptimo.

**De Bono: seis sombreros.** Pasa la idea por lógica (blanco), emoción (rojo), riesgos (negro), optimismo (amarillo), creatividad (verde) y control del proceso (azul).
- P: con el sombrero negro sale que el juez y el generador son el mismo modelo y comparten sesgo; con el verde, usar otro modelo como juez.

**Primeros principios: reconstruir desde cero sin copiar lo existente.**
- P: olvida el prompt actual. ¿Cuál es la entrada mínima, qué decisión exacta tiene que tomar el modelo y qué salida necesita el sistema? Escribe un prompt nuevo de 10 líneas y compáralo con el largo.
- C: en lugar de parchear el parser, define la gramática de la entrada y genera el parser a partir de ella.

**Panel de perfiles: escéptico, ingeniero, usuario final y negocio debaten.**
- P: el escéptico pregunta si los casos de prueba representan el tráfico real; el usuario final, si importa la categoría o solo la acción siguiente; negocio, qué error cuesta más (falso positivo o falso negativo).

## 2. Técnicas específicas de IA

| Técnica | Cuándo | Ejemplo |
|---|---|---|
| Cambiar la arquitectura del prompt | Instrucciones mezcladas o en orden confuso | Separar rol, tarea, criterios y formato en bloques etiquetados; poner los criterios de decisión antes que el contexto |
| Dividir en varias llamadas o cadenas | Una llamada hace dos tareas | Primero extraer los hechos de la entrada y después clasificar sobre esos hechos |
| Few-shot | El modelo no sabe qué resultado se espera en los casos frontera | 3-5 ejemplos elegidos justo en las fronteras entre categorías, no casos fáciles |
| Salida estructurada | Fallos de formato o parseo | `output_config.format` con un esquema JSON; enum para las categorías |
| Modelo como juez | No hay métrica automática | Juez por pares con criterios binarios, en los dos órdenes (ver evaluacion.md) |
| Cambiar de modelo o de esfuerzo | Fallos de razonamiento, no de instrucción | Probar el mismo prompt con esfuerzo `low` y `high`; si `high` no mejora, el problema no es de razonamiento |
| Añadir o quitar contexto | El modelo se distrae o le falta un dato | Quitar la mitad del contexto y medir; a veces mejora porque desaparece una instrucción contradictoria |

## 3. Del error a la oportunidad (fase 4)

Pregunta guía: ¿qué hace bien el "fallo"? ¿Dónde sería justo lo que se busca?

- **Post-it:** un pegamento demasiado débil acabó siendo el producto. P: si el modelo "se inventa" una categoría nueva una y otra vez, quizá esa categoría falta de verdad en la taxonomía.
- **IKEA:** quitar las patas para que la mesa cupiera en el coche dio lugar al mueble plano. C: si la tarea no cabe en una llamada, desmontarla en piezas puede ser el diseño correcto y no un parche.
- **Penicilina:** Fleming aprovechó un cultivo contaminado. P: los casos en los que el modelo "falla" de forma consistente son un dataset de casos frontera gratis para el few-shot.
- **Pixar:** los primeros borradores son malos y se iteran sin miedo. Mide un borrador feo pronto en vez de pulir una idea sin datos.

**5 porqués (Toyota).** Ejemplo:
1. ¿Por qué falla el clasificador? Confunde "queja" con "duda".
2. ¿Por qué? Los mensajes mezclan las dos cosas.
3. ¿Por qué no lo resuelve el prompt? Exige una única etiqueta.
4. ¿Por qué una sola? El sistema de destino solo admite un campo.
5. ¿Por qué? Nadie lo revisó desde que se diseñó.

Causa raíz: el problema es de diseño (etiqueta única), no de prompt. Oportunidad: multi-etiqueta con prioridad.

## 4. Qué enfoque según el tipo de bloqueo

| Bloqueo | Enfoques que suelen rendir |
|---|---|
| Prompt | Feynman, Munger, Edison, técnicas de IA |
| Lógica de código | Einstein (casos extremos), Feynman, primeros principios |
| Rendimiento | Edison (medir variantes), Da Vinci, Munger |
| Librería/API | Da Vinci (cómo lo hacen otros), primeros principios, panel |
| Diseño | Primeros principios, De Bono, panel, 5 porqués |
