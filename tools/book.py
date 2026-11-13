"""가계부 원본(data/YYYY-MM.json)을 엑셀 칸 주소로 읽고 쓴다. 엑셀 rget/rset과 같은 방식.

  python tools/book.py get 26-11 Q14:Z15      # 칸 값 (행마다 리스트 한 줄, rget과 같은 모양)
  python tools/book.py set 26-11 U14=5000 V14=사유   # 금액 '?'는 미정, 빈 값('U14=')은 지우기
  python tools/book.py newmonth [27-01]        # 다음 달 파일 만들기 (newmonth.py와 같은 규칙)
  python tools/book.py dirty                   # 엑셀에 아직 안 옮긴 칸 목록

- 칸 구조는 각 달 파일의 layout([열, side, 분류])을 따른다. 금액 칸 오른쪽이 사유 칸.
- 행 = 일 + 2 (1일 → 3행). 2행·34행 등 날짜 밖 행은 날짜 없음.
- 금액/사유 칸 밖의 칸(I37·I38 포인트 메모 등)은 extra에 저장.
- 쓴 칸은 dirty 표시 → tools/push_excel.py가 2주마다 엑셀에 옮기고 지운다.
"""
import calendar, datetime, json, os, re, sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
REAL_DATE = re.compile(r"\((\d{1,2})\.(\d{1,2})\)\s*$")


def col_idx(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def col_name(i):
    s = ""
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def split_ref(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref.strip().upper())
    if not m:
        raise SystemExit(f"칸 주소가 이상함: {ref}")
    return m.group(1), int(m.group(2))


def sheet_to_month(sheet):
    m = re.fullmatch(r"(\d\d)-(\d\d)", sheet)
    if not m:
        raise SystemExit(f"시트 이름은 YY-MM: {sheet}")
    return f"20{m.group(1)}-{m.group(2)}"


def path_of(month):
    return os.path.join(DATA, month + ".json")


def load(sheet):
    p = path_of(sheet_to_month(sheet))
    if not os.path.exists(p):
        raise SystemExit(f"없는 달: {sheet} (newmonth로 먼저 만들 것)")
    return json.load(open(p, encoding="utf-8"))


def save(d):
    with open(path_of(d["month"]), "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, indent=1))
    idx_p = os.path.join(DATA, "index.json")
    idx = json.load(open(idx_p, encoding="utf-8"))
    if d["month"] not in idx["months"]:
        idx["months"] = sorted(idx["months"] + [d["month"]])
    idx["updated"] = datetime.datetime.now().isoformat(timespec="minutes")
    with open(idx_p, "w", encoding="utf-8") as f:
        f.write(json.dumps(idx, ensure_ascii=False, indent=1))


def maps(d):
    amount_cols = {c: (side, cat) for c, side, cat in d["layout"]}
    memo_cols = {col_name(col_idx(c) + 1): c for c in amount_cols}
    return amount_cols, memo_cols


def row_date(d, row):
    y, m = map(int, d["month"].split("-"))
    day = row - 2
    if 1 <= day <= calendar.monthrange(y, m)[1] and row <= 33:
        return datetime.date(y, m, day).isoformat()
    return None


def find(d, col, row):
    for e in d["entries"]:
        if e["col"] == col and e.get("row") == row:
            return e
    return None


def cell_value(d, col, row):
    amount_cols, memo_cols = maps(d)
    if col == "A":
        return row_date(d, row) or ""
    if col in amount_cols:
        e = find(d, col, row)
        if not e:
            return ""
        if isinstance(e.get("amount"), int):
            return e["amount"]
        return "?" if e.get("pending") else e.get("amountNote", "")
    if col in memo_cols:
        e = find(d, memo_cols[col], row)
        return (e or {}).get("memo", "")
    return d.get("extra", {}).get(f"{col}{row}", "")


def cmd_get(sheet, rng):
    d = load(sheet)
    a, b = (rng.split(":") + [rng])[:2]
    c1, r1 = split_ref(a)
    c2, r2 = split_ref(b)
    for r in range(r1, r2 + 1):
        print([cell_value(d, col_name(c), r) for c in range(col_idx(c1), col_idx(c2) + 1)])


def set_real_date(d, e):
    e.pop("realDate", None)
    m = REAL_DATE.search(e.get("memo") or "")
    if m:
        y, mo = map(int, d["month"].split("-"))
        rm, rd = int(m.group(1)), int(m.group(2))
        ry = y - 1 if rm > mo + 6 else y + 1 if rm < mo - 6 else y
        try:
            e["realDate"] = datetime.date(ry, rm, rd).isoformat()
        except ValueError:
            pass


def cmd_set(sheet, pairs):
    d = load(sheet)
    amount_cols, memo_cols = maps(d)
    done = []
    for pair in pairs:
        ref, val = pair.split("=", 1)
        col, row = split_ref(ref)
        val = val.strip()
        if col in amount_cols or col in memo_cols:
            acol = col if col in amount_cols else memo_cols[col]
            e = find(d, acol, row)
            if e is None:
                if val == "":
                    continue
                side, cat = amount_cols[acol]
                e = {"date": row_date(d, row), "side": side, "cat": cat, "col": acol, "row": row}
                if e["date"] is None:
                    e["undated"] = True
                d["entries"].append(e)
            if col == acol:
                for k in ("amount", "pending", "amountNote"):
                    e.pop(k, None)
                if re.fullmatch(r"-?\d+", val):
                    e["amount"] = int(val)
                elif val == "?":
                    e["amount"], e["pending"] = None, True
                elif val:
                    e["amount"], e["amountNote"] = None, val
                else:
                    e["amount"] = None
            else:
                if val:
                    e["memo"] = val
                else:
                    e.pop("memo", None)
                set_real_date(d, e)
            e["dirty"] = True
            dc = e.setdefault("dirtyCells", [])  # 엑셀에는 실제로 바꾼 칸만 쓴다 (가린 사유 보호)
            if f"{col}{row}" not in dc:
                dc.append(f"{col}{row}")
            if e.get("amount") is None and not e.get("pending") and not e.get("amountNote") and not e.get("memo"):
                d["entries"].remove(e)
                d.setdefault("cleared", []).append([acol, row])  # 엑셀에서도 지울 칸
        else:
            d.setdefault("extra", {})[f"{col}{row}"] = val
            dirty = d.setdefault("extraDirty", [])
            if f"{col}{row}" not in dirty:
                dirty.append(f"{col}{row}")
        done.append(f"{col}{row}")
    save(d)
    print(f"OK {d['month']}: {', '.join(done)}")


INSTALL = re.compile(r"\((\d+)/(\d+)\)")


def cmd_newmonth(target=None):
    months = sorted(f[:-5] for f in os.listdir(DATA) if re.fullmatch(r"\d{4}-\d\d\.json", f))
    src = json.load(open(path_of(months[-1]), encoding="utf-8"))
    y, m = map(int, src["month"].split("-"))
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    month = f"{ny}-{nm:02d}"
    if target and sheet_to_month(target) != month:
        raise SystemExit(f"최신 달({src['month']}) 다음은 {month}")
    if os.path.exists(path_of(month)):
        raise SystemExit(f"이미 있음: {month}")
    # 엑셀 쪽은 newmonth_remote.py(newmonth.py)가 같은 규칙으로 시트를 만드니 여기선 dirty 표시 안 함
    new = {"month": month, "sheet": f"{ny % 100:02d}-{nm:02d}", "layout": src["layout"], "entries": [],
           "extra": {"I37": "N포인트 적립 +0", "I38": "N포인트 사용 -0"}}
    days = calendar.monthrange(ny, nm)[1]
    for e in src["entries"]:
        memo = e.get("memo") or ""
        keep = None
        if e.get("fixed"):
            keep = dict(e)
            if "관리비" in memo:
                keep["memo"] = re.sub(r"\d+월관리비", f"{m}월관리비", memo)
                keep.pop("amount", None); keep.pop("amountNote", None)
                keep["amount"], keep["pending"] = None, True
        else:
            im = INSTALL.search(memo)
            if im and int(im.group(1)) < int(im.group(2)):
                keep = dict(e)
                keep["memo"] = memo.replace(im.group(0), f"({int(im.group(1)) + 1}/{im.group(2)})")
        if keep is None:
            continue
        row = keep["row"]
        keep["date"] = datetime.date(ny, nm, row - 2).isoformat() if 3 <= row <= 33 and row - 2 <= days else None
        if keep["date"] is None:
            keep["undated"] = True
        else:
            keep.pop("undated", None)
        keep.pop("realDate", None)
        keep.pop("dirty", None); keep.pop("dirtyCells", None)
        new["entries"].append(keep)
    new["newSheet"] = True  # 엑셀에 아직 시트 없음 → push_excel이 newmonth_remote.py로 만든다
    save(new)
    print(f"{src['month']} -> {month}: {len(new['entries'])}칸 이어받음")


def cmd_dirty():
    for f in sorted(os.listdir(DATA)):
        if not re.fullmatch(r"\d{4}-\d\d\.json", f):
            continue
        d = json.load(open(os.path.join(DATA, f), encoding="utf-8"))
        cells = [f"{e['col']}{e['row']}" for e in d["entries"] if e.get("dirty")]
        cells += [f"{c}{r}(지움)" for c, r in d.get("cleared", [])] + d.get("extraDirty", [])
        if cells or d.get("newSheet"):
            print(d["sheet"], ("새 시트 " if d.get("newSheet") else "") + " ".join(cells))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "get":
        cmd_get(args[0], args[1])
    elif cmd == "set":
        cmd_set(args[0], args[1:])
    elif cmd == "newmonth":
        cmd_newmonth(args[0] if args else None)
    elif cmd == "dirty":
        cmd_dirty()
    else:
        print(__doc__)
