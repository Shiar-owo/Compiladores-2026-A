#include <iostream>
#include <fstream>

using namespace std;

const string nameFile = "pseudocodigo.txt";

int main() {
    ifstream archivo(nameFile);
    char c;

    if (!archivo) {
        cout << "ERROR ARCHIVO" << endl;
        return 1;
    }

    cout << "Archivo caracter por caracter:" << endl;

    while (archivo.get(c)) {
        cout << c << " ";
    }
    cout << endl;

    archivo.close();
    return 0;
}