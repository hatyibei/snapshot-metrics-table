"""metrics_table.py のテスト（すべて架空データ）。

実行: python3 -m unittest
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import metrics_table as mt  # noqa: E402

SCRIPT = os.path.join(ROOT, "metrics_table.py")
HEADER = (
    "snapshot_at,snapshot_type,url,platform,title,theme,published_at,"
    "likes,stocks_or_bookmarks,pv,comments\n"
)


def write_csv(testcase, body):
    """HEADER + body を一時ファイルに書いてパスを返す。"""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(HEADER + body)
    testcase.addCleanup(os.remove, path)
    return path


def run_rows(testcase, body):
    """CSV を読んで build_rows の結果と stderr を返す。"""
    path = write_csv(testcase, body)
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rows = mt.build_rows(mt.load(path))
    return rows, err.getvalue()


def run_cli(*args):
    return subprocess.run(
        [sys.executable, SCRIPT, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class LatestSnapshotTest(unittest.TestCase):
    def test_latest_snapshot_at_wins(self):
        rows, _ = run_rows(self, (
            "2026-01-08T00:00:00Z,7d,https://example.com/a,blog,T,x,2026-01-01T00:00:00Z,10,0,100,0\n"
            "2026-01-09T00:00:00Z,7d,https://example.com/a,blog,T,x,2026-01-01T00:00:00Z,30,0,300,0\n"
            "2026-01-07T00:00:00Z,7d,https://example.com/a,blog,T,x,2026-01-01T00:00:00Z,20,0,200,0\n"
        ))
        self.assertEqual(rows[0][4:], ["30", "300"])

    def test_z_and_plus0900_are_compared_as_instants(self):
        # 2026-01-08T10:00+09:00 は 01:00Z。02:00Z の方が新しい。
        rows, _ = run_rows(self, (
            "2026-01-08T02:00:00Z,7d,https://example.com/a,blog,T,x,,11,0,,0\n"
            "2026-01-08T10:00:00+09:00,7d,https://example.com/a,blog,T,x,,22,0,,0\n"
        ))
        self.assertEqual(rows[0][4], "11")
        # 逆: +09:00 側が新しい（12:00+09:00 = 03:00Z）
        rows, _ = run_rows(self, (
            "2026-01-08T12:00:00+09:00,7d,https://example.com/a,blog,T,x,,33,0,,0\n"
            "2026-01-08T02:00:00Z,7d,https://example.com/a,blog,T,x,,44,0,,0\n"
        ))
        self.assertEqual(rows[0][4], "33")

    def test_dated_row_beats_empty_snapshot_at(self):
        for body in (
            ",24h,https://example.com/a,blog,T,x,,1,0,,0\n"
            "2026-01-02T00:00:00Z,24h,https://example.com/a,blog,T,x,,2,0,,0\n",
            "2026-01-02T00:00:00Z,24h,https://example.com/a,blog,T,x,,2,0,,0\n"
            ",24h,https://example.com/a,blog,T,x,,1,0,,0\n",
        ):
            rows, _ = run_rows(self, body)
            self.assertEqual(rows[0][3], "2")

    def test_types_are_independent(self):
        rows, _ = run_rows(self, (
            "2026-01-01T00:00:00Z,initial,https://example.com/a,blog,T,x,,1,0,,0\n"
            "2026-01-02T00:00:00Z,24h,https://example.com/a,blog,T,x,,2,0,,0\n"
            "2026-01-08T00:00:00Z,7d,https://example.com/a,blog,T,x,,3,0,40,0\n"
        ))
        self.assertEqual(rows, [["blog", "T", "1", "2", "3", "40"]])


class IgnoredRowsTest(unittest.TestCase):
    def test_unknown_snapshot_type_warns_and_is_ignored(self):
        rows, err = run_rows(self, (
            "2026-01-01T00:00:00Z,initial,https://example.com/a,blog,T,x,,1,0,,0\n"
            "2026-01-09T00:00:00Z,monthly,https://example.com/a,blog,T,x,,999,0,999,0\n"
        ))
        self.assertIn("monthly", err)
        self.assertIn("警告", err)
        self.assertEqual(rows, [["blog", "T", "1", "-", "-", "-"]])

    def test_empty_url_rows_are_ignored(self):
        rows, err = run_rows(self, (
            "2026-01-01T00:00:00Z,initial,,blog,No URL,x,,5,0,,0\n"
            "2026-01-01T00:00:00Z,initial,   ,blog,Spaces only,x,,6,0,,0\n"
            "2026-01-01T00:00:00Z,initial,https://example.com/a,blog,T,x,,1,0,,0\n"
        ))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "T")
        self.assertEqual(err, "")


class MissingValueTest(unittest.TestCase):
    def test_empty_likes_and_pv_become_dash(self):
        rows, _ = run_rows(self, (
            "2026-01-01T00:00:00Z,initial,https://example.com/a,blog,T,x,,,0,,0\n"
            "2026-01-02T00:00:00Z,24h,https://example.com/a,blog,T,x,,  ,0,,0\n"
            "2026-01-08T00:00:00Z,7d,https://example.com/a,blog,T,x,,,0,,0\n"
        ))
        self.assertEqual(rows[0][2:], ["-", "-", "-", "-"])

    def test_missing_snapshot_becomes_dash(self):
        rows, _ = run_rows(self, (
            "2026-01-08T00:00:00Z,7d,https://example.com/a,,,x,,7,0,70,0\n"
        ))
        # platform / title が空なら「-」、initial / 24h が無ければ「-」
        self.assertEqual(rows, [["-", "-", "-", "-", "7", "70"]])


class OrderTest(unittest.TestCase):
    def test_published_at_desc_and_unreadable_last(self):
        rows, _ = run_rows(self, (
            "2026-01-01T00:00:00Z,initial,https://example.com/old,blog,Old,x,2026-01-01T00:00:00Z,1,0,,0\n"
            "2026-01-01T00:00:00Z,initial,https://example.com/bad,blog,Bad,x,not-a-date,1,0,,0\n"
            "2026-01-01T00:00:00Z,initial,https://example.com/new,blog,New,x,2026-03-01T09:00:00+09:00,1,0,,0\n"
            "2026-01-01T00:00:00Z,initial,https://example.com/none,blog,None,x,,1,0,,0\n"
            "2026-01-01T00:00:00Z,initial,https://example.com/mid,blog,Mid,x,2026-02-01T00:00:00Z,1,0,,0\n"
        ))
        titles = [r[1] for r in rows]
        self.assertEqual(titles[:3], ["New", "Mid", "Old"])
        self.assertCountEqual(titles[3:], ["Bad", "None"])

    def test_timezone_aware_ordering(self):
        # 2026-02-01T08:00+09:00 (= 前日 23:00Z) は 2026-01-31T23:30Z より古い
        rows, _ = run_rows(self, (
            "2026-02-02T00:00:00Z,initial,https://example.com/jst,blog,JST,x,2026-02-01T08:00:00+09:00,1,0,,0\n"
            "2026-02-02T00:00:00Z,initial,https://example.com/utc,blog,UTC,x,2026-01-31T23:30:00Z,1,0,,0\n"
        ))
        self.assertEqual([r[1] for r in rows], ["UTC", "JST"])


class TitleTest(unittest.TestCase):
    def test_whitespace_collapsed(self):
        rows, _ = run_rows(self, (
            '2026-01-01T00:00:00Z,initial,https://example.com/a,blog,"  Fake \t title\n  with   gaps  ",x,,1,0,,0\n'
        ))
        self.assertEqual(rows[0][1], "Fake title with gaps")

    def test_first_30_chars_python_slice(self):
        long_title = "あいうえおかきくけこ" * 4 + "abc"  # 43 文字
        rows, _ = run_rows(self, (
            f"2026-01-01T00:00:00Z,initial,https://example.com/a,blog,{long_title},x,,1,0,,0\n"
        ))
        self.assertEqual(rows[0][1], long_title[:30])
        self.assertEqual(len(rows[0][1]), 30)

    def test_first_nonempty_title_is_used(self):
        rows, _ = run_rows(self, (
            "2026-01-01T00:00:00Z,initial,https://example.com/a,,,x,,1,0,,0\n"
            "2026-01-02T00:00:00Z,24h,https://example.com/a,blog,Later Title,x,,2,0,,0\n"
        ))
        self.assertEqual(rows[0][:2], ["blog", "Later Title"])


class RenderTest(unittest.TestCase):
    def test_east_asian_width_alignment(self):
        rows = [
            ["blog", "全角タイトル（テスト）", "1", "22", "333", "4444"],
            ["wiki", "ascii title", "-", "-", "-", "-"],
            ["blog", "ﾊﾝｶｸｶﾅとＡＢＣ", "10", "-", "5", "-"],
        ]
        lines = mt.render(rows).split("\n")
        self.assertEqual(len(lines), 5)
        # 区切り " | " の表示上の位置が全行で一致すること
        def bar_positions(line, sep="|"):
            pos, out = 0, []
            for ch in line:
                if ch in (sep, "+"):
                    out.append(pos)
                pos += mt.display_width(ch)
            return out

        expected = bar_positions(lines[0])
        self.assertEqual(len(expected), 5)
        for line in lines[1:]:
            self.assertEqual(bar_positions(line), expected, line)
        # 数値列は右寄せ、最終列は行末に揃う
        self.assertTrue(lines[2].endswith("4444"))
        self.assertTrue(lines[4].endswith("    -"))

    def test_display_width(self):
        self.assertEqual(mt.display_width("abc"), 3)
        self.assertEqual(mt.display_width("あいう"), 6)
        self.assertEqual(mt.display_width("ＡＢ"), 4)
        self.assertEqual(mt.display_width("ｱｲ"), 2)

    def test_header(self):
        first = mt.render([]).split("\n")[0]
        self.assertEqual(
            [c.strip() for c in first.split("|")],
            ["platform", "title", "initial likes", "24h likes", "7d likes", "7d pv"],
        )


class ParseDtTest(unittest.TestCase):
    def test_z_equals_utc_offset(self):
        self.assertEqual(
            mt.parse_dt("2026-01-01T00:00:00Z"),
            mt.parse_dt("2026-01-01T09:00:00+09:00"),
        )

    def test_unreadable_and_empty(self):
        self.assertIsNone(mt.parse_dt(""))
        self.assertIsNone(mt.parse_dt(None))
        self.assertIsNone(mt.parse_dt("yesterday"))

    def test_naive_is_treated_as_utc(self):
        self.assertEqual(
            mt.parse_dt("2026-01-01T00:00:00"),
            mt.parse_dt("2026-01-01T00:00:00Z"),
        )


class CliTest(unittest.TestCase):
    def test_no_args_exit_2(self):
        r = run_cli()
        self.assertEqual(r.returncode, 2)
        self.assertIn("使い方", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_too_many_args_exit_2(self):
        r = run_cli("a.csv", "b.csv")
        self.assertEqual(r.returncode, 2)

    def test_missing_file_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_cli(os.path.join(d, "does-not-exist.csv"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("エラー", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_directory_exit_1(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_cli(d)
        self.assertEqual(r.returncode, 1)

    def test_example_csv_runs(self):
        r = run_cli(os.path.join(ROOT, "examples", "sample_metrics.csv"))
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.rstrip("\n").split("\n")
        self.assertEqual(len(lines), 2 + 3)
        self.assertIn("weekly", r.stderr)
        # 公開日不明の記事は末尾
        self.assertIn("公開日不明", lines[-1])

    def test_bom_csv(self):
        path = write_csv(self, "")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write(HEADER + "2026-01-01T00:00:00Z,initial,https://example.com/a,blog,T,x,,1,0,,0\n")
        r = run_cli(path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("blog", r.stdout.split("\n")[2])


if __name__ == "__main__":
    unittest.main()
