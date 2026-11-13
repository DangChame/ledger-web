# 가계부 웹

휴대폰·아이패드·노트북에서 보는 가계부 화면. 서버 없이 GitHub Pages에서 `data/*.json`을 읽어 그린다.

- `index.html`, `style.css`, `app.js`: 화면 (한 번 만들고 거의 안 바뀜)
- `data/YYYY-MM.json`: 월별 내역, `data/index.json`: 달 목록·마지막 갱신 시각
- `tools/import_xlsx.py`: 기존 엑셀(월 시트 `YY-MM`) → JSON 변환. 휴대폰 번호는 가리고, 수입은 `--with-income` 없이는 넣지 않는다

내역 한 줄: `date`(칸이 있는 날짜), `realDate`(사유의 `(11.5)` 실제 결제일), `side`(`me` 내 돈 / `mom` 엄마카드), `cat`, `amount`, `memo`, `fixed`(회색 고정지출), `pending`(금액 `?`).

공개 범위: `data/index.json`의 `visibleFrom`(지금 `2026-08`)부터만 올린다. 그 이전 달 JSON은 `archive/data/`(서피스에만 있음, `.gitignore`)에 보관.
범위를 넓히려면 `visibleFrom`을 바꾸고 `archive/data/`에서 해당 달 파일을 `data/`로 옮긴 뒤 `python tools/import_xlsx.py <엑셀> --since YY-MM`, 그리고 `tools/sync.ps1`의 `$Since`도 같이 바꾼다.

로컬 확인: `python -m http.server 8765 --bind 127.0.0.1` → http://127.0.0.1:8765
