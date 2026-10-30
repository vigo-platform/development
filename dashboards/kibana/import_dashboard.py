"""Import the checked-in Kibana export on each Compose startup."""

import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


def main():
    # Compose supplies the service hostname; direct host execution uses localhost.
    base_url = os.environ.get("KIBANA_URL", "http://localhost:5601").rstrip("/")
    export = Path(__file__).with_name("export.ndjson").read_bytes()
    deadline = time.monotonic() + 600
    print(f"Waiting for Kibana at {base_url} (up to 600 seconds)...", flush=True)
    while True:
        try:
            with urlopen(base_url + "/api/status", timeout=10) as response:
                status = json.load(response)
            level = status.get("status", {}).get("overall", {}).get("level")
            if level == "available":
                break
            reason = f"Kibana status: {level or 'unknown'}"
        except (URLError, TimeoutError, OSError, ValueError) as error:
            reason = str(error)
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Kibana at {base_url} did not become available within 600 seconds: {reason}")
        print(f"Not ready: {reason}. Retrying in 5 seconds...", flush=True)
        time.sleep(5)

    boundary = "kibana-import-" + uuid4().hex
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="export.ndjson"\r\n'
        "Content-Type: application/x-ndjson\r\n\r\n"
    ).encode() + export + f"\r\n--{boundary}--\r\n".encode()
    request = Request(
        base_url + "/api/saved_objects/_import?overwrite=true",
        data=body,
        headers={
            "kbn-xsrf": "true",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            result = json.load(response)
    except HTTPError as error:
        raise RuntimeError(
            f"Import HTTP {error.code}: {error.read().decode(errors='replace')}"
        ) from error
    # Kibana can return HTTP 200 even when some saved objects failed to import.
    if result.get("success") is not True or result.get("errors"):
        raise RuntimeError("Kibana import failed: " + json.dumps(result))
    print(f"Imported {result.get('successCount', 0)} Kibana saved objects.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Dashboard setup failed: {error}", file=sys.stderr)
        sys.exit(1)
