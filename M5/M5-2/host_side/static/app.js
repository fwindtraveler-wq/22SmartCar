/* 前端实时渲染：指标曲线、故障流、任务状态、系统仪表盘。 */
(function () {
  "use strict";

  var lastEventTs = 0;
  var history = { fps: [], latency: [], nav: [] };
  var maxPoints = 60;

  function $(id) { return document.getElementById(id); }

  function setText(id, text) { $(id).textContent = text; }

  function pushSeries(name, value) {
    history[name].push(Number(value) || 0);
    if (history[name].length > maxPoints) history[name].shift();
    drawLine(name + "-chart", history[name], name === "latency" ? "#4f9df7" : name === "nav" ? "#f6b83c" : "#31c48d");
  }

  function drawLine(canvasId, values, color) {
    var canvas = $(canvasId);
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    var w = canvas.width, h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    if (!values.length) return;
    var max = Math.max.apply(null, values.concat([1]));
    values.forEach(function (v, i) {
      var x = i / Math.max(1, values.length - 1) * w;
      var y = h - (v / max) * (h - 8) - 4;
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  function renderTaskState(task) {
    if (!task || Object.keys(task).length === 0) {
      setText("task-state", "等待 task_state");
      return;
    }
    var lines = [];
    if (task.current) lines.push("当前: " + task.current);
    if (task.stage) lines.push("阶段: " + task.stage);
    if (task.progress != null) lines.push("进度: " + task.progress + "%");
    if (task.context) lines.push("上下文: " + JSON.stringify(task.context));
    setText("task-state", lines.join("\n") || JSON.stringify(task));
  }

  function renderFaults(faults) {
    var box = $("fault-list");
    if (!faults || !faults.length) {
      box.innerHTML = "暂无故障";
      return;
    }
    box.innerHTML = faults.slice().reverse().map(function (f) {
      var cls = f.event === "fault_recovered" || f.recovered ? "recovered" : "warning";
      var time = new Date(f.ts * 1000).toLocaleTimeString();
      return '<div class="fault-item ' + cls + '">' + time + " " + f.type + " / " + f.source + " - " + f.reason + "</div>";
    }).join("");
  }

  function renderSystem(sys) {
    sys = sys || {};
    setText("cpu-value", sys.cpu != null ? Number(sys.cpu).toFixed(0) : "--");
    setText("temp-value", sys.temp != null ? Number(sys.temp).toFixed(0) : "--");
    setText("volt-value", sys.voltage != null ? Number(sys.voltage).toFixed(2) : "--");
    setText("rtt-value", sys.rtt != null ? Number(sys.rtt).toFixed(1) : "--");
  }

  function renderSummary(latest) {
    var topics = latest && latest.topics ? Object.keys(latest.topics).length : 0;
    var ts = latest && latest.ts ? new Date(latest.ts * 1000).toLocaleTimeString() : "--";
    setText("metric-summary", "聚合话题数: " + topics + "，最后更新: " + ts);
  }

  function markStale() {
    var stale = lastEventTs && Date.now() - lastEventTs > 1500;
    document.body.classList.toggle("stale", stale);
    setText("conn-status", stale ? "失联：长时间未收到聚合数据" : "已连接");
  }

  function render(event) {
    lastEventTs = Date.now();
    document.body.classList.remove("stale");
    setText("conn-status", "已连接");
    var latest = event.latest || {};
    renderTaskState(latest.task_state || event.task_state);
    renderFaults(event.faults || []);
    renderSystem(latest.system);
    renderSummary(latest);

    var topics = latest.topics || {};
    var first = topics[Object.keys(topics)[0]];
    if (first) {
      pushSeries("fps", first.hz);
      pushSeries("latency", first.latency_ms);
      pushSeries("nav", topics["/navigation/status"] ? topics["/navigation/status"].hz : 0);
    }
  }

  function connect() {
    var es = new EventSource("/api/stream");
    es.onmessage = function (evt) { render(JSON.parse(evt.data)); };
    es.onerror = function () { markStale(); };
  }

  $("export-btn").addEventListener("click", function () { window.location.href = "/api/export"; });
  $("record-btn").addEventListener("click", function () { alert("录屏功能可接入 web_video_server，比赛模式默认关闭。"); });
  $("estop-btn").addEventListener("click", function () {
    fetch("/api/command", { method: "POST", body: JSON.stringify({ action: "emergency_stop" }), headers: { "Content-Type": "application/json" } });
  });

  var exported = $("export-data");
  if (exported && exported.textContent.trim()) {
    var data = JSON.parse(exported.textContent);
    render({ latest: data.latest, faults: data.faults, task_state: data.task_state, ts: Date.now() });
  } else {
    connect();
    setInterval(markStale, 1000);
  }
}());
