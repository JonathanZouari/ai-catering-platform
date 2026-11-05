"""Install a pinned, integrity-checked PostgreSQL WASM test engine, not an app dependency."""
import base64
import hashlib
import io
from pathlib import Path
import tarfile
import urllib.request

URL = "https://registry.npmjs.org/@electric-sql/pglite/-/pglite-0.5.15.tgz"
SHA512 = "ERZWgaRTxueGV4cvL1tfpAOzFCWTXoUtbCBqnf2FhHDVs/so9eAKaanvrwWF9Dntx7BYsmFQujVQ0/B4S8Mmiw=="
root = (Path(__file__).parent / ".test-tools/pglite").resolve()
with urllib.request.urlopen(URL, timeout=60) as response:
    data = response.read()
if base64.b64encode(hashlib.sha512(data).digest()).decode() != SHA512:
    raise RuntimeError("Package integrity verification failed")
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    for member in archive.getmembers():
        if not member.isfile():
            continue
        parts = Path(member.name).parts
        if not parts or parts[0] != "package":
            raise RuntimeError("Unexpected package path")
        target = root.joinpath(*parts[1:]).resolve()
        if not target.is_relative_to(root):
            raise RuntimeError("Unsafe package path")
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.extractfile(member) as source:
            target.write_bytes(source.read())
print("Installed verified PGlite 0.5.15 into ignored .test-tools/pglite")
