# Compiladores-2026-A
Fase 1 — Frontend del compilador (reutilizado)
El linter se acopla al final del pipeline estándar. No reimplementa el lexer ni el parser; consume directamente el AST producido por el compilador huésped.
Fase 2 — Análisis semántico extendido (núcleo del linter)
Tres subsistemas trabajando en paralelo:

El CFG Builder modela todos los caminos de ejecución posibles (condicionales, loops, excepciones).
El DFG Builder rastrea cómo los valores fluyen de variable en variable a través de asignaciones.
El Taint Propagation Engine es el corazón: marca cada variable que proviene de una fuente controlada por el usuario ($_GET, $_POST, STDIN, etc.) y propaga esa "mancha" a través de todo el DFG, incluyendo llamadas a funciones y retornos.

La Symbol Table enriquecida almacena no solo tipos, sino el estado de taint de cada símbolo. El Type Checker usa esa información para descartar rutas semánticamente imposibles y reducir falsos positivos.
Fase 3 — Análisis de rutas críticas
Con el grafo de taint construido, el Critical Path Finder recorre el CFG+DFG buscando caminos desde cada source marcado hasta cada sink SQL. En cada ruta verifica si algún nodo intermedio es un sanitizador reconocido (htmlspecialchars, PDO::quote, pg_escape_string, etc.). El análisis interprocedural expande las llamadas a funciones para no perder rutas que crucen límites de función.
Fase 4 — Decisión y reporte

Ruta sin sanitizador → Vulnerability Report con traza completa (línea de origen, variable contaminada, punto de inyección), severidad calculada y sugerencia de corrección.
Ruta con sanitizador verificado → suprimida, sin alerta.