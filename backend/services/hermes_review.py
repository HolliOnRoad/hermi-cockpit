import json
import socket
import time
import urllib.request
import urllib.error
from pathlib import Path

OLLAMA_API = "http://127.0.0.1:11434/api/generate"
REVIEW_MODEL = "qwen2.5:14b"
REVIEW_TIMEOUT = 120
MAX_TEXT_CHARS = 8000


def _build_prompt(title: str, text: str, source: str, source_type: str) -> str:
    full_text = text
    truncated = False
    if len(full_text) > MAX_TEXT_CHARS:
        truncated = True
        full_text = full_text[:MAX_TEXT_CHARS] + f"\n\n[Text wurde auf {MAX_TEXT_CHARS} Zeichen gekuerzt]"

    truncation_hint = (
        f"HINWEIS: Der Text wurde auf {MAX_TEXT_CHARS} Zeichen gekuerzt. "
        "Deine Analyse kann daher unvollstaendig sein.\n\n"
    ) if truncated else ""

    return (
        "Du bist ein Review-Assistent. Analysiere den folgenden Eintrag "
        "AUSSCHLIESSLICH auf Basis des vorliegenden Textes. "
        "Du hast KEINEN Zugriff auf externe Quellen, Websuche oder Faktenchecks. "
        "Formuliere alle Aussagen so, dass klar ist: sie basieren nur auf dem "
        "hier gegebenen Text, nicht auf extern geprueften Fakten.\n\n"
        "Nutze Formulierungen wie 'laut vorliegendem Text', 'auf Basis des Eintrags', "
        "'im Text wird behauptet', 'der Eintrag legt nahe'.\n\n"
        "Behaupte NIEMALS, dass etwas wahr oder falsch ist, wenn du es nicht "
        "extern geprueft hast. Wenn der Text Behauptungen aufstellt, "
        "gib sie als Behauptungen wieder, nicht als Fakten.\n\n"
        + truncation_hint
        + "--- EINTRAG ---\n"
        f"Titel: {title}\n"
        f"Quelle: {source or 'unbekannt'}\n"
        f"Typ: {source_type or 'unbekannt'}\n\n"
        f"Text:\n{full_text}\n"
        "--- ENDE EINTRAG ---\n\n"
        "Erstelle eine strukturierte Analyse im folgenden JSON-Format "
        "(NUR das JSON-Objekt, kein Begleittext):\n\n"
        "{\n"
        '  "kurzfazit": "2-4 Saetze: Was ist der Inhalt? Warum koennte das fuer Holger (Technik-Interessierter, arbeitet mit Hermes AI) relevant sein?",\n'
        '  "relevanz": {\n'
        '    "stufe": "HOCH|MITTEL|NIEDRIG",\n'
        '    "begruendung": "1-2 Saetze"\n'
        '  },\n'
        '  "plausibilitaet": {\n'
        '    "stufe": "HOCH|MITTEL|NIEDRIG|UNKLAR",\n'
        '    "begruendung": "1-2 Saetze auf Basis des vorliegenden Textes, ohne erfundene Fakten"\n'
        '  },\n'
        '  "empfehlung": {\n'
        '    "aktion": "VERWERFEN|SPAETER|KANBAN|LESEN",\n'
        '    "begruendung": "1-2 Saetze warum diese Aktion"\n'
        '  },\n'
        '  "risiken": "Was koennte unklar, uebertrieben, veraltet oder nicht geprueft sein? Sei ehrlich ueber Unsicherheiten.",\n'
        '  "naechster_schritt": "Eine konkrete Handlungsempfehlung fuer Holger, z.B. Querverweis mit XY pruefen, Thema im Council ansprechen, selbst testen, ignorieren."\n'
        "}\n\n"
        "WICHTIG: Antworte NUR mit dem JSON-Objekt. Kein '```json', kein Begleittext."
    )


def _parse_review_response(raw_response: str, entry_title: str) -> dict:
    text = raw_response.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        return parsed
    except json.JSONDecodeError:
        pass

    for prefix in ["{", "```json\n{", "```\n{"]:
        idx = raw_response.find(prefix)
        if idx != -1:
            depth = 0
            start = idx
            for i in range(idx, len(raw_response)):
                if raw_response[i] == "{":
                    depth += 1
                elif raw_response[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            chunk = raw_response[start:i + 1]
                            if chunk.startswith("```"):
                                chunk = chunk.split("\n", 1)[1] if "\n" in chunk else chunk[3:]
                            return json.loads(chunk)
                        except json.JSONDecodeError:
                            break
            break

    return {
        "kurzfazit": raw_response[:400] if len(raw_response) > 400 else raw_response,
        "relevanz": {"stufe": "UNKLAR", "begruendung": "Konnte nicht automatisch geparst werden."},
        "plausibilitaet": {"stufe": "UNKLAR", "begruendung": "Automatische Analyse nicht verwertbar."},
        "empfehlung": {"aktion": "LESEN", "begruendung": "Bitte manuell pruefen."},
        "risiken": "Analyse nicht strukturiert lesbar.",
        "naechster_schritt": "Manuelle Sichtung empfohlen.",
        "_parse_warning": "raw_fallback",
    }


def _run_local_fallback(title: str, text: str, source: str, source_type: str, reason: str = "") -> dict:
    raw_content = title + "\n" + text
    content_len = len(raw_content)

    warning = "Dies ist eine lokale Strukturpruefung ohne KI-Analyse."
    if reason:
        warning += f" Grund: {reason}"

    if content_len < 30:
        relevanz = {"stufe": "NIEDRIG", "begruendung": "Sehr wenig Rohmaterial fuer eine Bewertung."}
        plausibilitaet = {"stufe": "UNKLAR", "begruendung": "Kaum Text fuer eine Inhaltsanalyse vorhanden."}
        empfehlung = {"aktion": "LESEN", "begruendung": "Kaum Substanz; bei Interesse bitte selbst pruefen."}
        risiken = f"Zu wenig Text fuer eine sinnvolle Analyse. {warning}"
        naechster_schritt = "Bei Relevanz Originalquelle aufsuchen."
    elif content_len < 200:
        relevanz = {"stufe": "NIEDRIG", "begruendung": "Kurzer Eintrag, wenig Kontext."}
        plausibilitaet = {"stufe": "UNKLAR", "begruendung": "Auf Basis des kurzen Textes nicht einschaetzbar."}
        empfehlung = {"aktion": "LESEN", "begruendung": "Kurz, daher schnell selbst lesbar."}
        risiken = f"Kaum Kontext fuer eine fundierte Einschaetzung. {warning}"
        naechster_schritt = "Selbst lesen und entscheiden."
    else:
        preview = text[:300].replace("\n", " ")
        relevanz = {"stufe": "MITTEL", "begruendung": f"Mehrzeiliger Eintrag, Thema unklar. Text beginnt mit: '{preview[:80]}...'"}
        plausibilitaet = {"stufe": "UNKLAR", "begruendung": "Ohne LLM-Analyse keine Plausibilitaetspruefung moeglich."}
        empfehlung = {"aktion": "LESEN", "begruendung": "Laengeren Text bitte selbst bewerten."}
        risiken = warning
        naechster_schritt = "Text lesen und Relevanz selbst einschaetzen. Oder Ollama starten und erneut pruefen."

    return {
        "kurzfazit": f"Lokale Strukturpruefung fuer '{title}'. {text[:200]}" + ("..." if len(text) > 200 else ""),
        "relevanz": relevanz,
        "plausibilitaet": plausibilitaet,
        "empfehlung": empfehlung,
        "risiken": risiken,
        "naechster_schritt": naechster_schritt,
        "_analysis_source": "local_fallback_no_llm",
    }


def run_review(title: str, text: str, source: str = "", source_type: str = "") -> dict:
    prompt = _build_prompt(title, text, source, source_type)
    text_truncated = len(text) > MAX_TEXT_CHARS

    try:
        payload = json.dumps({
            "model": REVIEW_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 2048, "temperature": 0.2}
        }).encode()

        req = urllib.request.Request(
            OLLAMA_API,
            data=payload,
            headers={"Content-Type": "application/json"}
        )

        t_start = time.time()
        with urllib.request.urlopen(req, timeout=REVIEW_TIMEOUT) as resp:
            ollama_response = json.loads(resp.read())

        elapsed = round(time.time() - t_start, 1)
        response_text = ollama_response.get("response", "")
        eval_count = ollama_response.get("eval_count", 0)
        prompt_eval_count = ollama_response.get("prompt_eval_count", 0)

        parsed = _parse_review_response(response_text, title)
        parse_warning = parsed.pop("_parse_warning", None)

        parsed["_analysis_source"] = "ollama_local"
        parsed["_model"] = REVIEW_MODEL
        parsed["_elapsed_sec"] = elapsed
        parsed["_eval_count"] = eval_count
        parsed["_prompt_eval_count"] = prompt_eval_count
        if parse_warning:
            parsed["_parse_warning"] = parse_warning
        if text_truncated:
            parsed["_text_truncated"] = True
            parsed["_text_original_chars"] = len(text)

        print(
            f"[hermes-review] OK model={REVIEW_MODEL} elapsed={elapsed}s "
            f"eval={eval_count} prompt_eval={prompt_eval_count}"
            + (f" truncated={len(text)}->{MAX_TEXT_CHARS}" if text_truncated else "")
            + (f" parse_warn={parse_warning}" if parse_warning else ""),
            flush=True,
        )
        return parsed

    except urllib.error.HTTPError as e:
        if e.code == 404:
            reason = f"Modell '{REVIEW_MODEL}' nicht gefunden (HTTP 404). Bitte 'ollama pull {REVIEW_MODEL}' ausfuehren."
        else:
            reason = f"Ollama HTTP {e.code}: {e.reason}"
        print(f"[hermes-review] HTTPError: {reason}", flush=True)
        return _run_local_fallback(title, text, source, source_type, reason=reason)

    except urllib.error.URLError as e:
        reason = f"Ollama nicht erreichbar (Verbindungsfehler: {e.reason})"
        print(f"[hermes-review] URLError: {reason}", flush=True)
        return _run_local_fallback(title, text, source, source_type, reason=reason)

    except socket.timeout:
        reason = f"Timeout nach {REVIEW_TIMEOUT}s"
        print(f"[hermes-review] Timeout nach {REVIEW_TIMEOUT}s", flush=True)
        return _run_local_fallback(title, text, source, source_type, reason=reason)

    except Exception as e:
        reason = f"Unerwarteter Fehler: {type(e).__name__}"
        print(f"[hermes-review] Exception {type(e).__name__}: {e}", flush=True)
        return _run_local_fallback(title, text, source, source_type, reason=reason)
