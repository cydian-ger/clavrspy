from pathlib import Path
import platform
import os
import re


DB_DIR = "db"


def get_base_path() -> Path:
    path = Path(__file__).parent / DB_DIR
    return path


def get_path() -> str:
    filenames = [filename for filename in os.listdir(Path(__file__).parent / "db")]
    filenames = [filename for filename in filenames if "clavrs" in filename]

    filters = []
    current_platform = platform.system().lower()

    if current_platform == "windows":
        filters.append(lambda filename: "windows" in filename and ".exe" in filename)
    elif current_platform ==  "linux":
        filters.append(lambda filename: "linux" in filename)
    else:
        pass
    
    filenames = [f for f in filenames if any(filter_func(f) for filter_func in filters)]

    files_with_versions = []
    pattern = re.compile(r"clavrs-(\d+\.\d+\.\d+)")
    for filename in filenames:
        match = pattern.search(filename)
        if match:
            version = match.group(1).split(".")
            major, minor, patch = version[0], version[1], version[2]
            files_with_versions.append(((major, minor, patch), filename))
            continue

    latest_file = sorted(files_with_versions, key=lambda x: x[0], reverse=True)[0][1]
    path = Path(__file__).parent / DB_DIR / latest_file
    return str(path)