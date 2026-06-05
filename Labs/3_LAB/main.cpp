/* ============================================================
   Compiladores - Laboratorio 03
   Scanner / Analizador Léxico
   ============================================================ */

#include <stdio.h>
#include <ctype.h>
#include <string.h>
#include <stdlib.h>

/* ── Códigos de token ── */
#define TK_ID           256
#define TK_NUM          257
#define TK_MAYORIGUAL   258   /* >= */
#define TK_MENORIGUAL   259   /* <= */
#define TK_IGUAL        260   /* == */
#define TK_DISTINTO     261   /* != */
#define TK_WHILE        262
#define TK_IF           263
#define TK_FOR          264
#define TK_DO           265
#define TK_INT          266
#define TK_FLOAT        267
#define TK_CHAR         268
#define TK_RETURN       269
#define TK_VOID         270
#define TK_ELSE         271
#define TK_ASIGNACION   272   /* = (simple) */

#define TK_MAYOR        '>'
#define TK_MENOR        '<'
#define TK_MAS          '+'
#define TK_MENOS        '-'
#define TK_MULT         '*'
#define TK_DIV          '/'
#define TK_PARI         '('
#define TK_PARD         ')'
#define TK_CORI         '['
#define TK_CORD         ']'
#define TK_LLAVI        '{'
#define TK_LLAVD        '}'
#define TK_COMA         ','
#define TK_PUNTOYCOMA   ';'

/* ── Variables globales ── */
FILE *f;
char lexema[256];

/* ── Prototípos ── */
int  scanner(void);
void mostrar(int token);
int  es_palres(void);
void ignorar_comentario_linea(void);
void ignorar_comentario_bloque(void);

/* ================================================================
   TABLA DE PALABRAS RESERVADAS
   ================================================================ */
typedef struct { const char *palabra; int token; } PalRes;

static PalRes palabras_reservadas[] = {
    {"while",  TK_WHILE},
    {"if",     TK_IF},
    {"for",    TK_FOR},
    {"do",     TK_DO},
    {"int",    TK_INT},
    {"float",  TK_FLOAT},
    {"char",   TK_CHAR},
    {"return", TK_RETURN},
    {"void",   TK_VOID},
    {"else",   TK_ELSE},
    {NULL, -1}
};

int es_palres(void) {
    for (int i = 0; palabras_reservadas[i].palabra != NULL; i++)
        if (strcmp(lexema, palabras_reservadas[i].palabra) == 0)
            return palabras_reservadas[i].token;
    return -1;
}

/* ================================================================
   MANEJO DE COMENTARIOS
   ================================================================ */
void ignorar_comentario_linea(void) {
    int c;
    while ((c = fgetc(f)) != EOF && c != '\n');
}

void ignorar_comentario_bloque(void) {
    int c, prev = 0;
    while ((c = fgetc(f)) != EOF) {
        if (prev == '*' && c == '/') return;
        prev = c;
    }
    fprintf(stderr, "Error: comentario de bloque sin cerrar\n");
}

/* ================================================================
   SCANNER PRINCIPAL
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

    /* ── Números enteros (y opcionalmente decimales) ── */
    if (isdigit(c)) {
        i = 0;
        do {
            lexema[i++] = (char)c;
            c = fgetc(f);
        } while (isdigit(c));

        /* Parte decimal */
        if (c == '.') {
            lexema[i++] = (char)c;
            c = fgetc(f);
            while (isdigit(c)) {
                lexema[i++] = (char)c;
                c = fgetc(f);
            }
        }
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

        /* División o comentarios */
        case '/':
            c = fgetc(f);
            if (c == '/') {                     /* comentario en línea */
                ignorar_comentario_linea();
                return scanner();               /* recursión: próximo token */
            }
            if (c == '*') {                     /* comentario en bloque */
                ignorar_comentario_bloque();
                return scanner();
            }
            ungetc(c, f);
            lexema[0]='/'; lexema[1]='\0';
            return TK_DIV;

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

        /* Igual / Asignación */
        case '=':
            c = fgetc(f);
            if (c == '=') {
                strcpy(lexema, "==");
                return TK_IGUAL;
            }
            ungetc(c, f);
            lexema[0]='='; lexema[1]='\0';
            return TK_ASIGNACION;

        /* Distinto */
        case '!':
            c = fgetc(f);
            if (c == '=') {
                strcpy(lexema, "!=");
                return TK_DISTINTO;
            }
            ungetc(c, f);
            fprintf(stderr, "Caracter inesperado: !\n");
            return scanner();

        /* Delimitadores de un carácter */
        case '(':  lexema[0]='('; lexema[1]='\0'; return TK_PARI;
        case ')':  lexema[0]=')'; lexema[1]='\0'; return TK_PARD;
        case '[':  lexema[0]='['; lexema[1]='\0'; return TK_CORI;
        case ']':  lexema[0]=']'; lexema[1]='\0'; return TK_CORD;
        case '{':  lexema[0]='{'; lexema[1]='\0'; return TK_LLAVI;
        case '}':  lexema[0]='}'; lexema[1]='\0'; return TK_LLAVD;
        case ',':  lexema[0]=','; lexema[1]='\0'; return TK_COMA;
        case ';':  lexema[0]=';'; lexema[1]='\0'; return TK_PUNTOYCOMA;

        default:
            fprintf(stderr, "Caracter desconocido: '%c' (ascii %d)\n", c, c);
            return scanner();   /* ignorar y continuar */
    }
}

/* ================================================================
   MOSTRAR TOKEN
   ================================================================ */
void mostrar(int token) {
    switch (token) {
        case TK_ID:           printf("token = ID           [%s]\n", lexema); break;
        case TK_NUM:          printf("token = NUM          [%s]\n", lexema); break;
        case TK_WHILE:        printf("token = WHILE        [%s]\n", lexema); break;
        case TK_IF:           printf("token = IF           [%s]\n", lexema); break;
        case TK_FOR:          printf("token = FOR          [%s]\n", lexema); break;
        case TK_DO:           printf("token = DO           [%s]\n", lexema); break;
        case TK_INT:          printf("token = INT          [%s]\n", lexema); break;
        case TK_FLOAT:        printf("token = FLOAT        [%s]\n", lexema); break;
        case TK_CHAR:         printf("token = CHAR         [%s]\n", lexema); break;
        case TK_RETURN:       printf("token = RETURN       [%s]\n", lexema); break;
        case TK_VOID:         printf("token = VOID         [%s]\n", lexema); break;
        case TK_ELSE:         printf("token = ELSE         [%s]\n", lexema); break;
        case TK_MAYORIGUAL:   printf("token = MAYORIGUAL   [%s]\n", lexema); break;
        case TK_MENORIGUAL:   printf("token = MENORIGUAL   [%s]\n", lexema); break;
        case TK_IGUAL:        printf("token = IGUAL        [%s]\n", lexema); break;
        case TK_DISTINTO:     printf("token = DISTINTO     [%s]\n", lexema); break;
        case TK_ASIGNACION:   printf("token = ASIGNACION   [%s]\n", lexema); break;
        case TK_MAYOR:        printf("token = MAYOR        [%c]\n", token);  break;
        case TK_MENOR:        printf("token = MENOR        [%c]\n", token);  break;
        case TK_MAS:          printf("token = MAS          [%c]\n", token);  break;
        case TK_MENOS:        printf("token = MENOS        [%c]\n", token);  break;
        case TK_MULT:         printf("token = MULT         [%c]\n", token);  break;
        case TK_DIV:          printf("token = DIV          [%c]\n", token);  break;
        case TK_PARI:         printf("token = PARI         [%c]\n", token);  break;
        case TK_PARD:         printf("token = PARD         [%c]\n", token);  break;
        case TK_CORI:         printf("token = CORI         [%c]\n", token);  break;
        case TK_CORD:         printf("token = CORD         [%c]\n", token);  break;
        case TK_LLAVI:        printf("token = LLAVI        [%c]\n", token);  break;
        case TK_LLAVD:        printf("token = LLAVD        [%c]\n", token);  break;
        case TK_COMA:         printf("token = COMA         [%c]\n", token);  break;
        case TK_PUNTOYCOMA:   printf("token = PUNTOYCOMA   [%c]\n", token);  break;
        default:              printf("token = DESCONOCIDO  [%d]\n", token);  break;
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
        printf("Ingrese texto ... termine con Ctrl+Z (Windows) o Ctrl+D (Linux)\n");

    while (1) {
        token = scanner();
        if (token == EOF) break;
        mostrar(token);
    }

    if (f != stdin) fclose(f);
    return 0;
}