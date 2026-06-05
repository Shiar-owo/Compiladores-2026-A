/* Este es un comentario
   de bloque que debe ser ignorado */

int main(void) {
    int x = 10;
    float y = 3.14;
    char letra;

    /* Verificar condiciones */
    if (x >= 5) {
        x = x + 1;
    } else {
        x = x - 2;
    }

    while (x != 0) {
        if (x == 20) 
            return x;
    }

    for (int i = 0; i <= 100; i = i + 1) {
        y = y / 2;
    }

    // Operadores de comparacion
    int a = 3;
    int b = 7;
    if (a < b) {
        a = b;
    }
}