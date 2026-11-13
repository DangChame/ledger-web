(() => {
  const $ = (s) => document.querySelector(s);
  const won = (n) => (n < 0 ? "-" : "") + Math.abs(n).toLocaleString("ko-KR") + "원";
  const WD = ["일", "월", "화", "수", "목", "금", "토"];
  const SIDE = { me: "내 돈", mom: "엄마카드" };
  const cache = {};
  const st = { months: [], i: 0, side: "all", cat: null, q: "" };

  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };

  async function load(path) {
    if (cache[path]) return cache[path];
    const r = await fetch(path, { cache: "no-cache" });
    if (!r.ok) throw new Error(path + " " + r.status);
    return (cache[path] = await r.json());
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  const dayOf = (e) => e.realDate || e.date;

  async function render() {
    const m = st.months[st.i];
    const [y, mo] = m.split("-");
    $("#title").textContent = `${y}년 ${+mo}월`;
    $("#prev").disabled = st.i <= 0;
    $("#next").disabled = st.i >= st.months.length - 1;
    history.replaceState(null, "", "#" + m);

    let data;
    try { data = await load(`data/${m}.json`); }
    catch (err) { $("#days").innerHTML = `<p class="empty">불러오지 못했어요 (${esc(err.message)})</p>`; return; }

    const all = data.entries;
    const num = (e) => (typeof e.amount === "number" ? e.amount : 0);
    const sum = (arr) => arr.reduce((a, e) => a + num(e), 0);
    const me = all.filter((e) => e.side === "me"), mom = all.filter((e) => e.side === "mom");
    const tMe = sum(me), tMom = sum(mom), tAll = tMe + tMom;
    const tFixed = sum(all.filter((e) => e.fixed));

    // 요약
    const pMe = tAll > 0 ? Math.max(0, (tMe / tAll) * 100) : 0;
    $("#summary").innerHTML = `
      <div class="stat big"><div class="k">이번 달 총지출</div><div class="v">${won(tAll)}</div>
        <div class="bar"><i class="me" style="width:${pMe}%"></i><i class="mom" style="width:${100 - pMe}%"></i></div></div>
      <div class="stat me"><div class="k">내 돈</div><div class="v">${won(tMe)}</div></div>
      <div class="stat mom"><div class="k">엄마카드</div><div class="v">${won(tMom)}</div></div>
      <div class="stat"><div class="k">고정지출</div><div class="v">${won(tFixed)}</div><div class="s">회색 칸 합계</div></div>
      <div class="stat"><div class="k">변동지출</div><div class="v">${won(tAll - tFixed)}</div></div>`;

    // 쪽 선택
    const sideList = st.side === "all" ? all : all.filter((e) => e.side === st.side);

    // 분류별
    const byCat = new Map();
    for (const e of sideList) {
      const key = (st.side === "all" ? SIDE[e.side] + " · " : "") + e.cat;
      const o = byCat.get(key) || { key, cat: e.cat, side: e.side, t: 0 };
      o.t += num(e);
      byCat.set(key, o);
    }
    const cats = [...byCat.values()].filter((c) => c.t !== 0).sort((a, b) => b.t - a.t);
    const max = Math.max(1, ...cats.map((c) => c.t));
    $("#cats").innerHTML = cats.length ? cats.map((c) => `
      <div class="cat ${st.cat === c.key ? "sel" : st.cat ? "dim" : ""}" data-key="${esc(c.key)}">
        <span class="n"><b class="sd ${c.side}"></b>${esc(c.cat)}</span>
        <span class="t"><i style="width:${Math.max(0, (c.t / max) * 100)}%;background:var(--${c.side})"></i></span>
        <span class="a">${won(c.t)}</span></div>`).join("") : `<p class="empty">내역 없음</p>`;
    $("#cats").querySelectorAll(".cat").forEach((el) => el.onclick = () => {
      st.cat = st.cat === el.dataset.key ? null : el.dataset.key; render();
    });

    // 확인 필요 (금액 '?')
    const pend = sideList.filter((e) => e.pending);
    $("#pendingCard").hidden = !pend.length;
    $("#pending").innerHTML = pend.map((e) => row(e)).join("");

    // 날짜별
    const q = st.q.trim().toLowerCase();
    const shown = sideList.filter((e) => {
      if (st.cat && ((st.side === "all" ? SIDE[e.side] + " · " : "") + e.cat) !== st.cat) return false;
      if (q && !((e.memo || "") + " " + e.cat + " " + (e.amountNote || "")).toLowerCase().includes(q)) return false;
      return !e.pending || q || st.cat;
    });
    const groups = new Map();
    for (const e of shown) {
      const d = dayOf(e) || "zz";
      if (!groups.has(d)) groups.set(d, []);
      groups.get(d).push(e);
    }
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const all_k = [...groups.keys()].filter((k) => k !== "zz");
    const past = all_k.filter((k) => k <= today).sort().reverse();
    const future = all_k.filter((k) => k > today).sort();
    if (groups.has("zz")) future.push("zz");
    const block = (d) => {
      const es = groups.get(d).sort((a, b) => num(b) - num(a));
      let head = "날짜 없음";
      if (d !== "zz") {
        const dt = new Date(d + "T00:00:00");
        head = `${dt.getMonth() + 1}월 ${dt.getDate()}일<span class="w">${WD[dt.getDay()]}</span>`;
      }
      return `<div class="day"><h3><span>${head}</span><span class="sum">${won(sum(es))}</span></h3>
        <ul class="list">${es.map(row).join("")}</ul></div>`;
    };
    const futSum = future.reduce((a, d) => a + sum(groups.get(d)), 0);
    $("#days").innerHTML = all_k.length || groups.has("zz")
      ? past.map(block).join("") +
        (future.length ? `<div class="sect">이번 달 예정 · ${won(futSum)}</div>` + future.map(block).join("") : "")
      : `<p class="empty">${q || st.cat ? "맞는 내역이 없어요" : "내역 없음"}</p>`;

    $("#foot").textContent = st.updated ? `마지막 갱신 ${st.updated.replace("T", " ")}` : "";
  }

  function row(e) {
    const amt = typeof e.amount === "number" ? won(e.amount) : e.pending ? "?" : "";
    const chips = [
      e.fixed ? `<span class="chip fixed">고정</span>` : "",
      e.pending ? `<span class="chip warn">금액 미정</span>` : "",      e.amountNote ? `<span class="chip">${esc(e.amountNote)}</span>` : "",
    ].join("");
    const moved = e.realDate && e.date && e.realDate !== e.date ? " · 칸 위치 " + e.date.slice(5).replace("-", ".") : "";
    return `<li class="row"><span class="dot ${e.side}"></span>
      <div><div class="m">${esc(e.memo || e.cat)}${chips}</div>
      <div class="c">${SIDE[e.side]} · ${esc(e.cat)}${moved}</div></div>
      <div class="amt ${typeof e.amount === "number" && e.amount < 0 ? "neg" : ""}">${amt}</div></li>`;
  }

  async function init() {
    const idx = await load("data/index.json");
    // visibleFrom 이전 달은 목록에서 빼서 아예 불러오지 않는다
    st.months = idx.visibleFrom ? idx.months.filter((m) => m >= idx.visibleFrom) : idx.months;
    st.updated = idx.updated;
    const now = new Date();
    const cur = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    const want = location.hash.slice(1);
    let i = st.months.indexOf(want);
    if (i < 0) i = st.months.indexOf(cur);
    if (i < 0) i = st.months.filter((m) => m <= cur).length - 1;
    st.i = Math.max(0, i);
    st.side = store.get("side") || "all";
    document.querySelectorAll("#sideTabs button").forEach((b) => b.classList.toggle("on", b.dataset.side === st.side));
    render();
  }

  $("#prev").onclick = () => { if (st.i > 0) { st.i--; st.cat = null; render(); scrollTo(0, 0); } };
  $("#next").onclick = () => { if (st.i < st.months.length - 1) { st.i++; st.cat = null; render(); scrollTo(0, 0); } };
  document.querySelectorAll("#sideTabs button").forEach((b) => b.onclick = () => {
    st.side = b.dataset.side; st.cat = null; store.set("side", st.side);
    document.querySelectorAll("#sideTabs button").forEach((x) => x.classList.toggle("on", x === b));
    render();
  });
  $("#q").oninput = (ev) => { st.q = ev.target.value; render(); };
  addEventListener("keydown", (ev) => {
    if (ev.target.tagName === "INPUT") return;
    if (ev.key === "ArrowLeft") $("#prev").click();
    if (ev.key === "ArrowRight") $("#next").click();
  });
  addEventListener("hashchange", () => {
    const i = st.months.indexOf(location.hash.slice(1));
    if (i > -1 && i !== st.i) { st.i = i; render(); }
  });
  init().catch((err) => { $("#days").innerHTML = `<p class="empty">불러오지 못했어요 (${esc(err.message)})</p>`; });
})();
