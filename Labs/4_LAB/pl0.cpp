/* ============================================================
   Compiladores - Laboratorio 03
   Scanner / Analizador Léxico  ──  Lenguaje PL/0
   Gramática de referencia (Wirth, 1976):
     program    = block "." .
     block      = ["const" ident "=" number {"," ident "=" number} ";"]
                  ["var" ident {"," ident} ":" type ";"]
                  {"procedure" ident ";" block ";"} statement .
     type       = "integer" | "boolean" | "real" .
     statement  = [ident ":=" expression
                  | "call" ident
                  | "begin" statement {";" statement} "end"
                  | "if" condition "then" statement
                  | "while" condition "do" statement] .
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
#define TK_ID           256   /* identificador                  */
#define TK_NUM          257   /* número entero                  */

/* Palabras reservadas */
#define TK_PROGRAM      258   /* program  (cabecera de programa)*/
#define TK_CONST        259   /* const                          */
#define TK_VAR          260   /* var                            */
#define TK_PROCEDURE    261   /* procedure                      */
#define TK_CALL         262   /* call                           */
#define TK_BEGIN        263   /* begin                          */
#define TK_END          264   /* end                            */
#define TK_IF           265   /* if                             */
#define TK_THEN         266   /* then                           */
#define TK_WHILE        267   /* while                          */
#define TK_DO           268   /* do                             */
#define TK_ODD          269   /* odd  (operador de condición)   */

/* Operadores relacionales */
#define TK_IGUAL        270   /* =                              */
#define TK_DISTINTO     271   /* #                              */
#define TK_MENORIGUAL   272   /* <=                             */
#define TK_MAYORIGUAL   273   /* >=                             */

/* Operador de asignación (dos caracteres) */
#define TK_ASIGNACION   274   /* :=                             */

/* Tipos de datos */
#define TK_INTEGER      275   /* integer                        */
#define TK_BOOLEAN      276   /* boolean                        */
#define TK_REAL         277   /* real                           */

/* Delimitador de dos puntos simple */
#define TK_DOSPUNTOS    278   /* :   (separador ID : TIPO)      */

/* Operadores y delimitadores de un solo carácter
   Se reutiliza el valor ASCII del carácter como código de token.  */
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
#define TK_PUNTO        '.'   /* marca el fin del programa      */

/* ── Variables globales ── */
FILE *f;
char  lexema[256];

/* ── Prototipos ── */
int  scanner(void);
void mostrar(int token);
int  es_palres(void);

/* ================================================================
   TABLA DE PALABRAS RESERVADAS  (PL/0)
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
   SCANNER PRINCIPAL  (PL/0)
   ================================================================ */
int scanner(void) {
    int c, i;

    /* Saltar espacios en blanco */
    do { c = fgetc(f); } while (c != EOF && isspace(c));

    if (c == EOF) return EOF;

    /* ── Identificadores y palabras reservadas ── */
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

    /* ── Números enteros (PL/0 solo admite enteros) ── */
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

    /* ── Operadores y delimitadores ── */
    switch (c) {

        /* Operadores aritméticos */
        case '+': lexema[0]='+'; lexema[1]='\0'; return TK_MAS;
        case '-': lexema[0]='-'; lexema[1]='\0'; return TK_MENOS;
        case '*': lexema[0]='*'; lexema[1]='\0'; return TK_MULT;
        case '/': lexema[0]='/'; lexema[1]='\0'; return TK_DIV;

        /* Operador de igualdad (no asignación en PL/0) */
        case '=':
            lexema[0]='='; lexema[1]='\0';
            return TK_IGUAL;

        /* Operador "distinto de" — PL/0 usa '#' en lugar de '!=' */
        case '#':
            lexema[0]='#'; lexema[1]='\0';
            return TK_DISTINTO;

        /* Menor / MenorIgual */
        case '<':
            c = fgetc(f);
            if (c == '=') {
                strcpy(lexema, "<=");
                return TK_MENORIGUAL;
            }
            ungetc(c, f);
            lexema[0]='<'; lexema[1]='\0';
            return TK_MENOR;

        /* Mayor / MayorIgual */
        case '>':
            c = fgetc(f);
            if (c == '=') {
                strcpy(lexema, ">=");
                return TK_MAYORIGUAL;
            }
            ungetc(c, f);
            lexema[0]='>'; lexema[1]='\0';
            return TK_MAYOR;

        /* Dos puntos: ':=' asignación  o  ':' separador de tipo */
        case ':':
            c = fgetc(f);
            if (c == '=') {
                strcpy(lexema, ":=");
                return TK_ASIGNACION;
            }
            ungetc(c, f);
            lexema[0]=':'; lexema[1]='\0';
            return TK_DOSPUNTOS;

        /* Delimitadores */
        case '(':  lexema[0]='('; lexema[1]='\0'; return TK_PARI;
        case ')':  lexema[0]=')'; lexema[1]='\0'; return TK_PARD;
        case ',':  lexema[0]=','; lexema[1]='\0'; return TK_COMA;
        case ';':  lexema[0]=';'; lexema[1]='\0'; return TK_PUNTOYCOMA;
        case '.':  lexema[0]='.'; lexema[1]='\0'; return TK_PUNTO;

        default:
            fprintf(stderr, "Carácter desconocido: '%c' (ascii %d)\n", c, c);
            return scanner();   /* ignorar y continuar */
    }
}

/* ================================================================
   MOSTRAR TOKEN
   ================================================================ */
void mostrar(int token) {
    switch (token) {
        /* Tokens con lexema variable */
        case TK_ID:         printf("token = ID          [%s]\n", lexema); break;
        case TK_NUM:        printf("token = NUM         [%s]\n", lexema); break;

        /* Palabras reservadas */
        case TK_PROGRAM:    printf("token = PROGRAM     [%s]\n", lexema); break;
        case TK_CONST:      printf("token = CONST       [%s]\n", lexema); break;
        case TK_VAR:        printf("token = VAR         [%s]\n", lexema); break;
        case TK_PROCEDURE:  printf("token = PROCEDURE   [%s]\n", lexema); break;
        case TK_CALL:       printf("token = CALL        [%s]\n", lexema); break;
        case TK_BEGIN:      printf("token = BEGIN       [%s]\n", lexema); break;
        case TK_END:        printf("token = END         [%s]\n", lexema); break;
        case TK_IF:         printf("token = IF          [%s]\n", lexema); break;
        case TK_THEN:       printf("token = THEN        [%s]\n", lexema); break;
        case TK_WHILE:      printf("token = WHILE       [%s]\n", lexema); break;
        case TK_DO:         printf("token = DO          [%s]\n", lexema); break;
        case TK_ODD:        printf("token = ODD         [%s]\n", lexema); break;

        /* Tipos de datos */
        case TK_INTEGER:    printf("token = INTEGER     [%s]\n", lexema); break;
        case TK_BOOLEAN:    printf("token = BOOLEAN     [%s]\n", lexema); break;
        case TK_REAL:       printf("token = REAL        [%s]\n", lexema); break;

        /* Operadores relacionales compuestos */
        case TK_IGUAL:      printf("token = IGUAL       [%s]\n", lexema); break;
        case TK_DISTINTO:   printf("token = DISTINTO    [%s]\n", lexema); break;
        case TK_MENORIGUAL: printf("token = MENORIGUAL  [%s]\n", lexema); break;
        case TK_MAYORIGUAL: printf("token = MAYORIGUAL  [%s]\n", lexema); break;
        case TK_ASIGNACION: printf("token = ASIGNACION  [%s]\n", lexema); break;
        case TK_DOSPUNTOS:  printf("token = DOSPUNTOS   [%s]\n", lexema); break;

        /* Operadores y delimitadores de un carácter */
        case TK_MENOR:      printf("token = MENOR       [%c]\n", token); break;
        case TK_MAYOR:      printf("token = MAYOR       [%c]\n", token); break;
        case TK_MAS:        printf("token = MAS         [%c]\n", token); break;
        case TK_MENOS:      printf("token = MENOS       [%c]\n", token); break;
        case TK_MULT:       printf("token = MULT        [%c]\n", token); break;
        case TK_DIV:        printf("token = DIV         [%c]\n", token); break;
        case TK_PARI:       printf("token = PARI        [%c]\n", token); break;
        case TK_PARD:       printf("token = PARD        [%c]\n", token); break;
        case TK_COMA:       printf("token = COMA        [%c]\n", token); break;
        case TK_PUNTOYCOMA: printf("token = PUNTOYCOMA  [%c]\n", token); break;
        case TK_PUNTO:      printf("token = PUNTO       [%c]\n", token); break;

        default:            printf("token = DESCONOCIDO [%d]\n", token); break;
    }
}

/* ================================================================
   MAIN
   ================================================================ */
int main(int argc, char *argv[]) {
    int token;

    f = stdin;
    if (argc == 2) {
        f = fopen(argv[1], "rt");
        if (f == NULL) {
            fprintf(stderr, "No se pudo abrir el archivo: %s\n", argv[1]);
            f = stdin;
        }
    }

    if (f == stdin)
        printf("Ingrese código PL/0 ... termine con Ctrl+Z (Windows) o Ctrl+D (Linux)\n");

    while (1) {
        token = scanner();
        if (token == EOF) break;
        mostrar(token);
    }

    if (f != stdin) fclose(f);
    return 0;
}