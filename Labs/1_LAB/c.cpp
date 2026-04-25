#include <iostream>
#include <fstream>
#include <cctype>

using namespace std;

const string nameFile = "pseudocodigo.txt";

void procesarToken(const string& token) {
    if (token.empty()) return;

    // Verificar si es full num
    bool esNumero = true;
    for (char c : token) {
        if (!isdigit(c)) {
            esNumero = false;
            break;
        }
    }

    // Verificar si es palabra
    bool esIdentificador = true;

    // Primer char: letra o _
    if (!isalpha(token[0]) && token[0] != '_') {
        esIdentificador = false;
    } else {
        // Resto letras, números o _
        for (int i = 1; i < token.size(); i++) {
            if (!isalnum(token[i]) && token[i] != '_') {
                esIdentificador = false;
                break;
            }
        }
    }

    if (esNumero)
        cout << "numero = " << token << endl;
    else if (esIdentificador)
        cout << "palabra = " << token << endl;
    else
        cout << "simbolo = " << token << endl;
}

string simbolos = "+-*/=;(){}";

int main() {
    ifstream archivo(nameFile);
    char c;
    string token = "";

    if (!archivo) {
        cout << "Error al abrir archivo" << endl;
        return 1;
    }

    while (archivo.get(c)) {
        // sepacios, caracter blanco
        if (isspace(c)) {
            procesarToken(token);
            token = "";
        }
        // Puntuación, parentesis, llaves
        else if (simbolos.find(c) != string::npos) {
            procesarToken(token);
            token = "";

            cout << "simbolo = " << c << endl;
        }
        else {
            token += c;
        }
    }

    // ultimo token
    procesarToken(token);

    archivo.close();
    return 0;
}