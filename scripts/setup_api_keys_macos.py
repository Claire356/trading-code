from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


def main() -> None:
    anthropic_key = prompt_hidden(
        "Claude API Key",
        "请输入你的 ANTHROPIC_API_KEY。输入会被隐藏，不会打印到终端。",
    )
    miromind_key = prompt_hidden(
        "Miromind API Key",
        "请输入你的 MIROMIND_API_KEY。输入会被隐藏，不会打印到终端。",
    )

    existing = read_existing_env()
    existing["ANTHROPIC_API_KEY"] = anthropic_key
    existing["MIROMIND_API_KEY"] = miromind_key
    existing.setdefault("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    existing.setdefault("MIROMIND_MODEL", "mirothinker-1-7-deepresearch-mini")
    existing.setdefault("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    existing.setdefault("MIROMIND_BASE_URL", "https://api.miromind.ai")

    write_env(existing)
    notify("完成", f"API keys 已保存到：{ENV_PATH}")


def prompt_hidden(title: str, message: str) -> str:
    script = f'''
    display dialog "{escape_applescript(message)}" default answer "" with hidden answer buttons {{"取消", "保存"}} default button "保存" with title "{escape_applescript(title)}"
    text returned of result
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit("已取消，未保存 API key。")
    value = result.stdout.strip()
    if not value:
        raise SystemExit(f"{title} 为空，未保存。")
    return value


def notify(title: str, message: str) -> None:
    script = f'display dialog "{escape_applescript(message)}" buttons {{"OK"}} default button "OK" with title "{escape_applescript(title)}"'
    subprocess.run(["osascript", "-e", script], check=False)


def read_existing_env() -> dict:
    values = {}
    if not ENV_PATH.exists():
        return values
    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_env(values: dict) -> None:
    ordered_keys = [
        "ANTHROPIC_API_KEY",
        "MIROMIND_API_KEY",
        "CLAUDE_MODEL",
        "MIROMIND_MODEL",
        "ANTHROPIC_BASE_URL",
        "MIROMIND_BASE_URL",
    ]
    lines = ["# Local secrets. Do not commit this file.", ""]
    for key in ordered_keys:
        if key in values:
            lines.append(f"{key}={values[key]}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_PATH.chmod(0o600)


def escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


if __name__ == "__main__":
    main()
