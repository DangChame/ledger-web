"""가계부 xlsx → data/YYYY-MM.json 변환 (월 시트 'YY-MM'만).

사용: python tools/import_xlsx.py <ledger.xlsx> [--out data] [--only 26-11,26-10] [--with-income]

- 1행 제목으로 칸을 읽는다: 바로 오른쪽 칸 제목이 '사유'면 금액 칸.
- '일지출'/'엄마카드'/'하루 총합' 제목 또는 사유 짝이 없는 빈 제목 칸을 경계로 왼쪽=내 돈, 오른쪽=엄마카드.
- 회색 칸(theme 6, tint 0.6) = 고정지출.
- 사유 끝의 '(11.5)' = 실제 결제일 → realDate.
- 금액이 '?'면 pending, 그 밖의 글자면 amountNote.
- 휴대폰 번호는 가린다. 수입(용돈 등)은 --with-income일 때만 넣는다.
"""
import argparse, datetime, json, os, re, sys
import openpyxl

PHONE = re.compile(r"01[016789]-?\d{3,4}-?\d{4}")
REAL_DATE = re.compile(r"\((\d{1,2})\.(\d{1,2})\)\s*$")
SHEET = re.compile(r"^(\d\d)-(\d\d)$")


# 시트 합계 수식이 칸 구분과 다르게 센 경우 (시트명: [(열, 첫 행, 끝 행, side)])
SIDE_OVERRIDE = {
    "19-09": [("O", 19, 34, "me")],  # B35 수식이 O19:O34를 내 지출로 셈
}


def mask(s):
    return PHONE.sub("휴대폰 회선", s) if isinstance(s, str) else s


def is_fixed(cell):
    f = cell.fill
    if f is None or f.fill_type is None:
        return False
    fg = f.fgColor
    return fg.type == "theme" and fg.theme == 6 and round(fg.tint or 0, 1) == 0.6


def layout(ws):
    hdr = {c: ws.cell(1, c).value for c in range(1, ws.max_column + 2)}
    cols, side = [], "me"
    for c in range(2, ws.max_column + 1):
        h = hdr[c]
        h = h.strip() if isinstance(h, str) else h
        nxt = hdr.get(c + 1)
        if h in ("일지출", "엄마카드", "하루 총합"):
            side = "mom"
            continue
        if h == "사유":
            continue
        if nxt == "사유":
            name = h or ("데이트" if side == "me" else "기타")
            cols.append((c, side, name))
        elif h is None and side == "me" and cols:
            side = "mom"  # 24-06처럼 제목 없는 구분 칸
    return cols


def find_label_value(ws, label, last_row):
    for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, last_row + 15)):
        for c in row:
            if isinstance(c.value, str) and c.value.strip() == label:
                return ws.cell(c.row, c.column + 1).value
    return None


def convert(ws, wv, name):
    yy, mm = SHEET.match(name).groups()
    year, month = 2000 + int(yy), int(mm)
    cols = layout(ws)
    # 데이터 행: 3행부터 A열이 '지출합'인 행 직전까지
    end = ws.max_row
    for r in range(3, ws.max_row + 1):
        if isinstance(ws.cell(r, 1).value, str) and ws.cell(r, 1).value.strip() == "지출합":
            end = r - 1
            break
    entries, warn = [], []
    for r in range(2, end + 1):  # 2행(날짜 제목 줄)에 적힌 지출도 있다 → 날짜 없음으로
        dv = ws.cell(r, 1).value
        day = dv.date().isoformat() if isinstance(dv, datetime.datetime) else None
        for c, side, cat in cols:
            cell, memo_cell = ws.cell(r, c), ws.cell(r, c + 1)
            v = wv.cell(r, c).value  # 수식이면 계산값
            memo = memo_cell.value
            if v in (None, "") and memo in (None, ""):
                continue
            s = side
            for col, r0, r1, ov in SIDE_OVERRIDE.get(name, []):
                if cell.column_letter == col and r0 <= r <= r1:
                    s = ov
            e = {"date": day, "side": s, "cat": cat, "col": cell.column_letter, "row": r}
            if isinstance(v, (int, float)):
                e["amount"] = int(round(v))
            elif isinstance(v, str) and v.strip() == "?":
                e["amount"], e["pending"] = None, True
            elif v in (None, ""):
                if memo in (None, ""):
                    continue
                e["amount"] = None  # 사유만 있는 칸
            else:
                e["amount"], e["amountNote"] = None, mask(str(v))
            if memo not in (None, ""):
                m = mask(str(memo).strip())
                e["memo"] = m
                rd = REAL_DATE.search(m)
                if rd:
                    rm, rdd = int(rd.group(1)), int(rd.group(2))
                    ry = year - 1 if rm > month + 6 else year + 1 if rm < month - 6 else year
                    try:
                        e["realDate"] = datetime.date(ry, rm, rdd).isoformat()
                    except ValueError:
                        warn.append(f"{name}!{memo_cell.coordinate} 날짜 해석 실패: {m}")
            if is_fixed(cell) or is_fixed(memo_cell):
                e["fixed"] = True
            if day is None:
                e["undated"] = True
            entries.append(e)
    out = {"month": f"{year}-{month:02d}", "sheet": name, "entries": entries}
    # 검증용 시트 합계
    me_total = find_label_value(wv, "내 지출합", end)
    mom_total = find_label_value(wv, "엄마카드지출", end)
    calc_me = sum(e["amount"] or 0 for e in entries if e["side"] == "me")
    calc_mom = sum(e["amount"] or 0 for e in entries if e["side"] == "mom")
    out["sheetTotals"] = {"me": me_total if isinstance(me_total, (int, float)) else None,
                          "mom": mom_total if isinstance(mom_total, (int, float)) else None}
    for k, a, b in (("me", calc_me, me_total), ("mom", calc_mom, mom_total)):
        if isinstance(b, (int, float)) and int(round(b)) != a:
            warn.append(f"{name} {k} 합계 다름: 계산 {a:,} / 시트 {int(round(b)):,}")
    return out, warn, end


def income(ws, wv, end):
    """'수입' 라벨 아래 금액(F)·내용(G) 쌍."""
    items = []
    for r in range(end + 1, min(ws.max_row, end + 20) + 1):
        for c in range(1, ws.max_column):
            v, lab = wv.cell(r, c).value, wv.cell(r, c + 1).value
            if isinstance(v, (int, float)) and isinstance(lab, str) and lab.strip() and not lab.startswith("N포인트"):
                if ws.cell(r, c).column_letter in ("F",):
                    items.append({"amount": int(v), "label": mask(lab.strip())})
    return items


def apply_overlay(data, pend, sheet_name):
    """엑셀에 아직 못 쓴 기록(pending_writes.json)을 화면용 데이터에 덮어쓴다."""
    for it in pend:
        if it.get("sheet") != sheet_name:
            continue
        cells = it.get("cells", {})
        for coord, val in cells.items():
            col = re.match(r"[A-Z]+", coord).group(0)
            row = int(coord[len(col):])
            if isinstance(val, str):
                continue  # 사유 칸은 금액 칸과 함께 처리
            memo_col = openpyxl.utils.get_column_letter(openpyxl.utils.column_index_from_string(col) + 1)
            memo = cells.get(f"{memo_col}{row}")
            hit = [e for e in data["entries"] if e["col"] == col and e.get("row") == row]
            for e in hit:
                e["amount"] = int(val)
                e.pop("pending", None)
                if memo:
                    e["memo"] = memo
                e["unsynced"] = True  # 엑셀에는 아직 안 들어감


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--only")
    ap.add_argument("--since", help="이 달(YY-MM) 이후 시트만 변환, 예: 26-08")
    ap.add_argument("--with-income", action="store_true")
    ap.add_argument("--overlay", default=os.path.expanduser("~/.config/ledger/pending_writes.json"),
                    help="엑셀에 아직 못 쓴 기록 파일 (있으면 화면 데이터에 반영)")
    a = ap.parse_args()
    pend = json.load(open(a.overlay, encoding="utf-8")) if a.overlay and os.path.exists(a.overlay) else []
    wb = openpyxl.load_workbook(a.xlsx)
    wbv = openpyxl.load_workbook(a.xlsx, data_only=True)
    names = [n for n in wb.sheetnames if SHEET.match(n)]
    if a.only:
        names = [n for n in names if n in a.only.split(",")]
    if a.since:
        names = [n for n in names if n >= a.since]
    os.makedirs(a.out, exist_ok=True)
    months, allwarn, changed = [], [], []
    for n in names:
        data, warn, end = convert(wb[n], wbv[n], n)
        if a.with_income:
            data["income"] = income(wb[n], wbv[n], end)
        apply_overlay(data, pend, n)
        allwarn += warn
        if not data["entries"]:
            allwarn.append(f"{n}: 내역 없음, 건너뜀")
            continue
        path = os.path.join(a.out, data["month"] + ".json")
        text = json.dumps(data, ensure_ascii=False, indent=1)
        old_text = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        if text != old_text:  # 바뀐 달만 쓴다 → 변화 없으면 커밋도 없음
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            changed.append(data["month"])
        months.append(data["month"])
    idx_path = os.path.join(a.out, "index.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    allm = sorted(set(idx.get("months", [])) | set(months))
    if idx.get("visibleFrom"):  # 공개 범위 밖 달은 목록에도 안 올린다
        allm = [m for m in allm if m >= idx["visibleFrom"]]
    if changed or allm != idx.get("months"):
        idx["months"] = allm
        idx["updated"] = datetime.datetime.now().isoformat(timespec="minutes")
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=1)
    print(f"{len(months)}개월 확인, 바뀐 달: {', '.join(changed) or '없음'}")
    for w in allwarn:
        print("WARN", w)


if __name__ == "__main__":
    main()
