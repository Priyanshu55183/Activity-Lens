"""
ActivityLens - Handoff Prompt Generator
=========================================

Scans a project directory and generates a structured context prompt that you
can paste into any AI chatbot. When you switch from one chatbot to another,
this tool gives the new chatbot full context about your project so it can
continue where you left off.

Usage:
    python src/handoff.py <project_path>                  # Print to stdout
    python src/handoff.py <project_path> --copy           # Copy to clipboard
    python src/handoff.py <project_path> --out context.md # Save to file
    python src/handoff.py <project_path> --max-files 20   # Override file limit

Example:
    python src/handoff.py d:\\my-project --copy
    # Now paste into any AI chatbot — it has full project context.
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import Config


# ---------------------------------------------------------------------------
# File tree scanner
# ---------------------------------------------------------------------------

def scan_file_tree(
    project_path: Path,
    ignore_dirs: list[str],
    ignore_extensions: list[str],
) -> str:
    """
    Walk the project directory and produce a clean, indented file tree.
    
    Skips ignored directories and file extensions. Limits depth to 4 levels
    to keep the tree readable.
    """
    ignore_dirs_lower = {d.lower() for d in ignore_dirs}
    ignore_ext_lower = {e.lower() for e in ignore_extensions}
    lines = []
    root_name = project_path.name

    def _walk(path: Path, prefix: str, depth: int):
        if depth > 4:
            return

        try:
            entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        # Filter entries
        filtered = []
        for entry in entries:
            if entry.name.startswith('.') and entry.name.lower() in ignore_dirs_lower:
                continue
            if entry.is_dir() and entry.name.lower() in ignore_dirs_lower:
                continue
            if entry.is_file() and any(entry.name.lower().endswith(ext) for ext in ignore_ext_lower):
                continue
            filtered.append(entry)

        for i, entry in enumerate(filtered):
            is_last = (i == len(filtered) - 1)
            connector = "+-- " if is_last else "|-- "
            extension = "    " if is_last else "|   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                _walk(entry, prefix + extension, depth + 1)
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    lines.append(f"{root_name}/")
    _walk(project_path, "", 0)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Key file detection
# ---------------------------------------------------------------------------

# Files that are always important if they exist
PRIORITY_FILES = [
    "README.md", "README.rst", "README.txt", "README",
    "package.json", "requirements.txt", "pyproject.toml", "Cargo.toml",
    "go.mod", "Gemfile", "pom.xml", "build.gradle",
    "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example",
]

# Entry point patterns (checked by name)
ENTRY_POINTS = [
    "main.py", "app.py", "index.js", "index.ts", "main.js", "main.ts",
    "server.py", "server.js", "server.ts", "manage.py",
    "main.go", "main.rs", "Program.cs",
]

# Config file patterns
CONFIG_FILES = [
    "config.yaml", "config.yml", "config.json", "config.toml",
    ".eslintrc.json", "tsconfig.json", "vite.config.js", "vite.config.ts",
    "webpack.config.js", "next.config.js", "tailwind.config.js",
]


def detect_key_files(
    project_path: Path,
    ignore_dirs: list[str],
    ignore_extensions: list[str],
    max_files: int = 15,
) -> list[Path]:
    """
    Auto-detect the most important files in a project.
    
    Priority order:
    1. README and manifest files (always included)
    2. Entry point files (main.py, index.js, etc.)
    3. Config files
    4. Recently modified files (last 24 hours)
    5. Source files by recency
    """
    ignore_dirs_lower = {d.lower() for d in ignore_dirs}
    ignore_ext_lower = {e.lower() for e in ignore_extensions}

    priority = []
    entry_points = []
    configs = []
    recent = []

    now = datetime.now().timestamp()
    day_ago = now - 86400  # 24 hours

    def _should_skip(path: Path) -> bool:
        for part in path.relative_to(project_path).parts:
            if part.lower() in ignore_dirs_lower:
                return True
        return any(path.name.lower().endswith(ext) for ext in ignore_ext_lower)

    for root, dirs, files in os.walk(project_path):
        root_path = Path(root)

        # Prune ignored directories
        dirs[:] = [d for d in dirs if d.lower() not in ignore_dirs_lower]

        for fname in files:
            fpath = root_path / fname

            if _should_skip(fpath):
                continue

            # Check if it's a text file (skip binary)
            if _is_binary(fpath):
                continue

            rel = fpath.relative_to(project_path)

            # Priority files
            if fname in PRIORITY_FILES:
                priority.append(fpath)
            elif fname in ENTRY_POINTS:
                entry_points.append(fpath)
            elif fname in CONFIG_FILES:
                configs.append(fpath)
            else:
                # Check recency
                try:
                    mtime = fpath.stat().st_mtime
                    if mtime > day_ago:
                        recent.append((fpath, mtime))
                except OSError:
                    pass

    # Sort recent by modification time (newest first)
    recent.sort(key=lambda x: x[1], reverse=True)
    recent_files = [f for f, _ in recent]

    # Combine in priority order, dedup
    seen = set()
    result = []

    for fpath in priority + entry_points + configs + recent_files:
        key = str(fpath)
        if key not in seen:
            seen.add(key)
            result.append(fpath)
            if len(result) >= max_files:
                break

    return result


def _is_binary(path: Path) -> bool:
    """Quick check if a file is binary by reading first 1024 bytes."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        # If there are null bytes, it's likely binary
        return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


# ---------------------------------------------------------------------------
# File reader (with smart truncation)
# ---------------------------------------------------------------------------

def read_file_content(path: Path, max_lines: int = 300) -> str:
    """
    Read a file's content, truncating if it exceeds max_lines.
    
    For long files, includes the first 200 lines + last 50 lines
    with a note about truncation.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, PermissionError):
        return "(Could not read file)"

    if len(lines) <= max_lines:
        return "".join(lines).rstrip()

    head = "".join(lines[:200])
    tail = "".join(lines[-50:])
    skipped = len(lines) - 250

    return (
        f"{head.rstrip()}\n\n"
        f"# ... ({skipped} lines omitted for brevity) ...\n\n"
        f"{tail.rstrip()}"
    )


# ---------------------------------------------------------------------------
# Git context
# ---------------------------------------------------------------------------

def get_git_context(project_path: Path) -> dict | None:
    """
    Extract git context: branch, recent commits, uncommitted changes.
    Returns None if the project is not a git repo.
    """
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return None

    ctx = {}

    try:
        # Current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=str(project_path), timeout=5,
        )
        ctx["branch"] = result.stdout.strip() or "(detached HEAD)"

        # Last 5 commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-5", "--no-decorate"],
            capture_output=True, text=True, cwd=str(project_path), timeout=5,
        )
        ctx["recent_commits"] = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(project_path), timeout=5,
        )
        changes = result.stdout.strip().split("\n") if result.stdout.strip() else []
        ctx["uncommitted"] = changes[:20]  # Limit to 20

        # Last commit date
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            capture_output=True, text=True, cwd=str(project_path), timeout=5,
        )
        ctx["last_commit_date"] = result.stdout.strip()

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    return ctx


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def generate_prompt(
    project_path: Path,
    tree: str,
    key_files: list[Path],
    git_ctx: dict | None,
    max_lines: int = 300,
) -> str:
    """Assemble the full handoff prompt."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    project_name = project_path.name
    sections = []

    # Header
    sections.append(f"# Project Context - {project_name}")
    sections.append(f"> Generated by ActivityLens Handoff on {now}\n")

    # Project structure
    sections.append("## Project Structure")
    sections.append(f"```\n{tree}\n```\n")

    # Git status
    if git_ctx:
        sections.append("## Git Status")
        sections.append(f"- **Branch:** `{git_ctx['branch']}`")

        if git_ctx.get("last_commit_date"):
            sections.append(f"- **Last commit:** {git_ctx['last_commit_date']}")

        if git_ctx.get("recent_commits"):
            sections.append("- **Recent commits:**")
            for commit in git_ctx["recent_commits"]:
                sections.append(f"  - {commit}")

        if git_ctx.get("uncommitted"):
            sections.append("- **Uncommitted changes:**")
            for change in git_ctx["uncommitted"]:
                sections.append(f"  - `{change.strip()}`")

        sections.append("")

    # Key files
    if key_files:
        sections.append("## Key Files\n")

        for fpath in key_files:
            rel = fpath.relative_to(project_path)
            ext = fpath.suffix.lstrip(".")
            lang = _detect_language(ext)
            content = read_file_content(fpath, max_lines)

            sections.append(f"### {rel}")
            sections.append(f"```{lang}\n{content}\n```\n")

    # Continue instruction
    sections.append("## Continue From Here")
    sections.append(
        f"I'm working on **{project_name}**. "
        f"The project structure and key files are shown above. "
        f"Please review the codebase context and help me continue development. "
        f"Ask me what I'd like to work on next."
    )

    return "\n".join(sections)


def _detect_language(ext: str) -> str:
    """Map file extension to markdown code fence language."""
    lang_map = {
        "py": "python", "js": "javascript", "ts": "typescript",
        "jsx": "jsx", "tsx": "tsx", "json": "json",
        "yaml": "yaml", "yml": "yaml", "toml": "toml",
        "md": "markdown", "html": "html", "css": "css",
        "sql": "sql", "sh": "bash", "bash": "bash",
        "rs": "rust", "go": "go", "rb": "ruby",
        "java": "java", "kt": "kotlin", "cs": "csharp",
        "cpp": "cpp", "c": "c", "h": "c",
        "xml": "xml", "txt": "", "cfg": "ini",
        "ini": "ini", "env": "bash",
    }
    return lang_map.get(ext, ext)


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------

def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard. Returns True on success."""
    try:
        subprocess.run(
            ["clip"],
            input=text.encode("utf-16-le"),  # clip.exe expects UTF-16LE on Windows
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: try pyperclip if available
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except (ImportError, Exception):
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ActivityLens Handoff - Generate project context for AI chatbots"
    )
    parser.add_argument(
        "project_path",
        type=str,
        help="Path to the project directory to scan",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy the output to clipboard",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Save output to a file (e.g., --out context.md)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Override max number of key files to include",
    )
    args = parser.parse_args()

    project_path = Path(args.project_path).resolve()
    if not project_path.exists():
        print(f"  [ERROR] Path not found: {project_path}")
        sys.exit(1)
    if not project_path.is_dir():
        print(f"  [ERROR] Not a directory: {project_path}")
        sys.exit(1)

    # Load config
    config = Config()
    hcfg = config.handoff_config
    ignore_dirs = hcfg["ignore_dirs"]
    ignore_exts = hcfg["ignore_extensions"]
    max_lines = hcfg["max_file_lines"]
    max_files = args.max_files or hcfg["max_files"]

    print("=" * 60)
    print("  ActivityLens - Handoff Prompt Generator")
    print("=" * 60)
    print(f"\n  Project: {project_path}")

    # Step 1: Scan file tree
    print("  Scanning file tree...")
    tree = scan_file_tree(project_path, ignore_dirs, ignore_exts)

    # Step 2: Detect key files
    print(f"  Detecting key files (max {max_files})...")
    key_files = detect_key_files(project_path, ignore_dirs, ignore_exts, max_files)
    print(f"  Found {len(key_files)} key files:")
    for f in key_files:
        rel = f.relative_to(project_path)
        print(f"    - {rel}")

    # Step 3: Git context
    print("  Checking git status...")
    git_ctx = get_git_context(project_path)
    if git_ctx:
        print(f"  Branch: {git_ctx['branch']}, "
              f"{len(git_ctx.get('recent_commits', []))} recent commits, "
              f"{len(git_ctx.get('uncommitted', []))} uncommitted changes")
    else:
        print("  (not a git repo)")

    # Step 4: Generate prompt
    print("  Generating handoff prompt...")
    prompt = generate_prompt(project_path, tree, key_files, git_ctx, max_lines)

    # Count stats
    prompt_lines = prompt.count("\n") + 1
    prompt_chars = len(prompt)
    print(f"\n  Prompt: {prompt_lines} lines, {prompt_chars:,} characters")

    # Output
    if args.out:
        out_path = Path(args.out)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"  Saved to: {out_path.resolve()}")

    if args.copy:
        if copy_to_clipboard(prompt):
            print("  Copied to clipboard!")
        else:
            print("  [WARNING] Could not copy to clipboard. Output printed below.")
            args.copy = False

    if not args.copy and not args.out:
        print("\n" + "-" * 60)
        # Use UTF-8 for stdout to handle non-ASCII in file contents
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        print(prompt)
        print("-" * 60)

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
