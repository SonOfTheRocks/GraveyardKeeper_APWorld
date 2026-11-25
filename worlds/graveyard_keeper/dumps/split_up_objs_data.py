import json
from collections import defaultdict

INPUT_FILE = "objs_data.json"

# Map your enum values here (adjust numbers if needed)
TYPE_MAP = {
    0: "Default",
    1: "Mob",
    2: "NPC",
    3: "PorterStation",
    4: "SoulTotem",
}

def split_json_by_type():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)  # list of objects

    grouped = defaultdict(dict)
    seen_ids = set()

    for obj in data:
        obj_id = obj.get("id")
        raw_type = obj.get("type")

        if obj_id is None:
            raise ValueError(f"Object missing 'id': {obj}")

        if obj_id in seen_ids:
            raise ValueError(f"Duplicate id found: {obj_id}")

        seen_ids.add(obj_id)

        # Map int enum → readable string
        obj_type = TYPE_MAP.get(raw_type, f"Unknown_{raw_type}")

        grouped[obj_type][obj_id] = obj

    # Write each type to its own file
    for obj_type, items in grouped.items():
        filename = f"objs_data/{obj_type}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)

        print(f"Wrote {len(items)} items to {filename}")

if __name__ == "__main__":
    split_json_by_type()