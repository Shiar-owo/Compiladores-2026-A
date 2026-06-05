# Compiladores-2026-A
Fase 1 — Frontend del compilador (reutilizado)
El linter se acopla al final del pipeline estándar. No reimplementa el lexer ni el parser; consume directamente el AST producido por el compilador huésped.
Fase 2 — Análisis semántico extendido (núcleo del linter)
Tres subsistemas trabajando en paralelo:

El CFG Builder modela todos los caminos de ejecución posibles (condicionales, loops, excepciones).
El DFG Builder rastrea cómo los valores fluyen de variable en variable a través de asignaciones.
El Taint Propagation Engine es el corazón: marca cada variable que proviene de una fuente controlada por el usuario ($_GET, $_POST, STDIN, etc.) y propaga esa "mancha" a través de todo el DFG, incluyendo llamadas a funciones y retornos.

 CFG y DFG en el Contexto del Security Linter

## 1. CFG — Control Flow Graph

El **Control Flow Graph** (grafo de flujo de control) modela todos los caminos posibles de ejecución de un programa. Cada nodo del CFG es un **bloque básico**: una secuencia de instrucciones que siempre se ejecutan de forma consecutiva, sin saltos intermedios. Cada arista representa una transferencia de control posible entre bloques.

### Estructura

Dado el siguiente fragmento:

```python
user_id = input("ID: ")
if user_id.isdigit():
    query = "SELECT * FROM users WHERE id = " + user_id
else:
    query = "SELECT * FROM users"
cursor.execute(query)
```

El CFG resultante contiene cuatro bloques básicos:

| Bloque | Instrucciones                              |
|--------|--------------------------------------------|
| B1     | `user_id = input("ID: ")`                  |
| B2     | `query = "SELECT ... WHERE id = " + user_id` |
| B3     | `query = "SELECT * FROM users"`            |
| B4     | `cursor.execute(query)`                    |

Con las aristas: B1 → B2 (rama `True`), B1 → B3 (rama `False`), B2 → B4, B3 → B4.


## 2. DFG — Data Flow Graph

El **Data Flow Graph** (grafo de flujo de datos) modela cómo los **valores fluyen de una variable a otra** a través de asignaciones, operaciones y llamadas a función. Cada nodo representa una definición (`DEF`) o un uso (`USE`) de una variable, y las aristas conectan el punto donde se produce un valor con todos los puntos donde ese valor es consumido.

### Estructura

Para el mismo fragmento anterior, el DFG captura la siguiente cadena:

```
input("ID: ")  →  DEF user_id
                       │
              USE user_id  →  DEF query   (concatenación)
                                   │
                          USE query  →  cursor.execute()
```

Cada eslabón de esta cadena es una arista en el DFG. El análisis de taint recorre estas aristas para propagar la 
"mancha" desde la fuente hasta el sumidero.

Por qué se necesitan ambos

Ninguno de los dos grafos es suficiente de forma aislada:

- **Solo con el CFG** se conocen los bloques de ejecución y las ramas del programa, pero no qué le ocurre a los datos dentro de cada bloque ni cómo fluyen entre variables.
- **Solo con el DFG** se conoce la cadena de dependencias entre valores, pero no es posible razonar sobre rutas condicionales: un dato contaminado puede llegar al sink únicamente por una rama específica, y sin el CFG el linter no puede saberlo.

El **Taint Engine de la Fase 2** superpone ambos grafos:

1. Recorre el **DFG** para propagar el estado `TAINTED` variable a variable.
2. Consulta el **CFG** para verificar que la ruta de propagación es alcanzable en tiempo de ejecución.
3. Comprueba, en cada ruta válida, si existe algún nodo de sanitización (`int()`, `re.escape()`, consulta parametrizada) antes del sink.

Solo la intersección de ambos grafos permite detectar rutas críticas reales minimizando al mismo tiempo los falsos positivos y los falsos negativos, que es el objetivo central del proyecto.


La Symbol Table enriquecida almacena no solo tipos, sino el estado de taint de cada símbolo. El Type Checker usa esa información para descartar rutas semánticamente imposibles y reducir falsos positivos.
Fase 3 — Análisis de rutas críticas
Con el grafo de taint construido, el Critical Path Finder recorre el CFG+DFG buscando caminos desde cada source marcado hasta cada sink SQL. En cada ruta verifica si algún nodo intermedio es un sanitizador reconocido (htmlspecialchars, PDO::quote, pg_escape_string, etc.). El análisis interprocedural expande las llamadas a funciones para no perder rutas que crucen límites de función.
Fase 4 — Decisión y reporte

Ruta sin sanitizador → Vulnerability Report con traza completa (línea de origen, variable contaminada, punto de inyección), severidad calculada y sugerencia de corrección.
Ruta con sanitizador verificado → suprimida, sin alerta.