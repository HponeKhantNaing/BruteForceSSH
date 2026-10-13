(function () {
  const refreshMs = window.P12_REFRESH_MS || 1000;

  function el(id) { return document.getElementById(id); }

  function text(node, value) {
    node.textContent = value == null ? "" : String(value);
  }

  function badge(label, cls) {
    const s = document.createElement("span");
    s.className = "badge " + (cls || "info");
    text(s, label);
    return s;
  }

  function tag(label, cls) {
    const s = document.createElement("span");
    s.className = "tag " + (cls || label);
    text(s, label);
    return s;
  }

  async function getJSON(url) {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error("http " + r.status);
    return r.json();
  }

  function fmt(ts) {
    if (!ts) return "—";
    return String(ts).replace("T", " ").replace("+00:00", "Z");
  }

  async function refresh() {
    const [health, summary, model, preds, alerts] = await Promise.all([
      getJSON("/api/health"),
      getJSON("/api/summary"),
      getJSON("/api/model"),
      getJSON(predQuery()),
      getJSON("/api/alerts?limit=50"),
    ]);

    const badges = el("badges");
    badges.replaceChildren();
    const p11cls = health.p11_status === "ONLINE" ? "ok" : (health.p11_status === "STALE" ? "warn" : "crit");
    badges.appendChild(badge("P11 " + health.p11_status, p11cls));
    badges.appendChild(badge("P12 ONLINE", "ok"));
    const d = health.discord_status || "DISABLED";
    badges.appendChild(badge("DISCORD " + d, d === "ENABLED" || d === "SENT_OK" ? "ok" : (d === "DEGRADED" ? "warn" : "info")));
    badges.appendChild(badge("Release " + (health.release_id || window.P12_RELEASE), "info"));

    const kpis = el("kpis");
    kpis.replaceChildren();
    const items = [
      ["Predictions", summary.predictions_ingested],
      ["NORMAL", summary.normal],
      ["SUSPICIOUS", summary.suspicious],
      ["BRUTE_FORCE", summary.brute_force],
      ["Discord sent", summary.alerts_sent],
      ["Pending/Failed", (summary.alerts_pending || 0) + "/" + (summary.alerts_failed || 0)],
    ];
    for (const [l, n] of items) {
      const d = document.createElement("div");
      d.className = "kpi";
      const nn = document.createElement("div"); nn.className = "n"; text(nn, n);
      const ll = document.createElement("div"); ll.className = "l"; text(ll, l);
      d.appendChild(nn); d.appendChild(ll);
      kpis.appendChild(d);
    }

    const live = el("live");
    live.replaceChildren();
    const latest = {};
    for (const p of (preds.items || [])) {
      if (!latest[p.episode_id]) latest[p.episode_id] = p;
    }
    Object.values(latest).slice(0, 8).forEach((p) => {
      const card = document.createElement("div");
      card.className = "live-item " + p.predicted_label + (p.provisional ? " provisional" : "");
      const head = document.createElement("div");
      head.appendChild(tag(p.predicted_label));
      head.appendChild(document.createTextNode(" "));
      head.appendChild(tag(p.provisional ? "PROVISIONAL" : "FINAL", p.provisional ? "PROVISIONAL" : "FINAL"));
      const meta = document.createElement("div");
      meta.className = "meta";
      text(meta, p.source_id + " · " + p.episode_id + " · attempts=" + p.attempt_count + " · " + fmt(p.event_timestamp));
      const scores = document.createElement("div");
      scores.className = "meta";
      text(scores, "Uncalibrated scores — N " + Number(p.score_normal).toFixed(3) +
        " · S " + Number(p.score_suspicious).toFixed(3) +
        " · B " + Number(p.score_brute_force).toFixed(3));
      card.appendChild(head); card.appendChild(meta); card.appendChild(scores);
      live.appendChild(card);
    });
    if (!Object.keys(latest).length) {
      const empty = document.createElement("div");
      empty.className = "meta";
      text(empty, "No predictions yet.");
      live.appendChild(empty);
    }

    const modelBox = el("model");
    modelBox.replaceChildren();
    const m = document.createElement("div");
    m.className = "meta";
    text(m,
      "Model: Random Forest — Behavior\n" +
      "Release: " + model.release_id + "\n" +
      "Features: " + model.feature_count + " raw behavioral features\n" +
      "Maturity: " + model.maturity + "\n" +
      "Probabilities: UNCALIBRATED"
    );
    m.style.whiteSpace = "pre-line";
    modelBox.appendChild(m);

    const chart = el("chart");
    chart.replaceChildren();
    const buckets = {};
    for (const a of (summary.activity || [])) {
      buckets[a.bucket] = (buckets[a.bucket] || 0) + a.n;
    }
    const vals = Object.keys(buckets).sort().slice(-24).map((k) => buckets[k]);
    const max = Math.max(1, ...vals);
    vals.forEach((v) => {
      const b = document.createElement("div");
      b.className = "bar";
      b.style.height = Math.max(4, Math.round(80 * v / max)) + "px";
      b.title = String(v);
      chart.appendChild(b);
    });

    const tbody = el("pred-body");
    tbody.replaceChildren();
    for (const p of (preds.items || [])) {
      const tr = document.createElement("tr");
      const cells = [
        fmt(p.event_timestamp), p.source_id, p.episode_id,
        (p.provisional ? "PROVISIONAL/" : "FINAL/") + p.snapshot_type,
        p.attempt_count, p.predicted_label,
        Number(p.score_normal).toFixed(3),
        Number(p.score_suspicious).toFixed(3),
        Number(p.score_brute_force).toFixed(3),
        p.alert_status || "—"
      ];
      cells.forEach((c) => {
        const td = document.createElement("td");
        text(td, c);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    }

    const ab = el("alert-body");
    ab.replaceChildren();
    for (const a of (alerts.items || [])) {
      const tr = document.createElement("tr");
      [fmt(a.created_at), a.severity, a.source_id, a.episode_id, a.predicted_label, a.decision, a.delivery_state, a.retry_count]
        .forEach((c) => {
          const td = document.createElement("td");
          text(td, c);
          tr.appendChild(td);
        });
      ab.appendChild(tr);
    }
  }

  function predQuery() {
    const label = el("f-label").value;
    const snap = el("f-snap").value;
    const alertsOnly = el("f-alerts").checked;
    const q = new URLSearchParams({ limit: "100" });
    if (label) q.set("label", label);
    if (snap) q.set("snapshot_type", snap);
    if (alertsOnly) q.set("alerts_only", "true");
    return "/api/predictions?" + q.toString();
  }

  ["f-label", "f-snap", "f-alerts"].forEach((id) => {
    el(id).addEventListener("change", () => { refresh().catch(console.error); });
  });

  refresh().catch(console.error);
  setInterval(() => { refresh().catch(console.error); }, refreshMs);
})();
