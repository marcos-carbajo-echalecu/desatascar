# Desatascar

Skill para [Claude Code](https://claude.com/claude-code) que sirve para cuando llevas varios intentos con un prompt o un trozo de código que no mejora.

Cuando la IA se atasca, lo habitual es seguir probando variantes de la misma idea: reescribir el prompt, reescribirlo otra vez, añadir "revisa bien". Desatascar saca el problema de ese bucle. Busca ideas con agentes que no han visto la conversación y mide cada cambio para distinguir una mejora real de un golpe de suerte.

## Qué hace

1. **Diagnóstico.** Resume lo que ya se ha probado y por qué falló, y saca a la luz los supuestos que se están dando por buenos sin comprobar. Explica el problema con una analogía sencilla y lo clasifica: prompt, lógica de código, rendimiento, librería/API o diseño.
2. **Ideas desde fuera.** Lanza subagentes con contexto limpio, que solo reciben un resumen del problema y no arrastran el sesgo de la conversación. Cada uno elige enfoques de pensamiento según el tipo de bloqueo: Munger (qué haría que fallase seguro), Da Vinci (quién resuelve ya algo parecido), Edison (muchas variantes rápidas y medir), Feynman, primeros principios, los seis sombreros de De Bono o un panel con un escéptico, un ingeniero, el usuario final y negocio.
3. **Propuesta.** Presenta de 3 a 5 alternativas en una tabla con pros, contras, riesgo y esfuerzo, recomienda una y espera a que elijas.
4. **Medición.** Prueba la alternativa con un conjunto de casos fijo. En los modos profundo e iterativo hace un test A/A para medir el ruido, una comparación caso a caso, un juez por pares en los dos órdenes y un bootstrap. Si la diferencia no supera el ruido, el resultado es "sin evidencia de mejora".
5. **Registro.** Apunta cada intento, funcione o no, en `.desatascar/intentos.md` dentro de tu proyecto, para no volver a probar lo mismo con otras palabras.

## Instalación

Necesitas tener Claude Code instalado. La skill es esta carpeta entera, y tiene que quedar en `~/.claude/skills/desatascar`.

### Mac o Linux

Abre la app Terminal, pega esta línea y pulsa Intro:

```bash
git clone https://github.com/marcos-carbajo-echalecu/desatascar.git ~/.claude/skills/desatascar
```

### Windows

Abre PowerShell, pega esta línea y pulsa Intro:

```powershell
git clone https://github.com/marcos-carbajo-echalecu/desatascar.git "$HOME\.claude\skills\desatascar"
```

### Sin terminal

1. En esta página, pulsa el botón verde **Code** y después **Download ZIP**.
2. Descomprime el archivo. Saldrá una carpeta llamada `desatascar-main`.
3. Cámbiale el nombre a `desatascar` y muévela dentro de la carpeta `.claude/skills` de tu usuario (créala si no existe). En Mac, la carpeta `.claude` está oculta: en Finder pulsa Cmd + Mayús + . para verla.

Al final tiene que existir el archivo `~/.claude/skills/desatascar/SKILL.md`. Si ves `desatascar/desatascar-main/SKILL.md`, la carpeta ha quedado dentro de otra y la skill no aparecerá.

### Úsala

Abre una sesión nueva de Claude Code y escribe `/desatascar`. La skill solo se ejecuta cuando la llamas tú; Claude no la activa por su cuenta.

### Requisitos para la medición con la API (opcional)

El script `scripts/evaluar.py` compara dos versiones de un prompt llamando a la API de Anthropic. Solo lo necesitas para la medición completa:

- Python 3.10 o superior y el SDK: `pip install anthropic`
- La variable de entorno `ANTHROPIC_API_KEY`. No escribas la clave en ningún archivo.

Para ver cómo funciona sin gastar nada:

```bash
python3 ~/.claude/skills/desatascar/scripts/evaluar.py --dry-run
```

Antes de cada medición real, la skill te dice cuántas llamadas hará y cuánto costará aproximadamente.

## Modos

La primera palabra después del comando elige el modo. El resto es la descripción del problema.

| Modo | Comando | Qué hace |
| --- | --- | --- |
| Rápido | `/desatascar <problema>` | Diagnóstico, un subagente y 3 alternativas. La medición es orientativa, con al menos 10 casos. |
| Profundo | `/desatascar profundo <problema>` | Añade búsqueda en internet, dos subagentes en paralelo con modelos distintos, los 5 porqués y la medición completa. |
| Iterativo | `/desatascar iterativo <problema>` | Como el profundo, pero repite rondas de mejora (máximo 5) con un límite de llamadas que fijas tú. Al final comprueba la mejora con casos reservados que no se usaron para iterar. |

## Ejemplo

```
/desatascar profundo el primer DM de Insta Stalker no consigue respuestas
```

En este caso la skill:

1. Repasa las versiones del mensaje que ya se han probado y qué supuestos hay detrás, por ejemplo que el problema es el texto y no a quién se le envía.
2. Busca fuera qué funciona en mensajes de primer contacto y pide ideas a dos subagentes con modelos distintos.
3. Propone varias alternativas y, cuando eliges una, la compara con el mensaje actual sobre un conjunto de casos. Solo la da por buena si gana por encima del ruido.

## Estructura

```
desatascar/
├── SKILL.md                  # instrucciones de la skill
├── README.md
├── LICENSE
├── references/
│   ├── subagente.md          # plantilla del encargo a los subagentes
│   ├── tecnicas.md           # enfoques de pensamiento con ejemplos
│   └── evaluacion.md         # cómo medir sin confundir suerte con mejora
└── scripts/
    └── evaluar.py            # comparación A/B con A/A, juez por pares y bootstrap
```

## Autor y licencia

Marcos Carbajo. Licencia MIT: puedes usarla, cambiarla y compartirla. Ver [LICENSE](LICENSE).
