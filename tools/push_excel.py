"""data/*.json(원본)에서 엑셀에 아직 안 옮긴 칸(dirty)을 OneDrive 엑셀에 쓴다. 2주마다 작업 스케줄러가 실행.

  python tools/push_excel.py [--dry]

- 새 달(newSheet)이면 먼저 account-book/newmonth_remote.py로 엑셀 시트를 만든다.
- 칸 값은 JSON 그대로 덮어쓴다 (원본은 JSON). 성공한 칸만 dirty를 지운다.
- 엑셀 오류(장애 등)면 그대로 두고 다음 번에 다시 시도.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
LEDGER = os.path.normpath(os.path.join(HERE, "..", "..", "account-book"))
sys.path.insert(0, LEDGER)
sys.path.insert(0, HERE)
import book  # noqa: E402


def plan(d):
    _, memo_cols = book.maps(d)
    memo_of = {a: m for m, a in memo_cols.items()}
    ups = {}
    for e in d["entries"]:
        if not e.get("dirty"):
            continue
        c, r = e["col"], e["row"]
        cells = e.get("dirtyCells") or [f"{c}{r}", f"{memo_of[c]}{r}"]
        if f"{c}{r}" in cells:
            if isinstance(e.get("amount"), int):
                ups[f"{c}{r}"] = e["amount"]
            else:
                ups[f"{c}{r}"] = "?" if e.get("pending") else e.get("amountNote", "")
        if f"{memo_of[c]}{r}" in cells:
            ups[f"{memo_of[c]}{r}"] = e.get("memo", "")
    for c, r in d.get("cleared", []):
        ups[f"{c}{r}"] = ""
        ups[f"{memo_of[c]}{r}"] = ""
    for ref in d.get("extraDirty", []):
        ups[ref] = d.get("extra", {}).get(ref, "")
    return ups


def main():
    dry = "--dry" in sys.argv
    files = sorted(f for f in os.listdir(DATA) if re.fullmatch(r"\d{4}-\d\d\.json", f))
    todo = []
    for f in files:
        d = json.load(open(os.path.join(DATA, f), encoding="utf-8"))
        ups = plan(d)
        if ups or d.get("newSheet"):
            todo.append((d, ups))
    if not todo:
        print("엑셀 반영: 옮길 칸 없음")
        return
    for d, ups in todo:
        print(f"{d['sheet']}: {'새 시트, ' if d.get('newSheet') else ''}{len(ups)}칸")
    if dry:
        for d, ups in todo:
            print(d["sheet"], ups)
        return
    import ledger  # account-book/ledger.py (Graph)
    if any(d.get("newSheet") for d, _ in todo):
        out = subprocess.run([sys.executable, os.path.join(LEDGER, "newmonth_remote.py")],
                             capture_output=True, text=True, cwd=LEDGER)
        print("새 시트:", (out.stdout or out.stderr).strip()[-200:])
        if out.returncode != 0:
            raise SystemExit("엑셀 새 시트 만들기 실패 → 다음 번에 다시")
    ok_total = 0
    for d, ups in todo:
        try:
            if ups:
                ledger.remote_set(d["sheet"], ups)
        except SystemExit as e:
            print(f"{d['sheet']} 엑셀 쓰기 실패: {str(e)[:200]} → 다음 번에 다시")
            continue
        for e in d["entries"]:
            e.pop("dirty", None)
            e.pop("dirtyCells", None)
        for k in ("cleared", "extraDirty", "newSheet"):
            d.pop(k, None)
        with open(book.path_of(d["month"]), "w", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False, indent=1))
        ok_total += len(ups)
        print(f"{d['sheet']}: {len(ups)}칸 엑셀 반영")
    print(f"엑셀 반영 끝: {ok_total}칸")


if __name__ == "__main__":
    main()
