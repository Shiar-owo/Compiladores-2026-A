#include <iostream>
#include <string>

using namespace std;

int main() {
    string linea;

    cout << "Ingresar instruccion: ";
    getline(cin, linea);

    cout << "Letra por letra:" << endl;

    for (char c : linea) {
        cout << c << " ";
    }
    cout << endl;

    return 0;
}