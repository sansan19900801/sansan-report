#!/usr/bin/env python3
"""诊断存档的确定性工具：解析存档根、生成项目 slug、生成存档文件路径、列出存档。

只负责「重复且确定」的文件系统动作，不生成存档正文（正文由 Agent 写）。
sansan-save / sansan-restore / sansan-report 共用同一套规则，保证三者路径一致。

用法：
  archive.py resolve-root [--json]
  archive.py slug [--slug <指定项目>] [--json]
  archive.py new-path --title <标题> [--slug <项目>] [--json]
  archive.py list [<项目>] [--json]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import string
import sys
from datetime import datetime
from pathlib import Path

CONFIG_REL = Path(".sansan") / "config.json"
SESSIONS_DIR = "sessions"
STATUS_ZH = {"in-progress": "进行中", "resolved": "已结论", "abandoned": "已放弃"}


def die(message: str) -> "None":
    print(f"✗ {message}", file=sys.stderr)
    sys.exit(1)


def read_config(cwd: Path) -> dict | None:
    cfg_path = cwd / CONFIG_REL
    if not cfg_path.is_file():
        return None
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        die(f"配置文件无法解析：{cfg_path}（{error}）。请修正后重试，不会静默退回默认位置。")
    if not isinstance(data, dict):
        die(f"配置文件格式不正确：{cfg_path}，根节点必须是对象。")
    return data


def resolve_root(cwd: Path | None = None) -> Path:
    """按固定规则解析存档根目录；任何不安全或不支持的配置都直接报错。"""
    cwd = (cwd or Path.cwd()).resolve()
    home = Path.home().resolve()
    config = read_config(cwd)

    if config is None:
        mode = "default"
        raw_root = None
    else:
        mode = config.get("mode", "default")
        raw_root = config.get("root")

    if mode == "default":
        root = home / ".sansan"
    elif mode == "project":
        root = cwd / ".sansan"
    elif mode == "custom":
        if not raw_root or not isinstance(raw_root, str) or not raw_root.strip():
            die("custom 模式缺少非空 root 字段。")
        expanded = raw_root.strip().replace("~", str(home), 1) if raw_root.strip().startswith("~") else raw_root.strip()
        candidate = Path(expanded)
        root = (cwd / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    else:
        die(f"不支持的 mode：{mode}（只支持 default / project / custom）。")

    forbidden = {Path("/").resolve(), home, cwd}
    if root.resolve() in forbidden:
        die(f"存档根目录不允许指向 /、用户家目录或项目根目录：{root}")
    return root.resolve()


def project_slug(explicit: str | None = None, cwd: Path | None = None) -> str:
    cwd = (cwd or Path.cwd()).resolve()
    if explicit:
        raw = explicit
    elif cwd == Path.home().resolve():
        raw = "default"
    else:
        raw = cwd.name
    slug = raw.strip().lower()
    # 保留中英文与数字（\w 在 str 模式下含中文），空白和下划线转连字符，其余标点符号直接去掉
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^\w一-鿿-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug or "default"


def title_slug(title: str) -> str:
    text = title.strip().lower()
    # 保留中英文与数字，其余空白/标点统一成连字符
    text = re.sub(r"[\s_，。、；：？！,.;:!?\"'（）()\[\]{}<>《》/\\|]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "untitled"


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    data: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            data[key.strip()] = value.strip()
    return data


def cmd_resolve_root(args) -> None:
    root = resolve_root()
    cfg = Path.cwd() / CONFIG_REL
    payload = {"root": str(root), "config": str(cfg) if cfg.is_file() else None}
    print(json.dumps(payload, ensure_ascii=False) if args.json else str(root))


def cmd_slug(args) -> None:
    slug = project_slug(args.slug)
    print(json.dumps({"slug": slug}, ensure_ascii=False) if args.json else slug)


def cmd_new_path(args) -> None:
    root = resolve_root()
    slug = project_slug(args.slug)
    now = datetime.now().astimezone()
    iso = now.isoformat(timespec="seconds")
    compact = now.strftime("%Y%m%d-%H%M%S")
    tslug = title_slug(args.title)
    directory = root / SESSIONS_DIR / slug
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{compact}-{tslug}.md"
    path = directory / base
    if path.exists():  # 同一秒同名，追加 4 位随机后缀
        suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        path = directory / f"{compact}-{tslug}-{suffix}.md"
    payload = {
        "path": str(path),
        "root": str(root),
        "slug": slug,
        "iso_timestamp": iso,
        "filename": path.name,
    }
    print(json.dumps(payload, ensure_ascii=False) if args.json else str(path))


def cmd_list(args) -> None:
    root = resolve_root()
    slug = project_slug(args.project)
    directory = root / SESSIONS_DIR / slug
    records = []
    if directory.is_dir():
        for md in sorted(directory.glob("*.md")):
            meta = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            ts = meta.get("timestamp", "")
            display_time = ts.replace("T", " ")[:16] if ts else md.name[:15]
            records.append({
                "file": md.name,
                "timestamp": ts,
                "display_time": display_time,
                "title": meta.get("title", md.stem),
                "status": meta.get("status", ""),
                "source_skill": meta.get("source_skill", ""),
            })
    if args.json:
        print(json.dumps({"project": slug, "count": len(records), "items": records}, ensure_ascii=False, indent=2))
        return
    if not records:
        print(f"当前项目 `{slug}` 下没有存档。先做诊断再存档。")
        return
    print(f"项目：{slug}")
    print(f"共 {len(records)} 份存档：\n")
    for index, item in enumerate(records, 1):
        status = STATUS_ZH.get(item["status"], item["status"] or "未知")
        source = f" · 来自 {item['source_skill']}" if item["source_skill"] else ""
        print(f"{index}. {item['display_time']} · {item['title']} · {status}{source}")


def _snapshot_files(directory: Path) -> list[Path]:
    """某项目目录下的存档，按文件名前缀 YYYYMMDD-HHMMSS 升序（不看 mtime）。"""
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.md"), key=lambda p: p.name)


def _meta_of(md: Path) -> dict:
    meta = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
    ts = meta.get("timestamp", "")
    return {
        "file": md.name,
        "path": str(md),
        "timestamp": ts,
        "display_time": ts.replace("T", " ")[:16] if ts else md.name[:15],
        "title": meta.get("title", md.stem),
        "status": meta.get("status", ""),
        "source_skill": meta.get("source_skill", ""),
        "next_skill": meta.get("next_skill", ""),
    }


def cmd_projects(args) -> None:
    root = resolve_root()
    base = root / SESSIONS_DIR
    projects = []
    if base.is_dir():
        for project_dir in sorted(p for p in base.iterdir() if p.is_dir()):
            files = _snapshot_files(project_dir)
            if not files:
                continue
            latest = _meta_of(files[-1])
            projects.append({"project": project_dir.name, "count": len(files),
                             "latest": latest["timestamp"], "latest_display": latest["display_time"]})
    projects.sort(key=lambda x: x["latest"], reverse=True)
    if args.json:
        print(json.dumps(projects, ensure_ascii=False, indent=2))
        return
    if not projects:
        print(f"存档位置没有任何项目：{base}")
        return
    for index, item in enumerate(projects, 1):
        print(f"{index}. {item['project']}（{item['count']} 份，最近 {item['latest_display']}）")


def cmd_latest(args) -> None:
    root = resolve_root()
    slug = project_slug(args.slug)
    files = _snapshot_files(root / SESSIONS_DIR / slug)
    if not files:
        die(f"项目 `{slug}` 下没有存档。")
    if args.index is not None:
        if args.index < 1 or args.index > len(files):
            die(f"项目 `{slug}` 下只有 {len(files)} 份存档，序号 {args.index} 超出范围。")
        chosen = files[args.index - 1]
    else:
        chosen = files[-1]
    meta = _meta_of(chosen)
    meta["slug"] = slug
    meta["body"] = chosen.read_text(encoding="utf-8", errors="replace")
    if args.json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        print(meta["path"])


def cmd_search(args) -> None:
    root = resolve_root()
    base = root / SESSIONS_DIR
    needle = args.query.lower()
    only_slug = project_slug(args.slug) if args.slug else None
    hits = []
    project_dirs = [base / only_slug] if only_slug else (
        [p for p in base.iterdir() if p.is_dir()] if base.is_dir() else []
    )
    for project_dir in project_dirs:
        for md in _snapshot_files(project_dir):
            text = md.read_text(encoding="utf-8", errors="replace")
            if needle not in text.lower():
                continue
            meta = _meta_of(md)
            meta["project"] = project_dir.name
            snippet = ""
            for line in text.splitlines():
                if needle in line.lower():
                    snippet = line.strip().lstrip("-# ").strip()[:80]
                    break
            meta["snippet"] = snippet
            hits.append(meta)
    hits.sort(key=lambda x: x["timestamp"], reverse=True)
    if args.json:
        print(json.dumps({"query": args.query, "count": len(hits), "items": hits},
                         ensure_ascii=False, indent=2))
        return
    if not hits:
        print(f"没有找到包含「{args.query}」的存档。")
        return
    print(f"找到 {len(hits)} 份包含「{args.query}」的存档：\n")
    for index, item in enumerate(hits, 1):
        status = STATUS_ZH.get(item["status"], item["status"] or "")
        extra = f" · {snippet}" if (snippet := item.get("snippet")) else ""
        print(f"{index}. [{item['project']}] {item['display_time']} · {item['title']} · {status}{extra}")


def _date_of(md: Path, meta: dict) -> str:
    """尽量取 ISO 时间戳的 YYYY-MM-DD，缺失时退回文件名前 8 位。"""
    ts = meta.get("timestamp", "")
    if len(ts) >= 10 and ts[4] == "-":
        return ts[:10]
    digits = md.name[:8]
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return ""


def cmd_collect(args) -> None:
    root = resolve_root()
    slug = project_slug(args.slug)
    files = _snapshot_files(root / SESSIONS_DIR / slug)
    items = []
    for md in files:
        meta = _meta_of(md)
        date = _date_of(md, meta)
        if args.since and date and date < args.since:
            continue
        meta["date"] = date
        meta["body"] = md.read_text(encoding="utf-8", errors="replace")
        items.append(meta)
    if args.json:
        print(json.dumps({"project": slug, "count": len(items), "items": items},
                         ensure_ascii=False, indent=2))
        return
    if not items:
        print(f"项目 `{slug}` 下没有可汇总的存档。")
        return
    for index, item in enumerate(items, 1):
        print(f"{index}. {item['date']} · {item['title']} · {item['status']}")


def cmd_report_path(args) -> None:
    root = resolve_root()
    slug = project_slug(args.slug)
    now = datetime.now().astimezone()
    compact = now.strftime("%Y%m%d-%H%M%S")
    directory = root / "reports" / slug
    directory.mkdir(parents=True, exist_ok=True)
    base = f"{compact}-{slug}.md"
    path = directory / base
    if path.exists():
        suffix = "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(4))
        path = directory / f"{compact}-{slug}-{suffix}.md"
    payload = {"path": str(path), "project": slug, "generated": now.isoformat(timespec="seconds")}
    print(json.dumps(payload, ensure_ascii=False) if args.json else str(path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="诊断存档确定性工具（save/restore/report 共用）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    sub = parser.add_subparsers(dest="command", required=True)

    p_root = sub.add_parser("resolve-root", help="解析当前存档根目录")
    p_root.set_defaults(func=cmd_resolve_root)

    p_slug = sub.add_parser("slug", help="生成项目 slug")
    p_slug.add_argument("--slug", help="显式指定项目名")
    p_slug.set_defaults(func=cmd_slug)

    p_new = sub.add_parser("new-path", help="生成新存档文件路径并创建目录")
    p_new.add_argument("--title", required=True, help="存档标题")
    p_new.add_argument("--slug", help="显式指定项目名")
    p_new.set_defaults(func=cmd_new_path)

    p_list = sub.add_parser("list", help="列出项目下存档")
    p_list.add_argument("project", nargs="?", help="项目名，缺省用当前目录")
    p_list.set_defaults(func=cmd_list)

    p_projects = sub.add_parser("projects", help="列出所有项目及最近活跃时间")
    p_projects.set_defaults(func=cmd_projects)

    p_latest = sub.add_parser("latest", help="取项目下最新或指定序号的存档")
    p_latest.add_argument("--slug", help="项目名，缺省用当前目录")
    p_latest.add_argument("--index", type=int, help="按 list 编号取第 N 份")
    p_latest.set_defaults(func=cmd_latest)

    p_search = sub.add_parser("search", help="跨存档全文搜索关键词")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--slug", help="只搜指定项目")
    p_search.set_defaults(func=cmd_search)

    p_collect = sub.add_parser("collect", help="按时间收集项目下全部存档（可 --since 过滤），含正文")
    p_collect.add_argument("--slug", help="项目名，缺省用当前目录")
    p_collect.add_argument("--since", help="只取该日期(YYYY-MM-DD)及之后的存档")
    p_collect.set_defaults(func=cmd_collect)

    p_report = sub.add_parser("report-path", help="生成永不覆盖的报告文件路径并建目录")
    p_report.add_argument("--slug", help="项目名，缺省用当前目录")
    p_report.set_defaults(func=cmd_report_path)
    return parser


def main() -> None:
    parser = build_parser()
    # 全局 --json 既可能在子命令前也可能在后，这里做一次归一
    argv = sys.argv[1:]
    if "--json" in argv:
        argv = [a for a in argv if a != "--json"]
        args = parser.parse_args(argv)
        args.json = True
    else:
        args = parser.parse_args(argv)
        args.json = False
    args.func(args)


if __name__ == "__main__":
    main()
