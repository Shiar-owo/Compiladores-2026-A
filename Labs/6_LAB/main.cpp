#include <iostream>
#include <vector>
#include <string>
#include <map>
#include <set>
#include <iomanip>
#include <algorithm>
#include <fstream>

using namespace std;

map<string, set<string>> compute_first(map<string, vector<vector<string>>>& gramatica) {
    map<string, set<string>> FIRST;
    bool changed = true;
    while (changed) {
        changed = false;
        for (auto& regla : gramatica) {
            string A = regla.first;
            for (auto& prod : regla.second) {
                if (prod.size() == 1 && prod[0] == "e") {
                    if (FIRST[A].insert("e").second) changed = true;
                } else {
                    bool all_epsilon = true;
                    for (const string& simbolo : prod) {
                        if (gramatica.find(simbolo) != gramatica.end()) {
                            for (const string& t : FIRST[simbolo]) {
                                if (t != "e" && FIRST[A].insert(t).second) changed = true;
                            }
                            if (FIRST[simbolo].find("e") == FIRST[simbolo].end()) {
                                all_epsilon = false;
                                break;
                            }
                        } else {
                            if (FIRST[A].insert(simbolo).second) changed = true;
                            all_epsilon = false;
                            break;
                        }
                    }
                    if (all_epsilon && FIRST[A].insert("e").second) changed = true;
                }
            }
        }
    }
    return FIRST;
}

map<string, set<string>> compute_follow(map<string, vector<vector<string>>>& gramatica, string start, map<string, set<string>>& FIRST) {
    map<string, set<string>> FOLLOW;
    FOLLOW[start].insert("$");
    bool changed = true;
    while (changed) {
        changed = false;
        for (auto& regla : gramatica) {
            string A = regla.first;
            for (auto& prod : regla.second) {
                for (size_t i = 0; i < prod.size(); ++i) {
                    if (gramatica.find(prod[i]) != gramatica.end()) {
                        string B = prod[i];
                        set<string> FIRST_beta;
                        bool beta_epsilon = true;
                        for (size_t j = i + 1; j < prod.size(); ++j) {
                            if (gramatica.find(prod[j]) != gramatica.end()) {
                                for (const string& t : FIRST[prod[j]]) {
                                    if (t != "e") FIRST_beta.insert(t);
                                }
                                if (FIRST[prod[j]].find("e") == FIRST[prod[j]].end()) {
                                    beta_epsilon = false;
                                    break;
                                }
                            } else {
                                FIRST_beta.insert(prod[j]);
                                beta_epsilon = false;
                                break;
                            }
                        }
                        for (const string& t : FIRST_beta) {
                            if (FOLLOW[B].insert(t).second) changed = true;
                        }
                        if (beta_epsilon) {
                            for (const string& t : FOLLOW[A]) {
                                if (FOLLOW[B].insert(t).second) changed = true;
                            }
                        }
                    }
                }
            }
        }
    }
    return FOLLOW;
}


string vec_a_str(const vector<string>& v, size_t desde = 0) {
    string s = "";
    for (size_t i = desde; i < v.size(); ++i) s += v[i];
    return s;
}

void imprimir_fila_archivo(ofstream& file, const vector<string>& pila, const string& entrada, const string& salida) {
    file << left << setw(20) << vec_a_str(pila) << " | " << left << setw(20) << entrada << " | " << salida << endl;
}

void write_sets_to_file(map<string, set<string>>& FIRST, map<string, set<string>>& FOLLOW, const string& filename) {
    ofstream file(filename);
    file << "==============================================" << endl;
    file << "       CONJUNTOS FIRST Y FOLLOW               " << endl;
    file << "==============================================" << endl << endl;

    file << ">>> FIRST <<<" << endl;
    for (const auto& par : FIRST) {
        file << "FIRST(" << par.first << ") = { ";
        bool first = true;
        for (const string& s : par.second) {
            if (!first) file << ", ";
            file << s;
            first = false;
        }
        file << " }" << endl;
    }
    file << endl;

    file << ">>> FOLLOW <<<" << endl;
    for (const auto& par : FOLLOW) {
        file << "FOLLOW(" << par.first << ") = { ";
        bool first = true;
        for (const string& s : par.second) {
            if (!first) file << ", ";
            file << s;
            first = false;
        }
        file << " }" << endl;
    }
    file << endl;

    file << "==============================================" << endl;
    file << "       TABLA DE ANALISIS M                    " << endl;
    file << "==============================================" << endl << endl;

    string terminales[] = {"id", "+", "*", "(", ")", "$"};
    string no_terminales[] = {"E", "E'", "T", "T'", "F"};

    map<pair<string, string>, vector<string>> M;
    M[{"E", "id"}] = {"T", "E'"};   M[{"E", "("}]  = {"T", "E'"};
    M[{"E'", "+"}] = {"+", "T", "E'"}; M[{"E'", ")"}] = {"e"}; M[{"E'", "$"}] = {"e"};
    M[{"T", "id"}] = {"F", "T'"};   M[{"T", "("}]  = {"F", "T'"};
    M[{"T'", "+"}] = {"e"};         M[{"T'", "*"}] = {"*", "F", "T'"}; M[{"T'", ")"}] = {"e"}; M[{"T'", "$"}] = {"e"};
    M[{"F", "id"}] = {"id"};        M[{"F", "("}]  = {"(", "E", ")"};

    file << left << setw(6) << "NT";
    for (const string& t : terminales) file << " | " << left << setw(14) << t;
    file << endl << string(6 + 17 * 6, '-') << endl;

    for (const string& nt : no_terminales) {
        file << left << setw(6) << nt;
        for (const string& t : terminales) {
            if (M.find({nt, t}) != M.end()) {
                string prod = nt + " -> ";
                for (size_t i = 0; i < M[{nt, t}].size(); ++i) {
                    if (i > 0) prod += " ";
                    prod += M[{nt, t}][i];
                }
                file << " | " << left << setw(14) << prod;
            } else {
                file << " | " << left << setw(14) << "";
            }
        }
        file << endl;
    }
    file << endl;

    file << "==============================================" << endl;
    file << "       ESTRUCTURA DE LA PILA                   " << endl;
    file << "==============================================" << endl << endl;
    file << "La pila es una estructura LIFO (Last In, First Out)." << endl;
    file << "Se inicializa con: $ E (fondo = $, tope = E)" << endl;
    file << "Simbolos: terminales y no terminales de la gramatica." << endl;
    file << "Algoritmo:" << endl;
    file << "  1. Sacar tope X de la pila." << endl;
    file << "  2. Si X es terminal: comparar con entrada, si coincide avanzar." << endl;
    file << "  3. Si X es no terminal: buscar M[X, a] y reemplazar X por la produccion." << endl;
    file << "  4. Repetir hasta vaciar la pila o encontrar error." << endl;
    file << endl;

    set<string> nts = {"E", "E'", "T", "T'", "F"};

    auto simular = [&](const string& titulo, const vector<string>& cadena) {
        file << "==============================================" << endl;
        file << "       " << titulo << endl;
        file << "==============================================" << endl << endl;
        file << left << setw(20) << "PILA" << " | " << left << setw(20) << "ENTRADA" << " | " << "SALIDA" << endl;
        file << string(62, '-') << endl;

        vector<string> pila = {"$", "E"};
        vector<string> entrada = cadena;
        size_t ip = 0;

        file << left << setw(20) << vec_a_str(pila) << " | " << left << setw(20) << vec_a_str(entrada, ip) << " | " << "" << endl;

        bool error = false;
        while (!pila.empty()) {
            string X = pila.back();
            string a = entrada[ip];

            if (X == "$" && a == "$") break;

            if (nts.find(X) == nts.end()) {
                if (X == a) {
                    pila.pop_back();
                    ip++;
                    imprimir_fila_archivo(file, pila, vec_a_str(entrada, ip), "");
                } else {
                    file << "[ERROR]: Se esperaba '" << X << "' pero se encontro '" << a << "'" << endl;
                    error = true;
                    break;
                }
            } else {
                if (M.find({X, a}) == M.end()) {
                    file << "[ERROR]: No existe M[" << X << ", " << a << "]" << endl;
                    error = true;
                    break;
                }

                vector<string> produccion = M[{X, a}];
                pila.pop_back();

                string str_salida = X + " -> ";
                if (produccion.size() == 1 && produccion[0] == "e") {
                    str_salida += "e";
                } else {
                    for (int i = produccion.size() - 1; i >= 0; --i)
                        pila.push_back(produccion[i]);
                    for (size_t i = 0; i < produccion.size(); ++i) {
                        if (i > 0) str_salida += " ";
                        str_salida += produccion[i];
                    }
                }

                imprimir_fila_archivo(file, pila, vec_a_str(entrada, ip), str_salida);
            }
        }

        file << string(62, '-') << endl;
        file << "RESULTADO: Cadena " << (error ? "RECHAZADA" : "ACEPTADA") << endl << endl;
    };

    simular("CADENA 1: id+id*id$", {"id", "+", "id", "*", "id", "$"});
    simular("CADENA 2: (id+id)*id$", {"(", "id", "+", "id", ")", "*", "id", "$"});

    file.close();
    cout << ">> Conjuntos FIRST, FOLLOW, tabla M, pila y cadenas guardados en '" << filename << "'" << endl;
}

void imprimir_fila(const string& pila, const string& entrada, const string& salida) {
    cout << left << setw(14) << pila 
         << " | " << left << setw(14) << entrada 
         << " | " << salida << endl;
}

// Tokenizador mejorado: maneja espacios, valida el alfabeto y auto-inserta '$'
vector<string> tokenizar_dinamico(string entrada, bool &error_lexico) {
    vector<string> tokens;
    set<char> validos = {'+', '*', '(', ')', '$'};
    
    // Eliminamos espacios iniciales/finales extras
    entrada.erase(remove(entrada.begin(), entrada.end(), ' '), entrada.end());
    entrada.erase(remove(entrada.begin(), entrada.end(), '\t'), entrada.end());

    // Auto-insertar el símbolo de fin de cadena '$' si el usuario lo olvidó
    if (!entrada.empty() && entrada.back() != '$') {
        entrada += '$';
    }

    for (size_t i = 0; i < entrada.length(); ) {
        if (i + 1 < entrada.length() && entrada.substr(i, 2) == "id") {
            tokens.push_back("id");
            i += 2;
        } else if (validos.count(entrada[i])) {
            tokens.push_back(string(1, entrada[i]));
            i++;
        } else {
            cout << "\n[ERROR LEXICO]: El caracter '" << entrada[i] << "' no pertenece al alfabeto de la gramatica.\n";
            error_lexico = true;
            break;
        }
    }
    return tokens;
}

int main() {
    set<string> no_terminales = {"E", "E'", "T", "T'", "F"};
    map<pair<string, string>, vector<string>> M;

    // Tabla de Análisis M de la Gramática LL(1)
    M[{"E", "id"}] = {"T", "E'"};
    M[{"E", "("}]  = {"T", "E'"};

    M[{"E'", "+"}] = {"+", "T", "E'"};
    M[{"E'", ")"}] = {"e"};
    M[{"E'", "$"}] = {"e"};

    M[{"T", "id"}] = {"F", "T'"};
    M[{"T", "("}]  = {"F", "T'"};

    M[{"T'", "+"}] = {"e"};
    M[{"T'", "*"}] = {"*", "F", "T'"};
    M[{"T'", ")"}] = {"e"};
    M[{"T'", "$"}] = {"e"};

    M[{"F", "id"}] = {"id"};
    M[{"F", "("}]  = {"(", "E", ")"};

    // --- CÁLCULO DE FIRST Y FOLLOW ---
    map<string, vector<vector<string>>> gramatica = {
        {"E",  {{"T", "E'"} }},
        {"E'", {{"+", "T", "E'"}, {"e"}}},
        {"T",  {{"F", "T'"} }},
        {"T'", {{"*", "F", "T'"}, {"e"}}},
        {"F",  {{"id"}, {"(", "E", ")"}}}
    };

    map<string, set<string>> FIRST = compute_first(gramatica);
    map<string, set<string>> FOLLOW = compute_follow(gramatica, "E", FIRST);
    write_sets_to_file(FIRST, FOLLOW, "conjuntos.txt");

    // --- TABLA M EN CONSOLA ---
    string terminales[] = {"id", "+", "*", "(", ")", "$"};
    string no_terms[] = {"E", "E'", "T", "T'", "F"};

    cout << "\n==============================================" << endl;
    cout << "       TABLA DE ANALISIS M" << endl;
    cout << "==============================================" << endl << endl;

    cout << left << setw(6) << "NT";
    for (const string& t : terminales) cout << " | " << left << setw(14) << t;
    cout << endl << string(6 + 17 * 6, '-') << endl;

    for (const string& nt : no_terms) {
        cout << left << setw(6) << nt;
        for (const string& t : terminales) {
            if (M.find({nt, t}) != M.end()) {
                string prod = nt + " -> ";
                for (size_t i = 0; i < M[{nt, t}].size(); ++i) {
                    if (i > 0) prod += " ";
                    prod += M[{nt, t}][i];
                }
                cout << " | " << left << setw(14) << prod;
            } else {
                cout << " | " << left << setw(14) << "";
            }
        }
        cout << endl;
    }
    cout << endl;

    // --- CAPTURA DINÁMICA DE LA CADENA ---
    string cadena_input;
    cout << "========================================================\n";
    cout << "       ANALIZADOR SINTACTICO PREDICTIVO LL(1)           \n";
    cout << "========================================================\n";
    cout << "Ingresa una operacion (ej. (id+id)*id ) [Enter para prueba default]: ";
    
    getline(cin, cadena_input);

    if (cadena_input.empty()) {
        cadena_input = "id+id*id$";
        cout << ">> Usando cadena por defecto: " << cadena_input << "\n";
    }

    bool error_lexico = false;
    vector<string> entrada = tokenizar_dinamico(cadena_input, error_lexico);

    if (error_lexico) return 1;

    size_t ip = 0;
    vector<string> pila = {"$", "E"};

    cout << "\n" << string(48, '-') << "\n";
    imprimir_fila("PILA", "ENTRADA", "SALIDA");
    cout << string(48, '-') << "\n";

    imprimir_fila(vec_a_str(pila), vec_a_str(entrada, ip), "");

    bool error = false;

    while (!pila.empty()) {
        string X = pila.back();
        string a = entrada[ip];

        if (X == "$" && a == "$") break;

        if (no_terminales.find(X) == no_terminales.end()) {
            if (X == a) {
                pila.pop_back();
                ip++;
                imprimir_fila(vec_a_str(pila), vec_a_str(entrada, ip), "");
            } else {
                cout << "\n[ERROR SINTACTICO]: Se esperaba el terminal '" << X << "' pero se encontro '" << a << "'\n";
                error = true;
                break;
            }
        } else {
            if (M.find({X, a}) == M.end()) {
                cout << "\n[ERROR SINTACTICO]: No existe transicion en la tabla M[" << X << ", " << a << "]\n";
                error = true;
                break;
            }

            vector<string> produccion = M[{X, a}];
            pila.pop_back();

            string str_salida = X + " -> ";

            if (produccion.size() == 1 && produccion[0] == "e") {
                str_salida += "e";
            } else {
                for (int i = produccion.size() - 1; i >= 0; --i) {
                    pila.push_back(produccion[i]);
                }
                for (size_t i = 0; i < produccion.size(); ++i) {
                    if (i > 0) str_salida += " ";
                    str_salida += produccion[i];
                }
            }

            imprimir_fila(vec_a_str(pila), vec_a_str(entrada, ip), str_salida);
        }
    }

    cout << string(48, '-') << "\n";
    if (!error) {
        cout << ">> RESULTADO: Cadena ACEPTADA EXITOSAMENTE <<\n";
    } else {
        cout << ">> RESULTADO: Cadena RECHAZADA <<\n";
    }

    return 0;
}