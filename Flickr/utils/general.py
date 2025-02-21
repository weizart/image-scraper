# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# General utilities for use in image-handling operations
# Written by Glenn Jocher (glenn.jocher@ultralytics.com) for https://github.com/ultralytics

import os
from pathlib import Path

import requests
from PIL import Image


def download_uri(uri, dir="./"):
    """Downloads file from URI using streaming to reduce memory usage."""
    try:
        # Download using streaming
        f = Path(dir) / os.path.basename(uri)  # filename
        with requests.get(uri, stream=True, timeout=10) as r:
            r.raise_for_status()
            with open(f, 'wb') as file:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

        # Rename (remove wildcard characters)
        src = str(f)  # original name
        new_name = src
        for c in ["%20", "%", "*", "~", "(", ")"]:
            new_name = new_name.replace(c, "_")
        new_name = new_name[: new_name.index("?")] if "?" in new_name else new_name
        if src != new_name:
            os.rename(src, new_name)
            f = Path(new_name)

        # Add suffix (if missing)
        if f.suffix == "":
            try:
                src = str(f)  # original name
                with Image.open(src) as img:
                    new_name = f"{src}.{img.format.lower()}"
                os.rename(src, new_name)
                f = Path(new_name)
            except Exception as e:
                if os.path.exists(src):
                    os.remove(src)
                raise e
                
        return True
    except Exception as e:
        if os.path.exists(f):
            os.remove(f)
        raise e
