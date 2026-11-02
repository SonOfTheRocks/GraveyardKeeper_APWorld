import json
import os.path
from collections import defaultdict

INPUT_FILE = "craft_data.json"
OUTPUT_FILE = "craft_data_simplified.json"

def extract_ids(entries):
    if not isinstance(entries, list):
        return []
    return [e.get("id") for e in entries if isinstance(e, dict) and "id" in e]

def main():
    with open(os.path.join("dicts", INPUT_FILE), "r", encoding="utf-8") as f:
        data = json.load(f)

    # defaultdict lets us group by crafting station automatically
    grouped = defaultdict(dict)

    for item_id, item_data in data.items():
        entry = {
            "id": item_id,
            "needs": extract_ids(item_data.get("needs")),
            "output": extract_ids(item_data.get("output")),
            "icon": item_data.get("icon"),
            "craft_type": item_data.get("craft_type"),
            "tab_id": item_data.get("tab_id"),
        }

        craft_locations = item_data.get("craft_in", [])

        # if no crafting location exists, put it in a fallback group
        if not craft_locations:
            grouped["unknown"][item_id] = entry
        else:
            # add the item to every station it can be crafted in
            for station in craft_locations:
                grouped[station][item_id] = entry

    with open(os.path.join("dicts", OUTPUT_FILE), "w", encoding="utf-8") as f:
        json.dump(grouped, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in grouped.values())
    print(f"Written {total} items grouped into {len(grouped)} crafting stations to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()