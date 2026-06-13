"""Local web dashboard: a prettier face over the same config/state/stats JSON.

`workout` (or `! workout`) ensures a tiny localhost server is up and opens the
browser. The server is stdlib-only (no deps), binds to 127.0.0.1, exposes a
read endpoint (/api/state) and a write endpoint (/api/action), and shuts itself
down after a few minutes idle. The webcam challenge stays native — the
dashboard just spawns it via the existing `now` command.

Pure logic (build_state / apply_action) is kept I/O-light and server-free so it
is unit-testable without sockets.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import store
from .paths import PROJECT_DIR, python_bin

PORT_FILE = "web.port"
PID_FILE = "web.pid"
IDLE_SHUTDOWN_S = 600          # exit after 10 min with no requests (tab closed)


# ─────────────────────────── pure logic ───────────────────────────

def build_state() -> dict:
    """Everything the dashboard needs, in one JSON-able dict."""
    from . import challenge, trigger
    from .detector import EXERCISES

    config = store.load_config()
    state = store.load_state()
    stats = store.load_stats()

    by_day = stats.get("by_day", {})
    dates = [d for d, _ in store.last_days(by_day)]
    record = store.best_day(by_day)

    exercises = {}
    for name, ec in config["exercises"].items():
        reg = EXERCISES.get(name, {})
        exercises[name] = {
            "label": reg.get("label", name.upper()),
            "cue": reg.get("cue", ""),
            "enabled": bool(ec.get("enabled")),
            "reps_min": ec["reps_min"],
            "reps_max": ec["reps_max"],
            "total": stats.get("by_exercise", {}).get(name, 0),
            "spark": [store.day_counts(stats, name).get(d, 0) for d in dates],
        }

    return {
        "enabled": config["enabled"],
        "trigger": config["trigger"],
        "every_n_prompts": config["every_n_prompts"],
        "time_interval_min": config["time_interval_min"],
        "roulette_chance_pct": config["roulette_chance_pct"],
        "exercise_mode": config.get("exercise_mode", "choice"),
        "debug": bool(config.get("debug", False)),
        "preset": config.get("preset"),
        "presets": sorted(trigger.PRESETS),
        "exercises": exercises,
        "stats": {
            "total": stats.get("total_reps", 0),
            "today": by_day.get(store.today(), 0),
            "streak": store.streak_days(by_day),
            "record": ({"date": record[0], "reps": record[1]} if record else None),
            "last7": [{"date": d, "reps": by_day.get(d, 0)} for d in dates],
            "day_max": max((by_day.get(d, 0) for d in dates), default=0),
        },
        "status": {
            "prompt_count": state.get("prompt_count", 0),
            "debt": challenge.pending_summary(state) or "",
        },
        "challenge_running": store.running_challenge_pid() is not None,
    }


def apply_action(p: dict) -> dict:
    """Mutate config from a dashboard action, then return the fresh state.
    Mirrors the caps used by the curses TUI."""
    from . import trigger

    a = p.get("action")
    config = store.load_config()

    if a == "set_enabled":
        config["enabled"] = bool(p["value"])
    elif a == "preset" and p.get("name") in trigger.PRESETS:
        trigger.apply_preset(config, p["name"])
    elif a == "clear_preset":
        config["preset"] = None
    elif a == "trigger" and p.get("value") in ("prompts", "time", "roulette"):
        config["trigger"] = p["value"]
        config["preset"] = None
    elif a == "freq":
        config["every_n_prompts"] = max(1, min(99, int(p["value"])))
        config["trigger"] = "prompts"
        config["preset"] = None
    elif a == "time":
        config["time_interval_min"] = max(5, min(240, int(p["value"])))
        config["trigger"] = "time"
        config["preset"] = None
    elif a == "chance":
        config["roulette_chance_pct"] = max(5, min(100, float(p["value"])))
        config["trigger"] = "roulette"
        config["preset"] = None
    elif a == "reps" and p.get("exercise") in config["exercises"]:
        lo = max(1, int(p["min"]))
        hi = max(lo, min(50, int(p["max"])))
        config["exercises"][p["exercise"]]["reps_min"] = lo
        config["exercises"][p["exercise"]]["reps_max"] = hi
        config["preset"] = None
    elif a == "enable" and p.get("exercise") in config["exercises"]:
        config["exercises"][p["exercise"]]["enabled"] = bool(p["value"])
        config["preset"] = None
    elif a == "mode" and p.get("value") in ("choice", "random"):
        config["exercise_mode"] = p["value"]
    elif a == "debug":
        config["debug"] = bool(p["value"])
    elif a == "challenge":
        _spawn_challenge()
        return build_state()
    else:
        return build_state()

    store.save_config(config)
    return build_state()


def _spawn_challenge() -> None:
    """Open the native webcam challenge without blocking the server."""
    if store.running_challenge_pid() is not None:
        return
    subprocess.Popen(
        [str(python_bin()), "-m", "workout_gate", "now"],
        cwd=str(PROJECT_DIR), start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


# ─────────────────────────── server ───────────────────────────

class _State:
    last_activity = time.time()


def _handler_class():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, body, ctype):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            _State.last_activity = time.time()
            if self.path in ("/", "/index.html"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/api/ping":
                self._send(200, "ok", "text/plain")
            elif self.path == "/api/state":
                self._send(200, json.dumps(build_state()), "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            _State.last_activity = time.time()
            if self.path != "/api/action":
                self._send(404, "not found", "text/plain")
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or "{}")
                result = apply_action(payload)
                self._send(200, json.dumps(result), "application/json")
            except Exception as e:  # never crash the server on a bad action
                self._send(400, json.dumps({"error": str(e)}), "application/json")

    return Handler


def _idle_watch(httpd):
    while True:
        time.sleep(20)
        if time.time() - _State.last_activity > IDLE_SHUTDOWN_S:
            threading.Thread(target=httpd.shutdown, daemon=True).start()
            return


def serve() -> None:
    """Run the dashboard server (blocking). Picks a free port, advertises it in
    the data dir, and auto-exits when idle. Invoked detached by the launcher."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _handler_class())
    port = httpd.server_address[1]
    d = store.data_dir()
    (d / PORT_FILE).write_text(str(port))
    (d / PID_FILE).write_text(str(os.getpid()))
    threading.Thread(target=_idle_watch, args=(httpd,), daemon=True).start()
    try:
        httpd.serve_forever()
    finally:
        (d / PORT_FILE).unlink(missing_ok=True)
        (d / PID_FILE).unlink(missing_ok=True)


def _running_port():
    p = store.data_dir() / PORT_FILE
    if not p.exists():
        return None
    try:
        port = int(p.read_text())
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=0.5).read()
        return port
    except Exception:
        return None


def _spawn_server():
    subprocess.Popen(
        [str(python_bin()), "-m", "workout_gate", "serve"],
        cwd=str(PROJECT_DIR), start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(50):  # ~5s
        time.sleep(0.1)
        port = _running_port()
        if port:
            return port
    return None


def open_dashboard() -> None:
    """Ensure the server is up and open the browser. Fast + non-blocking, so
    `! workout` returns to the session immediately."""
    port = _running_port() or _spawn_server()
    if not port:
        print("Could not start the dashboard server. Try: workout tui")
        return
    url = f"http://127.0.0.1:{port}/"
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print(f"Workout Gate dashboard → {url}")


# ─────────────────────────── page ───────────────────────────

PAGE = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Workout Gate</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  :root{
    --bg:#161718; --panel:#1f2123; --panel2:#26282b; --line:#33363a;
    --ink:#e8e8e6; --dim:#8b9097; --orange:#d97757; --orange2:#e98e6e;
    --green:#6cc187; --yellow:#e3a93c; --blue:#6aa6e8; --red:#e06c6c;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:radial-gradient(120% 90% at 50% -10%, #2a1c16 0%, #161718 55%);
    color:var(--ink);font-family:"JetBrains Mono",ui-monospace,monospace;
    min-height:100vh;padding:34px 18px 60px}
  .wrap{max-width:860px;margin:0 auto;display:flex;flex-direction:column;gap:18px}
  header{display:flex;align-items:center;gap:16px}
  .brand{display:flex;flex-direction:column;gap:3px}
  .taunt{color:var(--dim);font-size:11px;letter-spacing:1.5px;text-transform:uppercase}
  h1{font-size:23px;font-weight:700;letter-spacing:.3px}
  h1 .sub{color:var(--dim);font-weight:500;font-size:15px;margin-left:6px}
  .spacer{flex:1}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
  .panel h2{font-size:13px;letter-spacing:2px;text-transform:uppercase;color:var(--dim);margin-bottom:16px;font-weight:700}
  /* gate toggle */
  .toggle{display:inline-flex;align-items:center;gap:10px;cursor:pointer;user-select:none;font-size:14px;color:var(--dim)}
  .sw{width:52px;height:28px;border-radius:99px;background:#3a3d41;position:relative;transition:.18s}
  .sw::after{content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;background:#cfcfcf;transition:.18s}
  .sw.on{background:var(--orange)}.sw.on::after{left:27px;background:#fff}
  /* stats */
  .stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
  .stat{background:var(--panel2);border:1px solid var(--line);border-radius:11px;padding:14px 16px}
  .stat .n{font-size:34px;font-weight:700;line-height:1}
  .stat .l{font-size:12px;color:var(--dim);margin-top:6px;text-transform:uppercase;letter-spacing:1px}
  .stat .n.fire{color:var(--yellow)} .stat .n.org{color:var(--orange)}
  .ex-row{display:flex;align-items:center;gap:12px;margin-top:12px;font-size:14px}
  .ex-row .name{width:90px;color:var(--ink)}
  .bar{flex:1;height:10px;background:#2c2f33;border-radius:6px;overflow:hidden}
  .bar i{display:block;height:100%;background:var(--green);border-radius:6px}
  .ex-row .v{width:46px;text-align:right;font-weight:700}
  .spark{color:var(--green);letter-spacing:1px;width:74px;text-align:right}
  .days{margin-top:14px;display:flex;flex-direction:column;gap:6px}
  .day{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--dim)}
  .day .d{width:60px} .day .b{flex:1;height:14px;background:#26282b;border-radius:5px;overflow:hidden}
  .day .b i{display:block;height:100%;background:var(--orange);border-radius:5px}
  .day .v{width:40px;text-align:right;color:var(--ink)}
  /* settings rows */
  .row{display:flex;align-items:center;gap:14px;padding:12px 0;border-top:1px solid var(--line)}
  .row:first-of-type{border-top:none}
  .row .lbl{flex:1}
  .row .lbl small{display:block;color:var(--dim);font-size:12px;margin-top:2px}
  .seg{display:inline-flex;background:#2c2f33;border-radius:9px;padding:3px;gap:2px}
  .seg button{border:0;background:transparent;color:var(--dim);font:inherit;font-size:13px;
    padding:6px 13px;border-radius:7px;cursor:pointer}
  .seg button.on{background:var(--orange);color:#fff;font-weight:600}
  .step{display:inline-flex;align-items:center;gap:0;background:#2c2f33;border-radius:9px;overflow:hidden}
  .step button{border:0;background:transparent;color:var(--ink);font:inherit;font-size:18px;width:34px;height:34px;cursor:pointer}
  .step button:hover{background:#3a3d41}
  .step .val{min-width:64px;text-align:center;font-weight:700;font-size:14px}
  .star{color:var(--orange);margin-left:6px}
  .exhead .reps{display:flex;align-items:center;gap:8px;color:var(--dim);font-size:13px}
  .btn{border:0;border-radius:10px;font:inherit;font-weight:700;cursor:pointer;padding:14px 18px;font-size:15px}
  .btn.go{background:var(--orange);color:#fff;width:100%}
  .btn.go:hover{background:var(--orange2)} .btn.go:disabled{opacity:.5;cursor:default}
  .pill{font-size:12px;padding:4px 10px;border-radius:99px;background:#2c2f33;color:var(--dim)}
  .pill.live{color:var(--green)} .pill.debt{color:var(--yellow)}
  .foot{color:var(--dim);font-size:12px;text-align:center;margin-top:4px}
  .foot code{color:var(--orange)}
  /* tabs */
  .tabs{display:flex;gap:4px;flex-wrap:wrap;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:6px}
  .tab{border:0;background:transparent;color:var(--dim);font:inherit;font-size:14px;font-weight:600;padding:9px 16px;border-radius:8px;cursor:pointer;display:flex;align-items:center;gap:7px}
  .tab:hover{color:var(--ink)}
  .tab.on{background:var(--orange);color:#fff}
  .tab .dot{width:7px;height:7px;border-radius:50%;background:#4b4f54}
  .tab .dot.on{background:var(--green)} .tab.on .dot.on{background:#fff}
  .tabpage{display:flex;flex-direction:column;gap:18px}
  .tabpage[hidden]{display:none}
  .cue{color:var(--dim);font-size:12px;letter-spacing:1px;text-transform:uppercase;margin:-4px 0 16px}
  .exhead{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin-bottom:18px}
  .stats.two{grid-template-columns:repeat(2,1fr)}
  @media(max-width:560px){.stats{grid-template-columns:repeat(2,1fr)}}
</style></head>
<body><div class="wrap">
  <header>
    <div class="brand">
      <h1>Workout Gate <span class="sub">dashboard</span></h1>
      <div class="taunt">drop and give me 20</div>
    </div>
    <span class="spacer"></span>
    <span id="status-pill" class="pill">…</span>
    <label class="toggle"><span id="gate-label">gate</span>
      <span id="gate-sw" class="sw"></span></label>
  </header>

  <nav id="tabs" class="tabs"></nav>

  <div id="page-overview" class="tabpage">
    <section class="panel">
      <h2>Stats</h2>
      <div class="stats">
        <div class="stat"><div class="n" id="s-total">–</div><div class="l">Total reps</div></div>
        <div class="stat"><div class="n org" id="s-today">–</div><div class="l">Today</div></div>
        <div class="stat"><div class="n fire" id="s-streak">–</div><div class="l">Streak 🔥</div></div>
        <div class="stat"><div class="n" id="s-record">–</div><div class="l">Record</div></div>
      </div>
      <div id="ex-bars"></div>
      <div class="days" id="days"></div>
    </section>

    <section class="panel">
      <h2>Settings</h2>
      <div class="row"><div class="lbl">Preset</div><div id="preset-seg" class="seg"></div></div>
      <div class="row"><div class="lbl">Trigger</div><div id="trigger-seg" class="seg"></div></div>
      <div id="trigger-detail"></div>
      <div class="row"><div class="lbl">Exercise pick<small>which exercise when several are on</small></div><div id="mode-seg" class="seg"></div></div>
      <div class="row"><div class="lbl">Debug overlay<small>skeleton + live joint angle</small></div><div id="debug-seg" class="seg"></div></div>
    </section>

    <section class="panel">
      <h2>Challenge</h2>
      <button id="go" class="btn go">▶  Force a challenge now</button>
      <div class="foot" style="margin-top:12px">opens the native webcam window · or run <code>! workout now</code></div>
    </section>
  </div>

  <div id="page-exercise" class="tabpage" hidden></div>

  <div class="foot">local dashboard · <code>! workout</code> reopens it · <code>workout tui</code> for the terminal version</div>
</div>

<script>
const $ = s => document.querySelector(s);
let S = null;
const SPARK = "▁▂▃▄▅▆▇█";
function spark(arr){const top=Math.max(0,...arr); if(top<=0)return SPARK[0].repeat(arr.length);
  return arr.map(v=>SPARK[Math.min(7,Math.round(v/top*7))]).join("");}
function prettyDate(iso){const [y,m,d]=iso.split("-").map(Number);
  return ["","Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][m]+" "+d;}

async function post(payload){
  const r = await fetch("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
  S = await r.json(); render();
}
async function load(){ const r = await fetch("/api/state"); S = await r.json(); render(); }

function seg(host, opts, current, onPick){
  host.innerHTML="";
  opts.forEach(o=>{const b=document.createElement("button");b.textContent=o.label;
    if(o.value===current)b.className="on";
    b.onclick=()=>onPick(o.value);host.appendChild(b);});
}
function stepper(label, value, unit, onDelta){
  return `<div class="row"><div class="lbl">${label}</div>
    <div class="step"><button data-d="-1">−</button><span class="val">${value}${unit||""}</span><button data-d="1">+</button></div></div>`;
}

let TAB = "overview";

function render(){
  if(!S) return;
  if(TAB!=="overview" && !S.exercises[TAB]) TAB="overview";  // exercise vanished
  renderHeader();
  renderTabs();
  renderOverview();                       // cheap; page may be hidden
  const onEx = TAB!=="overview";
  $("#page-overview").hidden = onEx;
  $("#page-exercise").hidden = !onEx;
  if(onEx) renderExercise(TAB); else $("#page-exercise").innerHTML="";
}

function renderHeader(){
  const sp=$("#status-pill");
  if(S.challenge_running){sp.className="pill live";sp.textContent="● challenge open";}
  else if(S.status.debt){sp.className="pill debt";sp.textContent="debt: "+S.status.debt;}
  else {sp.className="pill";sp.textContent=S.trigger==="prompts"?`${S.status.prompt_count}/${S.every_n_prompts} prompts`:S.trigger;}
  $("#gate-sw").className="sw"+(S.enabled?" on":"");
  $("#gate-label").textContent=S.enabled?"gate ON":"gate OFF";
}

function renderTabs(){
  const host=$("#tabs"); host.innerHTML="";
  // overview first, then one tab per exercise — straight from the registry,
  // so a new exercise (one file in detector.py) shows up here automatically.
  const tabs=[{key:"overview",label:"overview",enabled:null},
    ...Object.entries(S.exercises).map(([k,e])=>({key:k,label:e.label.toLowerCase(),enabled:e.enabled}))];
  tabs.forEach(t=>{const b=document.createElement("button");
    b.className="tab"+(TAB===t.key?" on":"");
    if(t.enabled===null) b.textContent=t.label;
    else b.innerHTML=`<span class="dot${t.enabled?' on':''}"></span>${t.label}`;
    b.onclick=()=>{TAB=t.key; render();}; host.appendChild(b);});
}

function renderOverview(){
  $("#s-total").textContent=S.stats.total;
  $("#s-today").textContent=S.stats.today;
  $("#s-streak").textContent=S.stats.streak+"d";
  $("#s-record").textContent=S.stats.record?S.stats.record.reps:"–";

  const exMax=Math.max(0,...Object.values(S.exercises).map(e=>e.total));
  $("#ex-bars").innerHTML=Object.entries(S.exercises).map(([k,e])=>
    `<div class="ex-row"><span class="name">${e.label.toLowerCase()}</span>
      <span class="bar"><i style="width:${exMax?Math.round(e.total/exMax*100):0}%"></i></span>
      <span class="v">${e.total}</span><span class="spark">${spark(e.spark)}</span></div>`).join("");

  const dmax=S.stats.day_max;
  $("#days").innerHTML=S.stats.last7.map(d=>
    `<div class="day"><span class="d">${prettyDate(d.date)}</span>
      <span class="b"><i style="width:${dmax?Math.round(d.reps/dmax*100):0}%"></i></span>
      <span class="v">${d.reps}</span></div>`).join("");

  // presets
  const presets=[{label:"none",value:null},...S.presets.map(p=>({label:p,value:p}))];
  seg($("#preset-seg"),presets,S.preset,v=> v?post({action:"preset",name:v}):post({action:"clear_preset"}));

  // trigger
  seg($("#trigger-seg"),[{label:"prompts",value:"prompts"},{label:"time",value:"time"},{label:"roulette",value:"roulette"}],S.trigger,v=>post({action:"trigger",value:v}));
  let detail="";
  if(S.trigger==="prompts") detail=stepper("Every N prompts",S.every_n_prompts,"",0);
  else if(S.trigger==="time") detail=stepper("Time interval",S.time_interval_min," min",0);
  else detail=stepper("Roulette chance",S.roulette_chance_pct,"%",0);
  $("#trigger-detail").innerHTML=detail;
  const td=$("#trigger-detail .step");
  if(td){td.querySelectorAll("button").forEach(b=>b.onclick=()=>{
    const d=+b.dataset.d;
    if(S.trigger==="prompts")post({action:"freq",value:S.every_n_prompts+d});
    else if(S.trigger==="time")post({action:"time",value:S.time_interval_min+5*d});
    else post({action:"chance",value:S.roulette_chance_pct+5*d});
  });}

  // mode + debug
  seg($("#mode-seg"),[{label:"choice",value:"choice"},{label:"random",value:"random"}],S.exercise_mode,v=>post({action:"mode",value:v}));
  seg($("#debug-seg"),[{label:"off",value:false},{label:"on",value:true}],S.debug,v=>post({action:"debug",value:v}));

  // challenge button
  $("#go").disabled=S.challenge_running;
  $("#go").textContent=S.challenge_running?"● challenge window open":"▶  Force a challenge now";
}

function renderExercise(ex){
  const e=S.exercises[ex];
  const today=e.spark.length?e.spark[e.spark.length-1]:0;
  const dmax=Math.max(0,...e.spark);
  $("#page-exercise").innerHTML=`
    <section class="panel">
      <h2>${e.label.toLowerCase()}</h2>
      <p class="cue">${e.cue||"&nbsp;"}</p>
      <div class="exhead">
        <span class="seg" id="ex-en">
          <button class="${e.enabled?'on':''}" data-v="1">on</button>
          <button class="${!e.enabled?'on':''}" data-v="0">off</button>
        </span>
        <span class="reps">reps
          <span class="step" id="ex-min"><button data-d="-1">−</button><span class="val">${e.reps_min}</span><button data-d="1">+</button></span>
          –
          <span class="step" id="ex-max"><button data-d="-1">−</button><span class="val">${e.reps_max}</span><button data-d="1">+</button></span>
        </span>
      </div>
      <div class="stats two">
        <div class="stat"><div class="n">${e.total}</div><div class="l">Total reps</div></div>
        <div class="stat"><div class="n org">${today}</div><div class="l">Today</div></div>
      </div>
      <div class="days" style="margin-top:18px">${S.stats.last7.map((d,i)=>
        `<div class="day"><span class="d">${prettyDate(d.date)}</span>
          <span class="b"><i style="width:${dmax?Math.round((e.spark[i]||0)/dmax*100):0}%"></i></span>
          <span class="v">${e.spark[i]||0}</span></div>`).join("")}</div>
    </section>`;
  $("#ex-en").querySelectorAll("button").forEach(b=>
    b.onclick=()=>post({action:"enable",exercise:ex,value:b.dataset.v==="1"}));
  $("#ex-min").querySelectorAll("button").forEach(b=>
    b.onclick=()=>post({action:"reps",exercise:ex,min:e.reps_min+(+b.dataset.d),max:e.reps_max}));
  $("#ex-max").querySelectorAll("button").forEach(b=>
    b.onclick=()=>post({action:"reps",exercise:ex,min:e.reps_min,max:e.reps_max+(+b.dataset.d)}));
}

$("#gate-sw").onclick=()=>post({action:"set_enabled",value:!S.enabled});
$("#go").onclick=()=>{ if(!S.challenge_running) post({action:"challenge"}); };

load();
setInterval(load, 4000);  // live stats + keeps the server alive while open
</script>
</body></html>
"""
