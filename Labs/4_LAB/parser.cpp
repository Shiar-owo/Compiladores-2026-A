/* ============================================================
   Compiladores - Laboratorio 04
   Parser / Analizador Sintáctico  ──  Lenguaje PL/0 (extendido)
   Gramática:
     program    = "program" ident ";" block "." .
     block      = ["const" ident "=" number {"," ident "=" number} ";"]
                  {"var" ident {"," ident} ":" type ";"}
                  {"procedure" ident ";" block ";"} statement .
     type       = "integer" | "boolean" | "real" .
     statement  = [ ident ":=" expression
                  | "call" ident
                  | "begin" statement {";" statement} "end"
                  | "if" condition "then" statement
                  | "while" condition "do" statement ] .
     condition  = "odd" expression
                  | expression ("="|"#"|"<"|"<="|">"|">=") expression .
     expression = ["+"|"-"] term {("+"|"-") term} .
     term       = factor {("*"|"/") factor} .
     factor     = ident | number | "(" expression ")" .
   ============================================================ */

#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>

/* ── Códigos de token ── */
#define TK_ID           256
#define TK_NUM          257

/* Palabras reservadas */
#define TK_PROGRAM      258
#define TK_CONST        259
#define TK_VAR          260
#define TK_PROCEDURE    261
#define TK_CALL         262
#define TK_BEGIN        263
#define TK_END          264
#define TK_IF           265
#define TK_THEN         266
#define TK_WHILE        267
#define TK_DO           268
#define TK_ODD          269

/* Operadores relacionales */
#define TK_IGUAL        270
#define TK_DISTINTO     271
#define TK_MENORIGUAL   272
#define TK_MAYORIGUAL   273

/* Operador de asignación */
#define TK_ASIGNACION   274

/* Tipos de datos */
#define TK_INTEGER      275
#define TK_BOOLEAN      276
#define TK_REAL         277

/* Dos puntos simple */
#define TK_DOSPUNTOS    278

/* Operadores / delimitadores de un carácter (valor ASCII) */
#define TK_MENOR        '<'
#define TK_MAYOR        '>'
#define TK_MAS          '+'
#define TK_MENOS        '-'
#define TK_MULT         '*'
#define TK_DIV          '/'
#define TK_PARI         '('
#define TK_PARD         ')'
#define TK_COMA         ','
#define TK_PUNTOYCOMA   ';'
#define TK_PUNTO        '.'

/* ── Variables globales ── */
FILE *f;
char  lexema[256];
int   token_actual;
int   linea = 1;          /* contador de línea para mensajes de error */
int   errores = 0;        /* cantidad de errores encontrados          */

/* ── Prototipos del scanner ── */
int  scanner(void);
int  es_palres(void);

/* ── Prototipos del parser ── */
void avanzar(void);
void match(int tk_esperado);
const char *nombre_token(int tk);

void parse_program(void);
void parse_block(void);
void parse_const_decl(void);
void parse_var_decl(void);
void parse_type(void);
void parse_procedure_decl(void);
void parse_statement(void);
void parse_condition(void);
void parse_expression(void);
void parse_term(void);
void parse_factor(void);

/* ================================================================
   TABLA DE PALABRAS RESERVADAS
   ================================================================ */
typedef struct { const char *palabra; int token; } PalRes;

static PalRes palabras_reservadas[] = {
    {"program",   TK_PROGRAM},
    {"const",     TK_CONST},
    {"var",       TK_VAR},
    {"procedure", TK_PROCEDURE},
    {"call",      TK_CALL},
    {"begin",     TK_BEGIN},
    {"end",       TK_END},
    {"if",        TK_IF},
    {"then",      TK_THEN},
    {"while",     TK_WHILE},
    {"do",        TK_DO},
    {"odd",       TK_ODD},
    {"integer",   TK_INTEGER},
    {"boolean",   TK_BOOLEAN},
    {"real",      TK_REAL},
    {NULL, -1}
};

int es_palres(void) {
    for (int i = 0; palabras_reservadas[i].palabra != NULL; i++)
        if (strcmp(lexema, palabras_reservadas[i].palabra) == 0)
            return palabras_reservadas[i].token;
    return -1;
}

/* ================================================================
   SCANNER
   ================================================================ */
int scanner(void) {
    int c, i;

    do {
        c = fgetc(f);
        if (c == '\n') linea++;
    } while (c != EOF && isspace(c));

    if (c == EOF) return EOF;

    if (isalpha(c) || c == '_') {
        i = 0;
        do {
            lexema[i++] = (char)c;
            c = fgetc(f);
        } while (isalnum(c) || c == '_');
        lexema[i] = '\0';
        ungetc(c, f);
        int tk = es_palres();
        return (tk >= 0) ? tk : TK_ID;
    }

    if (isdigit(c)) {
        i = 0;
        do {
            lexema[i++] = (char)c;
            c = fgetc(f);
        } while (isdigit(c));
        lexema[i] = '\0';
        ungetc(c, f);
        return TK_NUM;
    }

    switch (c) {
        case '+': lexema[0]='+'; lexema[1]='\0'; return TK_MAS;
        case '-': lexema[0]='-'; lexema[1]='\0'; return TK_MENOS;
        case '*': lexema[0]='*'; lexema[1]='\0'; return TK_MULT;
        case '/': lexema[0]='/'; lexema[1]='\0'; return TK_DIV;
        case '=': lexema[0]='='; lexema[1]='\0'; return TK_IGUAL;
        case '#': lexema[0]='#'; lexema[1]='\0'; return TK_DISTINTO;
        case '<':
            c = fgetc(f);
            if (c == '=') { strcpy(lexema, "<="); return TK_MENORIGUAL; }
            ungetc(c, f);
            lexema[0]='<'; lexema[1]='\0'; return TK_MENOR;
        case '>':
            c = fgetc(f);
            if (c == '=') { strcpy(lexema, ">="); return TK_MAYORIGUAL; }
            ungetc(c, f);
            lexema[0]='>'; lexema[1]='\0'; return TK_MAYOR;
        case ':':
            c = fgetc(f);
            if (c == '=') { strcpy(lexema, ":="); return TK_ASIGNACION; }
            ungetc(c, f);
            lexema[0]=':'; lexema[1]='\0'; return TK_DOSPUNTOS;
        case '(':  lexema[0]='('; lexema[1]='\0'; return TK_PARI;
        case ')':  lexema[0]=')'; lexema[1]='\0'; return TK_PARD;
        case ',':  lexema[0]=','; lexema[1]='\0'; return TK_COMA;
        case ';':  lexema[0]=';'; lexema[1]='\0'; return TK_PUNTOYCOMA;
        case '.':  lexema[0]='.'; lexema[1]='\0'; return TK_PUNTO;
        default:
            fprintf(stderr, "[línea %d] Carácter desconocido: '%c'\n", linea, c);
            return scanner();
    }
}

/* ================================================================
   UTILIDADES DEL PARSER
   ================================================================ */

/* Nombre legible de un token para mensajes de error */
const char *nombre_token(int tk) {
    switch (tk) {
        case TK_ID:          return "identificador";
        case TK_NUM:         return "número";
        case TK_PROGRAM:     return "'program'";
        case TK_CONST:       return "'const'";
        case TK_VAR:         return "'var'";
        case TK_PROCEDURE:   return "'procedure'";
        case TK_CALL:        return "'call'";
        case TK_BEGIN:       return "'begin'";
        case TK_END:         return "'end'";
        case TK_IF:          return "'if'";
        case TK_THEN:        return "'then'";
        case TK_WHILE:       return "'while'";
        case TK_DO:          return "'do'";
        case TK_ODD:         return "'odd'";
        case TK_INTEGER:     return "'integer'";
        case TK_BOOLEAN:     return "'boolean'";
        case TK_REAL:        return "'real'";
        case TK_IGUAL:       return "'='";
        case TK_DISTINTO:    return "'#'";
        case TK_MENORIGUAL:  return "'<='";
        case TK_MAYORIGUAL:  return "'>='";
        case TK_ASIGNACION:  return "':='";
        case TK_DOSPUNTOS:   return "':'";
        case TK_MENOR:       return "'<'";
        case TK_MAYOR:       return "'>'";
        case TK_MAS:         return "'+'";
        case TK_MENOS:       return "'-'";
        case TK_MULT:        return "'*'";
        case TK_DIV:         return "'/'";
        case TK_PARI:        return "'('";
        case TK_PARD:        return "')'";
        case TK_COMA:        return "','";
        case TK_PUNTOYCOMA:  return "';'";
        case TK_PUNTO:       return "'.'";
        case EOF:            return "fin de archivo";
        default:             return "token desconocido";
    }
}

/* Consume el token actual y obtiene el siguiente */
void avanzar(void) {
    token_actual = scanner();
}

/* Verifica que el token actual sea el esperado y avanza;
   si no coincide emite error pero intenta continuar. */
void match(int tk_esperado) {
    if (token_actual == tk_esperado) {
        avanzar();
    } else {
        fprintf(stderr,
            "[línea %d] Error sintáctico: se esperaba %s pero se encontró %s ('%s')\n",
            linea,
            nombre_token(tk_esperado),
            nombre_token(token_actual),
            lexema);
        errores++;
        /* recuperación mínima: si el token inesperado no es EOF, avanzar */
        if (token_actual != EOF) avanzar();
    }
}

/* ================================================================
   REGLAS GRAMATICALES
   ================================================================ */

/* program = "program" ident ";" block "." */
void parse_program(void) {
    printf("[parser] program\n");
    match(TK_PROGRAM);
    match(TK_ID);
    match(TK_PUNTOYCOMA);
    parse_block();
    match(TK_PUNTO);
}

/* block = [const_decl] {var_decl} {procedure_decl} statement */
void parse_block(void) {
    printf("[parser] block\n");

    if (token_actual == TK_CONST)
        parse_const_decl();

    while (token_actual == TK_VAR)
        parse_var_decl();

    while (token_actual == TK_PROCEDURE)
        parse_procedure_decl();

    parse_statement();
}

/* const_decl = "const" ident "=" number {"," ident "=" number} ";" */
void parse_const_decl(void) {
    printf("[parser]   const_decl\n");
    match(TK_CONST);
    match(TK_ID);
    match(TK_IGUAL);
    match(TK_NUM);
    while (token_actual == TK_COMA) {
        avanzar();          /* consume ',' */
        match(TK_ID);
        match(TK_IGUAL);
        match(TK_NUM);
    }
    match(TK_PUNTOYCOMA);
}

/* var_decl = "var" ident {"," ident} ":" type ";" */
void parse_var_decl(void) {
    printf("[parser]   var_decl\n");
    match(TK_VAR);
    match(TK_ID);
    while (token_actual == TK_COMA) {
        avanzar();          /* consume ',' */
        match(TK_ID);
    }
    match(TK_DOSPUNTOS);
    parse_type();
    match(TK_PUNTOYCOMA);
}

/* type = "integer" | "boolean" | "real" */
void parse_type(void) {
    if (token_actual == TK_INTEGER ||
        token_actual == TK_BOOLEAN ||
        token_actual == TK_REAL) {
        printf("[parser]     type (%s)\n", lexema);
        avanzar();
    } else {
        fprintf(stderr,
            "[línea %d] Error sintáctico: se esperaba un tipo "
            "(integer, boolean, real) pero se encontró %s ('%s')\n",
            linea, nombre_token(token_actual), lexema);
        errores++;
        if (token_actual != EOF) avanzar();
    }
}

/* procedure_decl = "procedure" ident ";" block ";" */
void parse_procedure_decl(void) {
    printf("[parser]   procedure_decl\n");
    match(TK_PROCEDURE);
    match(TK_ID);
    match(TK_PUNTOYCOMA);
    parse_block();
    match(TK_PUNTOYCOMA);
}

/* statement = [ ident ":=" expression
               | "call" ident
               | "begin" statement {";" statement} "end"
               | "if" condition "then" statement
               | "while" condition "do" statement ]         */
void parse_statement(void) {
    switch (token_actual) {

        case TK_ID:
            printf("[parser]   statement: asignación\n");
            avanzar();              /* consume ident */
            match(TK_ASIGNACION);
            parse_expression();
            break;

        case TK_CALL:
            printf("[parser]   statement: call\n");
            avanzar();              /* consume 'call' */
            match(TK_ID);
            break;

        case TK_BEGIN:
            printf("[parser]   statement: begin..end\n");
            avanzar();              /* consume 'begin' */
            parse_statement();
            while (token_actual == TK_PUNTOYCOMA) {
                avanzar();          /* consume ';' */
                parse_statement();
            }
            match(TK_END);
            break;

        case TK_IF:
            printf("[parser]   statement: if..then\n");
            avanzar();              /* consume 'if' */
            parse_condition();
            match(TK_THEN);
            parse_statement();
            break;

        case TK_WHILE:
            printf("[parser]   statement: while..do\n");
            avanzar();              /* consume 'while' */
            parse_condition();
            match(TK_DO);
            parse_statement();
            break;

        default:
            /* sentencia vacía — válida en PL/0 */
            printf("[parser]   statement: (vacío)\n");
            break;
    }
}

/* condition = "odd" expression
             | expression ("="|"#"|"<"|"<="|">"|">=") expression */
void parse_condition(void) {
    if (token_actual == TK_ODD) {
        printf("[parser]     condition: odd\n");
        avanzar();
        parse_expression();
    } else {
        printf("[parser]     condition: relacional\n");
        parse_expression();
        if (token_actual == TK_IGUAL    || token_actual == TK_DISTINTO ||
            token_actual == TK_MENOR    || token_actual == TK_MENORIGUAL ||
            token_actual == TK_MAYOR    || token_actual == TK_MAYORIGUAL) {
            avanzar();              /* consume operador relacional */
        } else {
            fprintf(stderr,
                "[línea %d] Error sintáctico: se esperaba operador relacional "
                "pero se encontró %s ('%s')\n",
                linea, nombre_token(token_actual), lexema);
            errores++;
        }
        parse_expression();
    }
}

/* expression = ["+"|"-"] term {("+"|"-") term} */
void parse_expression(void) {
    if (token_actual == TK_MAS || token_actual == TK_MENOS)
        avanzar();                  /* signo opcional */
    parse_term();
    while (token_actual == TK_MAS || token_actual == TK_MENOS) {
        avanzar();
        parse_term();
    }
}

/* term = factor {("*"|"/") factor} */
void parse_term(void) {
    parse_factor();
    while (token_actual == TK_MULT || token_actual == TK_DIV) {
        avanzar();
        parse_factor();
    }
}

/* factor = ident | number | "(" expression ")" */
void parse_factor(void) {
    if (token_actual == TK_ID) {
        avanzar();
    } else if (token_actual == TK_NUM) {
        avanzar();
    } else if (token_actual == TK_PARI) {
        avanzar();                  /* consume '(' */
        parse_expression();
        match(TK_PARD);
    } else {
        fprintf(stderr,
            "[línea %d] Error sintáctico: se esperaba identificador, "
            "número o '(' pero se encontró %s ('%s')\n",
            linea, nombre_token(token_actual), lexema);
        errores++;
        if (token_actual != EOF) avanzar();
    }
}

/* ================================================================
   MAIN
   ================================================================ */
int main(int argc, char *argv[]) {
    f = stdin;
    if (argc == 2) {
        f = fopen(argv[1], "rt");
        if (!f) {
            fprintf(stderr, "No se pudo abrir: %s\n", argv[1]);
            f = stdin;
        }
    }

    if (f == stdin)
        printf("Ingrese código PL/0 ... termine con Ctrl+D (Linux) / Ctrl+Z (Windows)\n\n");

    avanzar();          /* carga el primer token */
    parse_program();

    if (token_actual != EOF)
        fprintf(stderr,
            "[línea %d] Advertencia: tokens sobrantes tras el '.' (se encontró %s)\n",
            linea, nombre_token(token_actual));

    printf("\n");
    if (errores == 0)
        printf(">>> Análisis sintáctico completado SIN errores.\n");
    else
        printf(">>> Análisis sintáctico completado con %d error(es).\n", errores);

    if (f != stdin) fclose(f);
    return (errores == 0) ? 0 : 1;
}
