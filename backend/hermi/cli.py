"""Hermi CLI — Interactive command-line agent with Cockpit tracking."""

import sys
from pathlib import Path

# Ensure backend is importable when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermi.agent import HermiAgent


def main():
    agent = HermiAgent()
    print("Hermi CLI Agent — gib 'exit' zum Beenden")
    print("Tippe eine Aufgabe oder 'demonstration' für einen Demo-Durchlauf\n")

    try:
        while True:
            try:
                task = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nHermi beendet.")
                break

            if not task:
                continue
            if task.lower() == "exit":
                print("Hermi beendet.")
                break
            if task.lower() == "demonstration":
                task = "Suche nach KI-Trends 2026 analysiere die Ergebnisse und plane eine Zusammenfassung"

            result = agent.process(task)
            print(f"  Ergebnis: {result}\n")
    except KeyboardInterrupt:
        print("\nHermi beendet.")


if __name__ == "__main__":
    main()
