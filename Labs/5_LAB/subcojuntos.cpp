#include <iostream>
#include <iomanip>
#include <vector>
#include <set>
#include <map>
#include <queue>
#include <fstream>
#include <sstream>
#include <cstdlib>
#include <algorithm>

using namespace std;

// ─────────────────────────────────────────
//  Estructuras
// ─────────────────────────────────────────

struct NFA
{
    int startState;
    set<int> finalStates;
    map<int, map<char, set<int>>> transitions;
    map<int, set<int>> epsilonTransitions;
};

struct DFA
{
    int startState;
    set<int> finalStates;
    map<int, map<char, int>> transitions;
    vector<set<int>> stateSubsets;
};

// ─────────────────────────────────────────
//  Utilidades
// ─────────────────────────────────────────

string subsetName(const set<int>& subset)
{
    if (subset.empty()) return "∅";

    stringstream ss;
    ss << "{";
    bool first = true;
    for (int s : subset)
    {
        if (!first) ss << ",";
        ss << s;
        first = false;
    }
    ss << "}";
    return ss.str();
}

// Etiqueta corta: D0, D1, D2... para usar en la tabla
string stateLabel(int id)
{
    return "D" + to_string(id);
}

// ─────────────────────────────────────────
//  Carga del NFA
// ─────────────────────────────────────────

NFA loadNFA(const string& filename, vector<char>& alphabet)
{
    NFA nfa;
    ifstream file(filename);

    if (!file.is_open())
    {
        cerr << "Error: no se pudo abrir " << filename << "\n";
        exit(1);
    }

    string line;
    bool readingEpsilon = false;

    while (getline(file, line))
    {
        if (line.empty()) continue;

        if (line.find("start=") == 0)
        {
            nfa.startState = stoi(line.substr(6));
        }
        else if (line.find("final=") == 0)
        {
            stringstream ss(line.substr(6));
            string token;
            while (getline(ss, token, ','))
                if (!token.empty())
                    nfa.finalStates.insert(stoi(token));
        }
        else if (line.find("alphabet=") == 0)
        {
            stringstream ss(line.substr(9));
            string token;
            while (getline(ss, token, ','))
                if (!token.empty())
                    alphabet.push_back(token[0]);
        }
        else if (line == "epsilon:")
        {
            readingEpsilon = true;
        }
        else if (!line.empty() && isdigit(line[0]))
        {
            stringstream ss(line);
            int from;
            ss >> from;

            if (!readingEpsilon)
            {
                char symbol;
                int to;
                ss >> symbol >> to;
                nfa.transitions[from][symbol].insert(to);
            }
            else
            {
                int to;
                ss >> to;
                nfa.epsilonTransitions[from].insert(to);
            }
        }
    }

    return nfa;
}

// ─────────────────────────────────────────
//  Algoritmo central
// ─────────────────────────────────────────

set<int> epsilonClosure(const NFA& nfa, const set<int>& states)
{
    set<int> closure = states;
    queue<int> q;

    for (int s : states) q.push(s);

    while (!q.empty())
    {
        int cur = q.front(); q.pop();

        auto it = nfa.epsilonTransitions.find(cur);
        if (it == nfa.epsilonTransitions.end()) continue;

        for (int next : it->second)
        {
            if (!closure.count(next))
            {
                closure.insert(next);
                q.push(next);
            }
        }
    }

    return closure;
}

set<int> moveSet(const NFA& nfa, const set<int>& states, char symbol)
{
    set<int> result;

    for (int s : states)
    {
        auto stIt = nfa.transitions.find(s);
        if (stIt == nfa.transitions.end()) continue;

        auto trIt = stIt->second.find(symbol);
        if (trIt == stIt->second.end()) continue;

        result.insert(trIt->second.begin(), trIt->second.end());
    }

    return result;
}

DFA subsetConstruction(const NFA& nfa, const vector<char>& alphabet)
{
    DFA dfa;
    map<set<int>, int> subsetToId;
    queue<set<int>> pending;

    set<int> startSubset = epsilonClosure(nfa, {nfa.startState});

    subsetToId[startSubset] = 0;
    dfa.stateSubsets.push_back(startSubset);
    dfa.startState = 0;
    pending.push(startSubset);

    while (!pending.empty())
    {
        set<int> T = pending.front(); pending.pop();
        int T_id = subsetToId[T];

        for (char sym : alphabet)
        {
            set<int> R = epsilonClosure(nfa, moveSet(nfa, T, sym));

            if (R.empty()) continue;

            if (!subsetToId.count(R))
            {
                int newId = dfa.stateSubsets.size();
                subsetToId[R] = newId;
                dfa.stateSubsets.push_back(R);
                pending.push(R);
            }

            dfa.transitions[T_id][sym] = subsetToId[R];
        }
    }

    for (size_t i = 0; i < dfa.stateSubsets.size(); i++)
        for (int s : dfa.stateSubsets[i])
            if (nfa.finalStates.count(s))
            {
                dfa.finalStates.insert(i);
                break;
            }

    return dfa;
}

// ─────────────────────────────────────────
//  Salida: tabla de transiciones
// ─────────────────────────────────────────

void printTransitionTable(const DFA& dfa, const vector<char>& alphabet)
{
    // Ancho de columna de estado (la más larga de los nombres de subconjunto)
    int nameW = 6;
    for (size_t i = 0; i < dfa.stateSubsets.size(); i++)
    {
        int len = stateLabel(i).size() + 2 + subsetName(dfa.stateSubsets[i]).size();
        nameW = max(nameW, len + 2);
    }

    int cellW = 10;

    // ── Encabezado ──────────────────────────────────────
    string sep(nameW + 3 + alphabet.size() * (cellW + 3), '-');

    cout << "\n+" << string(sep.size() - 2, '-') << "+\n";
    cout << "|  TABLA DE TRANSICIONES DEL DFA";
    cout << string(sep.size() - 34, ' ') << "|\n";
    cout << "+" << string(sep.size() - 2, '-') << "+\n\n";

    // Fila de encabezado de columnas
    cout << "  " << setw(nameW) << left << "Estado";
    cout << "  │";
    for (char c : alphabet)
        cout << "  " << setw(cellW) << left << string(1, c) << "│";
    cout << "\n";

    // Separador
    cout << "  " << string(nameW, '-') << "--┼";
    for (size_t i = 0; i < alphabet.size(); i++)
        cout << string(cellW + 2, '-') << "┼";
    cout << "\n";

    // ── Filas ────────────────────────────────────────────
    for (size_t i = 0; i < dfa.stateSubsets.size(); i++)
    {
        bool isStart = ((int)i == dfa.startState);
        bool isFinal = dfa.finalStates.count(i);

        // Prefijo visual: → inicial, * final, ✦ ambos
        string prefix = "  ";
        if      (isStart && isFinal) prefix = "✦ ";
        else if (isStart)            prefix = "→ ";
        else if (isFinal)            prefix = "* ";

        string label = stateLabel(i) + " " + subsetName(dfa.stateSubsets[i]);
        cout << prefix << setw(nameW) << left << label << "│";

        for (char sym : alphabet)
        {
            auto stIt = dfa.transitions.find(i);
            if (stIt != dfa.transitions.end())
            {
                auto trIt = stIt->second.find(sym);
                if (trIt != stIt->second.end())
                {
                    string dest = stateLabel(trIt->second);
                    cout << "  " << setw(cellW) << left << dest << "│";
                    continue;
                }
            }
            cout << "  " << setw(cellW) << left << "—" << "│";
        }
        cout << "\n";
    }

    cout << "\n";
    cout << "  → estado inicial    * estado final    ✦ inicial y final\n\n";
}

// ─────────────────────────────────────────
//  Exportar DOT con layout circular
// ─────────────────────────────────────────

void exportToDOT(const DFA& dfa, const string& filename)
{
    ofstream file(filename);

    file << "digraph DFA {\n";

    // Layout horizontal izquierda -> derecha
    file << "    rankdir=LR;\n";
    file << "    splines=spline;\n";
    file << "    nodesep=0.9;\n";
    file << "    ranksep=1.4;\n";
    file << "    pad=0.4;\n";

    // Estilo global de nodos
    file << "    node [fontname=\"Helvetica\" fontsize=11];\n";
    file << "    edge [fontname=\"Helvetica\" fontsize=10];\n";

    // Estados finales: doble círculo, relleno verde claro
    file << "\n    // Estados finales\n";
    file << "    node [shape=doublecircle style=filled fillcolor=\"#c8f0d0\" color=\"#2a7a3b\"];\n";
    for (int f : dfa.finalStates)
        file << "    \"" << stateLabel(f) << "\";\n";

    // Estado inicial + final
    if (dfa.finalStates.count(dfa.startState))
    {
        file << "    \"" << stateLabel(dfa.startState)
             << "\" [fillcolor=\"#b0d8f5\" color=\"#1a5a8a\"];\n";
    }

    // Estados normales: círculo, relleno azul claro
    file << "\n    // Estados normales\n";
    file << "    node [shape=circle style=filled fillcolor=\"#ddeeff\" color=\"#336699\"];\n";
    for (size_t i = 0; i < dfa.stateSubsets.size(); i++)
        if (!dfa.finalStates.count(i))
            file << "    \"" << stateLabel(i) << "\";\n";

    // Etiquetas internas (subconjunto como tooltip / xlabel)
    file << "\n    // Etiquetas con subconjunto NFA\n";
    for (size_t i = 0; i < dfa.stateSubsets.size(); i++)
    {
        file << "    \"" << stateLabel(i) << "\""
             << " [label=\"" << stateLabel(i) << "\\n"
             << subsetName(dfa.stateSubsets[i]) << "\""
             << " tooltip=\"" << subsetName(dfa.stateSubsets[i]) << "\"];\n";
    }

    // Punto de entrada invisible
    file << "\n    // Flecha de inicio\n";
    file << "    __start [shape=point width=0.2 style=filled fillcolor=black];\n";
    file << "    __start -> \"" << stateLabel(dfa.startState) << "\";\n";

    // Agrupar aristas con mismo origen/destino (etiqueta combinada)
    map<pair<int,int>, vector<char>> edgeLabels;
    for (auto& [from, symMap] : dfa.transitions)
        for (auto& [sym, to] : symMap)
            edgeLabels[{from, to}].push_back(sym);

    file << "\n    // Transiciones\n";
    for (auto& [edge, syms] : edgeLabels)
    {
        auto [from, to] = edge;
        string label;
        for (size_t i = 0; i < syms.size(); i++)
        {
            if (i) label += ", ";
            label += syms[i];
        }

        // Self-loops con estilo diferente
        string extra = (from == to) ? " style=dashed" : "";
        file << "    \"" << stateLabel(from) << "\" -> \""
             << stateLabel(to) << "\""
             << " [label=\"" << label << "\"" << extra << "];\n";
    }

    file << "}\n";
    file.close();
}

// ─────────────────────────────────────────
//  Render
// ─────────────────────────────────────────

void renderGraph(const string& dotFile)
{
    // dot con rankdir=LR produce el layout horizontal
    string command = "dot -Tpng " + dotFile + " -o dfa.png";
    int result = system(command.c_str());

    if (result != 0)
        cerr << "Error: instala Graphviz (dot).\n";
}

// ─────────────────────────────────────────
//  Main
// ─────────────────────────────────────────

int main()
{
    vector<char> alphabet;
    NFA nfa = loadNFA("nfa.txt", alphabet);
    DFA dfa = subsetConstruction(nfa, alphabet);

    printTransitionTable(dfa, alphabet);
    exportToDOT(dfa, "dfa.dot");
    renderGraph("dfa.dot");

    cout << "Archivos generados: dfa.dot  dfa.png\n";
    return 0;
}