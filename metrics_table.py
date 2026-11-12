#!/usr/bin/env python3
"""記事ごとの likes / pv 推移を表にして標準出力に出す。

使い方: python3 metrics_table.py <CSVのパス>

入力列: snapshot_at,snapshot_type,url,platform,title,theme,published_at,
        likes,stocks_or_bookmarks,pv,comments
出力列: platform | タイトル先頭30文字 | initial likes | 24h likes | 7d likes | 7d pv
並び順: published_at の新しい順。値がないところは「-」。
同じ url・同じ snapshot_type の行が複数ある場合は snapshot_at が最も新しい行を使う。
"""
import csv
import sys
import unicodedata
from datetime import datetime, timezone

SNAPSHOT_TYPES = ("initial", "24h", "7d")
MISSING = "-"
TITLE_LEN = 30


def parse_dt(value):
    """ISO 8601 文字列を datetime に。読めなければ None。"""
    value = (value or "").strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def cell(value):
    value = (value or "").strip()
    return value if value else MISSING


def display_width(text):
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def pad(text, width):
    return text + " " * (width - display_width(text))


def load(path):
    articles = {}  # url -> {"platform", "title", "published_at", "snaps": {type: (snapshot_at, row)}}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("url") or "").strip()
            stype = (row.get("snapshot_type") or "").strip()
            if not url:
                continue
            art = articles.setdefault(
                url, {"platform": "", "title": "", "published_at": "", "snaps": {}}
            )
            # メタ情報は空でない値で埋める
            for key in ("platform", "title", "published_at"):
                v = (row.get(key) or "").strip()
                if v and not art[key]:
                    art[key] = v
            if stype not in SNAPSHOT_TYPES:
                print(f"警告: 不明な snapshot_type {stype!r} を無視しました ({url})", file=sys.stderr)
                continue
            snap_at = parse_dt(row.get("snapshot_at"))
            prev = art["snaps"].get(stype)
            if prev is None or (snap_at is not None and (prev[0] is None or snap_at >= prev[0])):
                art["snaps"][stype] = (snap_at, row)
    return articles


def build_rows(articles):
    rows = []
    for url, art in articles.items():
        snaps = art["snaps"]

        def get(stype, col):
            snap = snaps.get(stype)
            return cell(snap[1].get(col)) if snap else MISSING

        title = " ".join(art["title"].split())[:TITLE_LEN] or MISSING
        rows.append((
            parse_dt(art["published_at"]),
            [
                art["platform"] or MISSING,
                title,
                get("initial", "likes"),
                get("24h", "likes"),
                get("7d", "likes"),
                get("7d", "pv"),
            ],
        ))
    # published_at の新しい順。日時が読めない記事は末尾。
    min_dt = datetime.min.replace(tzinfo=timezone.utc)
    rows.sort(key=lambda r: (r[0] is not None, r[0] or min_dt), reverse=True)
    return [r[1] for r in rows]


def render(rows):
    header = ["platform", "title", "initial likes", "24h likes", "7d likes", "7d pv"]
    numeric = [False, False, True, True, True, True]
    widths = [display_width(h) for h in header]
    for r in rows:
        widths = [max(w, display_width(c)) for w, c in zip(widths, r)]

    def fmt(r):
        parts = []
        for c, w, num in zip(r, widths, numeric):
            parts.append(" " * (w - display_width(c)) + c if num else pad(c, w))
        return " | ".join(parts).rstrip()

    lines = [fmt(header), "-+-".join("-" * w for w in widths)]
    lines.extend(fmt(r) for r in rows)
    return "\n".join(lines)


def main(argv):
    if len(argv) != 2:
        print("使い方: python3 metrics_table.py <CSVのパス>", file=sys.stderr)
        return 2
    try:
        articles = load(argv[1])
    except OSError as e:
        print(f"エラー: CSV を開けません: {e}", file=sys.stderr)
        return 1
    print(render(build_rows(articles)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
