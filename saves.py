"""Zapisy gry: 3 sloty, plik ustawień (slot aktywny, limit FPS), wczytywanie i zapisywanie."""
import json
import time

from balance import *
from config import *
from progression import ARTIFACTS, CONTRACT_TIME, RELIC_PERKS


# --------------------
# Zapis postępu (kredyty, ulepszenia, statki)
# --------------------
SLOTS = 3


def slot_path(n):
    """Slot 1 to dawny frontier.json (stare zapisy działają dalej), pozostałe: frontier_2.json, frontier_3.json."""
    return SAVE_FILE if n == 1 else SAVE_FILE.with_name(f"frontier_{n}.json")


def settings_path():
    return SAVE_FILE.with_name("frontier_settings.json")


def read_settings():
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def write_settings(patch):
    """Uaktualnia plik ustawień w miejscu (slot aktywny + limit FPS), nie nadpisując drugiego pola."""
    data = read_settings()
    data.update(patch)
    try:
        settings_path().write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def read_active_slot():
    try:
        n = int(read_settings().get("slot", 1))
    except (ValueError, TypeError):
        n = 1
    return n if 1 <= n <= SLOTS else 1


def write_active_slot(n):
    write_settings({"slot": n})


def read_render_fps():
    try:
        n = int(read_settings().get("fps", 60))
    except (ValueError, TypeError):
        n = 60
    return n if n in RENDER_FPS_OPTIONS else 60


def write_render_fps(n):
    write_settings({"fps": n})


def default_save():
    return {"seed": WORLD_SEED, "credits": 0, "levels": {}, "owned": ["scout"], "ship": "scout",
            "base": {m["key"]: 0 for m in BASE_MODULES}, "project": None, "vault": 0.0,
            "drones": 0, "drone_tech": 0, "saved_at": 0.0,
            # endgame (sektor, relikty i artefakty zostają po skoku do nowego sektora)
            "sector": 1, "relics": 0, "relic_lv": {}, "artifacts": [], "earned": 0.0, "far": 0.0,
            "seen": ["iron"], "contracts": []}


def load_save(path, upgrade_keys, ship_ids):
    data = default_save()
    data["levels"] = {k: 0 for k in upgrade_keys}
    data["base"] = {m["key"]: 0 for m in BASE_MODULES}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data["seed"] = int(raw.get("seed", WORLD_SEED))
        data["credits"] = max(0, int(raw.get("credits", 0)))
        for k, costs in upgrade_keys.items():
            data["levels"][k] = max(0, min(len(costs), int(raw.get("levels", {}).get(k, 0))))
        data["owned"] = sorted({o for o in raw.get("owned", []) if o in ship_ids} | {"scout"})
        data["ship"] = raw.get("ship") if raw.get("ship") in data["owned"] else "scout"
        for m in BASE_MODULES:  # poziomy modułów bazy
            data["base"][m["key"]] = max(0, min(len(m["costs"]), int(raw.get("base", {}).get(m["key"], 0))))
        data["vault"] = max(0.0, float(raw.get("vault", 0.0)))
        data["drones"] = max(0, min(len(DRONE_COSTS), int(raw.get("drones", 0))))
        data["drone_tech"] = max(0, min(len(DRONE_TECH_COSTS), int(raw.get("drone_tech", 0))))
        data["saved_at"] = float(raw.get("saved_at", 0.0))
        data["sector"] = max(1, int(raw.get("sector", 1)))
        data["relics"] = max(0, int(raw.get("relics", 0)))
        data["relic_lv"] = {p["key"]: max(0, min(len(p["costs"]), int(raw.get("relic_lv", {}).get(p["key"], 0))))
                            for p in RELIC_PERKS}
        ids = {a[0] for a in ARTIFACTS}
        data["artifacts"] = [a for a in dict.fromkeys(raw.get("artifacts", [])) if a in ids]
        data["earned"] = max(0.0, float(raw.get("earned", 0.0)))
        data["far"] = max(0.0, float(raw.get("far", 0.0)))
        data["seen"] = [k for k in ORE_KINDS if k in raw.get("seen", []) or k == "iron"]
        data["contracts"] = [c for c in raw.get("contracts", []) if isinstance(c, dict) and c.get("type") in CONTRACT_TIME]
        pr = raw.get("project")
        if isinstance(pr, dict) and pr.get("key") in {m["key"] for m in BASE_MODULES}:
            m = module_by_key(pr["key"])
            if data["base"][m["key"]] < len(m["costs"]):
                data["project"] = {"key": pr["key"], "paid": max(0, int(pr.get("paid", 0))),
                                   "progress": {k: max(0, int(pr.get("progress", {}).get(k, 0))) for k in ORE_KINDS}}
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return data


def write_save(path, data):
    data["saved_at"] = time.time()
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        print("Nie można zapisać postępu:", path)
