
## 2024-05-18 - Prevent Path Traversal via Windows Separators on POSIX
**Vulnerability:** Path traversal possible via `os.path.basename` when processing malicious inputs containing Windows-style path separators (`\`).
**Learning:** `os.path.basename()` behaves differently on POSIX vs Windows. On POSIX systems, it does not recognize `\` as a path separator. Thus, a string like `..\\..\\etc\\passwd` passes through `os.path.basename` untouched on Linux, allowing directory traversal.
**Prevention:** Normalize input paths using `path.replace("\\", "/")` prior to any path validation or processing like `os.path.basename` to ensure security consistency across platforms.
