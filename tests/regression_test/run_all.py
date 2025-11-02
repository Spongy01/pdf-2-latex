import json
import subprocess
from datetime import datetime
import logging
from pathlib import Path


# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# --- Helper functions ---
def load_versions(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def save_versions(file_path, versions):
    with open(file_path, "w") as f:
        json.dump(versions, f, indent=2, default=str)

def set_current_version(versions, version_name):
    for v in versions:
        v["is_current"] = (v["name"] == version_name)

def get_current_version(versions):
    for v in versions:
        if v["is_current"]:
            return v["name"]
    return None

# --- Main runner ---
def run_on_all_versions(version_file, main_script):
    # Load versions
    versions = load_versions(version_file)

    # Remember original current version
    original_version = get_current_version(versions)

    try:
        # Iterate over all versions in order of creation
        # versions_sorted = sorted(versions, key=lambda x: datetime.fromisoformat(x["created_at"]))
        for version in versions:
            print(f"Running {main_script} on version: {version['name']}")

            # Make this version current
            set_current_version(versions, version["name"])
            save_versions(version_file, versions)

            # Run main.py via subprocess
            ai = "ai"
            algo = "algorithms"
            assm = "assembly"
            cyb = "cybersec"
            ds = "data-science"
            method = "--scoring-method"
            metric = f"multi-metric"
            subprocess.run(["python", main_script, ai , algo,assm,cyb,ds, method,metric], check=True)

    finally:
        # Restore original version
        print(f"Restoring original version: {original_version}")
        set_current_version(versions, original_version)
        save_versions(version_file, versions)

if __name__ == "__main__":
    version_file = Path(__file__).parent.parent.parent / "codes" / "pdf_to_latex" / "version_control" / "version_history.json"
    if not version_file.exists():
        logger.warning(f"version_history.json not found at {version_file}; skipping regression test.")
        exit(0)

    run_on_all_versions(version_file, "main.py")
