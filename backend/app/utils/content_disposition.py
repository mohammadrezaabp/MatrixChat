import re
from urllib.parse import quote


def attachment_content_disposition(filename: str) -> str:
    """
    Build a Content-Disposition value safe for Starlette (latin-1 on the wire).
    Uses an ASCII filename= fallback plus RFC 5987 filename*=UTF-8'' for Unicode.
    """
    name = (filename or "export").strip() or "export"
    if not name.lower().endswith(".sql"):
        name = f"{name}.sql"

    ascii_name = name.encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^\w.\-]", "_", ascii_name).strip("._") or "export"
    if not ascii_name.lower().endswith(".sql"):
        ascii_name = f"{ascii_name}.sql"

    encoded = quote(name, safe="")
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded}'
