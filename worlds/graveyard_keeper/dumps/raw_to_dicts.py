import json
from pathlib import Path

INPUT_DIR = Path("raw")
OUTPUT_DIR = Path("dicts")

OUTPUT_DIR.mkdir(exist_ok=True)

def split():
    for file_path in INPUT_DIR.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError(f"{file_path.name} does not contain a list")

        result = {}
        seen_ids = set()

        for obj in data:
            if "id" not in obj:
                raise ValueError(f"Missing 'id' in {file_path.name}: {obj}")

            obj_id = obj["id"]

            if obj_id in seen_ids:
                raise ValueError(f"Duplicate id '{obj_id}' in {file_path.name}")

            seen_ids.add(obj_id)
            result[obj_id] = obj

        output_path = OUTPUT_DIR / file_path.name
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"Processed: {file_path.name}")

if __name__ == "__main__":
    split()