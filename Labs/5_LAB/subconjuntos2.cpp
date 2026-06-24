#include <iostream>
#include <vector>
#include <set>
#include <map>
#include <queue>
#include <fstream>
#include <sstream>
#include <cstdlib>

using namespace std;

struct AFN
{
    int startState;
    set<int> finalStates;

    map<int, map<char, set<int>>> transitions;
    map<int, set<int>> epsilonTransitions;
};

struct AFD
{
    int startState;
    set<int> finalStates;

    map<int, map<char, int>> transitions;
    vector<set<int>> stateSubsets;
};

string subsetName(const set<int>& subset)
{
    stringstream ss;

    ss << "{";

    bool first = true;

    for (int state : subset)
    {
        if (!first)
            ss << ",";

        ss << state;
        first = false;
    }

    ss << "}";

    return ss.str();
}

AFN loadAFN(const string& filename, vector<char>& alphabet)
{
    AFN afn;

    ifstream file(filename);

    if (!file.is_open())
    {
        cerr << "Error: no se pudo abrir " << filename << endl;
        exit(1);
    }

    string line;
    bool readingEpsilon = false;

    while (getline(file, line))
    {
        if (line.empty())
            continue;

        if (line.find("start=") == 0)
        {
            afn.startState = stoi(line.substr(6));
        }
        else if (line.find("final=") == 0)
        {
            string finals = line.substr(6);

            stringstream ss(finals);

            while (ss.good())
            {
                string token;
                getline(ss, token, ',');

                if (!token.empty())
                    afn.finalStates.insert(stoi(token));
            }
        }
        else if (line.find("alphabet=") == 0)
        {
            string alpha = line.substr(9);

            stringstream ss(alpha);

            while (ss.good())
            {
                string token;
                getline(ss, token, ',');

                if (!token.empty())
                    alphabet.push_back(token[0]);
            }
        }
        else if (line == "epsilon:")
        {
            readingEpsilon = true;
        }
        else if (isdigit(line[0]))
        {
            stringstream ss(line);

            int from;
            ss >> from;

            if (!readingEpsilon)
            {
                char symbol;
                int to;

                ss >> symbol >> to;

                afn.transitions[from][symbol].insert(to);
            }
            else
            {
                int to;

                ss >> to;

                afn.epsilonTransitions[from].insert(to);
            }
        }
    }

    return afn;
}

set<int> epsilonClosure(const AFN& afn, const set<int>& states)
{
    set<int> closure = states;

    queue<int> q;

    for (int state : states)
        q.push(state);

    while (!q.empty())
    {
        int current = q.front();
        q.pop();

        auto it = afn.epsilonTransitions.find(current);

        if (it != afn.epsilonTransitions.end())
        {
            for (int next : it->second)
            {
                if (!closure.count(next))
                {
                    closure.insert(next);
                    q.push(next);
                }
            }
        }
    }

    return closure;
}

set<int> moveSet(
    const AFN& afn,
    const set<int>& states,
    char symbol)
{
    set<int> result;

    for (int state : states)
    {
        auto stateIt = afn.transitions.find(state);

        if (stateIt != afn.transitions.end())
        {
            auto transIt =
                stateIt->second.find(symbol);

            if (transIt != stateIt->second.end())
            {
                result.insert(
                    transIt->second.begin(),
                    transIt->second.end()
                );
            }
        }
    }

    return result;
}

AFD subsetConstruction(
    const AFN& afn,
    const vector<char>& alphabet)
{
    AFD afd;

    map<set<int>, int> subsetToId;
    queue<set<int>> unmarked;

    set<int> startSubset =
        epsilonClosure(
            afn,
            {afn.startState}
        );

    subsetToId[startSubset] = 0;
    afd.stateSubsets.push_back(startSubset);
    afd.startState = 0;

    unmarked.push(startSubset);

    while (!unmarked.empty())
    {
        set<int> T = unmarked.front();
        unmarked.pop();

        int T_id = subsetToId[T];

        for (char symbol : alphabet)
        {
            set<int> moved =
                moveSet(
                    afn,
                    T,
                    symbol
                );

            set<int> R =
                epsilonClosure(
                    afn,
                    moved
                );

            if (R.empty())
                continue;

            if (!subsetToId.count(R))
            {
                int newId =
                    afd.stateSubsets.size();

                subsetToId[R] = newId;
                afd.stateSubsets.push_back(R);

                unmarked.push(R);
            }

            afd.transitions[T_id][symbol] =
                subsetToId[R];
        }
    }

    for (size_t i = 0;
         i < afd.stateSubsets.size();
         i++)
    {
        for (int state : afd.stateSubsets[i])
        {
            if (afn.finalStates.count(state))
            {
                afd.finalStates.insert(i);
                break;
            }
        }
    }

    return afd;
}

void exportToDOT(
    const AFD& afd,
    const string& filename)
{
    ofstream file(filename);

    file << "digraph AFD {\n";
    file << "rankdir=LR;\n";

    file << "node [shape=doublecircle];\n";

    for (int finalState : afd.finalStates)
    {
        file
            << "\""
            << subsetName(
                afd.stateSubsets[finalState]
            )
            << "\";\n";
    }

    file << "\n";
    file << "node [shape=circle];\n";

    file << "start [shape=point];\n";

    file
        << "start -> \""
        << subsetName(
            afd.stateSubsets[afd.startState]
        )
        << "\";\n";

    for (auto& statePair : afd.transitions)
    {
        int from = statePair.first;

        for (auto& trans : statePair.second)
        {
            int to = trans.second;
            char symbol = trans.first;

            file
                << "\""
                << subsetName(
                    afd.stateSubsets[from]
                )
                << "\" -> \""
                << subsetName(
                    afd.stateSubsets[to]
                )
                << "\" [label=\""
                << symbol
                << "\"];\n";
        }
    }

    file << "}\n";

    file.close();
}

void renderGraph(const string& dotFile)
{
    string command =
        "dot -Tpng " +
        dotFile +
        " -o afd.png";

    int result = system(command.c_str());

    if (result != 0)
    {
        cerr
            << "Error ejecutando Graphviz.\n"
            << "Asegurate de tener instalado 'dot'.\n";
    }
}

void printAFD(const AFD& afd)
{
    cout << "\n=== AFD GENERADO ===\n\n";

    for (size_t i = 0;
         i < afd.stateSubsets.size();
         i++)
    {
        cout
            << "Estado "
            << i
            << " = "
            << subsetName(
                afd.stateSubsets[i]
            );

        if (afd.finalStates.count(i))
            cout << " (FINAL)";

        cout << endl;
    }

    cout << "\nTransiciones:\n";

    for (auto& statePair : afd.transitions)
    {
        int from = statePair.first;

        for (auto& trans : statePair.second)
        {
            cout
                << subsetName(
                    afd.stateSubsets[from]
                )
                << " --"
                << trans.first
                << "--> "
                << subsetName(
                    afd.stateSubsets[
                        trans.second
                    ]
                )
                << endl;
        }
    }
}

int main()
{
    vector<char> alphabet;

    AFN afn =
        loadAFN(
            "afn.txt",
            alphabet
        );

    AFD afd =
        subsetConstruction(
            afn,
            alphabet
        );

    printAFD(afd);

    exportToDOT(
        afd,
        "afd.dot"
    );

    renderGraph(
        "afd.dot"
    );

    cout
        << "\nArchivo DOT generado: afd.dot\n"
        << "Imagen generada: afd.png\n";

    return 0;
}
