"""将最新 AI 日志 JSONL 转为可读 Markdown，用法：uv run python tools/ai_log_to_md.py"""
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs" / "ai"


def find_latest_jsonl() -> Path | None:
    files = sorted(LOG_DIR.rglob("ai_*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None


def record_to_md(r: dict, idx: int) -> str:
    lines = [
        f"## [{idx}] {r.get('stage', '')}",
        f"- 时间：{r.get('ts', '')}",
        f"- thread_id：`{r.get('thread_id', '')}`",
        "",
    ]
    for msg in r.get("input", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "").strip()
        lines += [f"**{role}**", "", content, ""]

    lines += ["**output**", "", r.get("output", "").strip(), "", "---", ""]
    return "\n".join(lines)


def convert(jsonl_path: Path) -> Path:
    records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    md_path = jsonl_path.with_suffix(".md")
    parts = [f"# AI 日志 - {jsonl_path.name}\n"]
    for i, r in enumerate(records, 1):
        parts.append(record_to_md(r, i))
    md_path.write_text("\n".join(parts), encoding="utf-8")
    return md_path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_jsonl()
    if not target or not target.exists():
        print("未找到 AI 日志文件")
        sys.exit(1)
    out = convert(target)
    print(f"已生成: {out}")
