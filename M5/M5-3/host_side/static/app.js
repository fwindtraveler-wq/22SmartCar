(function () {
  "use strict";
  var state = { referee: {}, safety: {}, events: [] };
  function $(id) { return document.getElementById(id); }
  function post(action, args, target) {
    var body = { action: action, args: args || {} };
    if (target) {
      if (target === "model") body.args.target = $("model-input").value;
      if (target === "scene") body.args.target = $("scene-input").value;
    }
    if (action === "set_param") body.args = { name: $("param-name").value, value: $("param-value").value };
    if (action === "reset") body.args.confirm = confirm("确认解除急停？");
    fetch("/api/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); }).then(renderCommand);
  }
  function renderCommand(result) {
    if (result && result.ok === false) alert(result.reason || "操作失败");
  }
  function render(s) {
    state = s;
    $("referee-state").textContent = JSON.stringify(s.referee || {});
    $("referee-badge").textContent = (s.referee && s.referee.state) || "READY";
    $("safety-state").textContent = s.safety && s.safety.stopped ? "已急停: " + s.safety.reason : "未急停";
    $("event-log").textContent = (s.events || []).map(function (e) { return new Date(e.ts * 1000).toLocaleTimeString() + " " + e.topic + " " + JSON.stringify(e.payload); }).join("\n");
  }
  document.querySelectorAll("button[data-action]").forEach(function (btn) {
    btn.addEventListener("click", function () { post(btn.getAttribute("data-action"), {}, btn.getAttribute("data-target")); });
  });
  var es = new EventSource("/api/stream");
  es.onmessage = function (e) { render(JSON.parse(e.data)); };
  fetch("/api/state").then(function (r) { return r.json(); }).then(render);
}());
