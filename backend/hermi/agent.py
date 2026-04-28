"""Hermi Agent — Task processor with Cockpit event tracking."""

import sys
import time
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
_sys_path_added = False

def _ensure_path():
    global _sys_path_added
    if not _sys_path_added:
        sys.path.insert(0, str(_backend_dir))
        _sys_path_added = True

_ensure_path()
from services.event_client import send_event


class HermiAgent:
    """Hermi task agent. Processes user input, calls tools, spawns sub-agents. """

    def __init__(self):
        self.tools = {
            "web_search": self._tool_web_search,
            "fetch_url": self._tool_fetch_url,
            "analyze_code": self._tool_analyze_code,
            "read_file": self._tool_read_file,
            "write_file": self._tool_write_file,
        }
        self.agents = {
            "researcher": self._agent_research,
            "analyst": self._agent_analyze,
            "planner": self._agent_plan,
            "reviewer": self._agent_review,
        }

    # ---- Public API ----

    def process(self, task: str, source: str = "user") -> str:
        """Process a user task end-to-end. Returns result summary."""
        self._emit("task", f"Task gestartet: {task[:80]}", meta={"task": task})

        try:
            result = self._run_task(task)
            self._emit("done", "Task abgeschlossen", level="success",
                       meta={"task": task[:80], "result": result[:120]})
            return result
        except Exception as e:
            self._emit("error", f"Fehler: {str(e)}", level="error",
                       meta={"task": task[:80], "error": str(e)})
            return f"FEHLER: {e}"

    # ---- Internal task processing ----

    def _run_task(self, task: str) -> str:
        results = []
        task_lower = task.lower()

        if any(w in task_lower for w in ("search", "such", "recherch", "google")):
            results.append(self._call_tool("web_search", task))

        if any(w in task_lower for w in ("fetch", "url", "http", "lade")):
            results.append(self._call_tool("fetch_url", task))

        if any(w in task_lower for w in ("analy", "code", "review")):
            results.append(self._call_tool("analyze_code", task))

        if any(w in task_lower for w in ("file", "datei", "read", "lesen", "write", "schreib")):
            if "read" in task_lower or "lesen" in task_lower:
                results.append(self._call_tool("read_file", task))
            if "write" in task_lower or "schreib" in task_lower:
                results.append(self._call_tool("write_file", task))

        if any(w in task_lower for w in ("research", "recherch", "forsch", "researcher")):
            results.append(self._spawn_agent("researcher", task))

        if any(w in task_lower for w in ("plan", "planner", "planung")):
            results.append(self._spawn_agent("planner", task))

        if any(w in task_lower for w in ("review", "reviewer", "pruef", "check")):
            results.append(self._spawn_agent("reviewer", task))

        if any(w in task_lower for w in ("analyst",)):
            results.append(self._spawn_agent("analyst", task))

        if any(w in task_lower for w in ("error", "fehler", "crash", "fail")):
            raise RuntimeError(f"Simulierter Fehler beim Verarbeiten von: {task[:60]}")

        if not results:
            self._emit("log", f"Hermi verarbeitet: {task[:80]}")
            time.sleep(0.8)
            results.append(f"Verstanden: {task}")

        return " | ".join(results)

    # ---- Tool system ----

    def _call_tool(self, name: str, context: str) -> str:
        self._emit("tool", f"Tool aufgerufen: {name}", meta={"tool": name})
        fn = self.tools.get(name, self._tool_unknown)
        return fn(context)

    def _tool_web_search(self, ctx: str) -> str:
        time.sleep(0.5)
        return f"web_search: relevante Ergebnisse fuer '{ctx[:40]}...' gefunden"

    def _tool_fetch_url(self, ctx: str) -> str:
        time.sleep(0.5)
        return f"fetch_url: Inhalt geladen"

    def _tool_analyze_code(self, ctx: str) -> str:
        time.sleep(0.7)
        return f"analyze_code: Code-Analyse abgeschlossen"

    def _tool_read_file(self, ctx: str) -> str:
        time.sleep(0.3)
        return f"read_file: Datei gelesen"

    def _tool_write_file(self, ctx: str) -> str:
        time.sleep(0.3)
        return f"write_file: Datei geschrieben"

    def _tool_unknown(self, ctx: str) -> str:
        return f"Unbekanntes Tool: {ctx[:40]}"

    # ---- Sub-agent system ----

    def _spawn_agent(self, name: str, task: str) -> str:
        self._emit("agent", f"Agent gestartet: {name}", meta={"agent": name})
        fn = self.agents.get(name, self._agent_unknown)
        result = fn(task)
        self._emit("agent", f"Agent beendet: {name}", meta={"agent": name})
        return result

    def _agent_research(self, task: str) -> str:
        time.sleep(1.0)
        self._emit("log", "Researcher: sammle Informationen ...", source="agent")
        return "researcher: Recherche abgeschlossen"

    def _agent_analyze(self, task: str) -> str:
        time.sleep(0.6)
        return "analyst: Analyse abgeschlossen"

    def _agent_plan(self, task: str) -> str:
        time.sleep(0.8)
        self._emit("log", "Planner: erstelle Plan ...", source="agent")
        return "planner: Plan erstellt"

    def _agent_review(self, task: str) -> str:
        time.sleep(0.6)
        return "reviewer: Review abgeschlossen"

    def _agent_unknown(self, task: str) -> str:
        return f"Unbekannter Agent: {task[:40]}"

    # ---- Event emission ----

    def _emit(self, type: str, message: str, level: str = "info",
              source: str = "hermi", meta: dict | None = None):
        try:
            send_event(message, type=type, level=level, source=source, meta=meta)
        except Exception:
            pass  # never block on event failure
