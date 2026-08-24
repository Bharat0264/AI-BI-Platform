"""Initialize AURA-BI Mongo collections, indexes, and schema version safely."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from persistence.mongo import initialize, get_database
def main():
    initialize()
    version=get_database().schema_versions.find_one({"version":1},{"_id":0})
    print(f"MongoDB ready; schema version {version['version']} applied.")
if __name__ == "__main__": main()
