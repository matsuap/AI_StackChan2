import asyncio
import json
import queue
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import serial.tools.list_ports
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Error message variable mapping (config key → C++ variable name)
# ---------------------------------------------------------------------------

_ERR_MSGS = {
    'err_client':    'ERR_MSG_CLIENT',
    'err_connect':   'ERR_MSG_CONNECT',
    'err_timeout':   'ERR_MSG_TIMEOUT',
    'err_401':       'ERR_MSG_401',
    'err_429':       'ERR_MSG_429',
    'err_400':       'ERR_MSG_400',
    'err_404':       'ERR_MSG_404',
    'err_5xx':       'ERR_MSG_5XX',
    'err_empty':     'ERR_MSG_EMPTY',
    'err_nomemory':  'ERR_MSG_NOMEMORY',
    'err_parse':     'ERR_MSG_PARSE',
    'err_nocontent': 'ERR_MSG_NOCONTENT',
}

# ---------------------------------------------------------------------------
# Model categories
# ---------------------------------------------------------------------------

_STANDARD_GPT = {
    'gpt-4o', 'gpt-4o-mini',
    'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
    'gpt-4-turbo', 'gpt-3.5-turbo',
}
_O_SERIES = {'o1', 'o1-mini', 'o3', 'o3-mini', 'o4-mini'}

def _model_type(model: str) -> str:
    if model in _O_SERIES:
        return 'reasoning'
    if model in _STANDARD_GPT:
        return 'standard'
    return 'gpt5'

# Responses API placeholders as they appear in the .cpp file
_TOOLS_STR = ',\\"tools\\": [{\\"type\\": \\"web_search_preview\\"}]'
_MSGS      = ',\\"input\\": []}'

def _build_json_chat_str(model: str, temperature: str, max_tokens: str, reasoning_effort: str, use_web_search: bool) -> str:
    mt = _model_type(model)
    if mt == 'reasoning':
        params = f'\\"model\\": \\"{model}\\",\\"max_output_tokens\\": {max_tokens},\\"reasoning_effort\\": \\"{reasoning_effort}\\"'
    elif mt == 'gpt5':
        params = f'\\"model\\": \\"{model}\\",\\"max_output_tokens\\": {max_tokens}'
    else:
        params = f'\\"model\\": \\"{model}\\",\\"temperature\\": {temperature},\\"max_output_tokens\\": {max_tokens}'
    tools = _TOOLS_STR if use_web_search else ''
    return '{' + params + tools + _MSGS


ROOT = Path(__file__).parent.parent
MAIN_CPP = ROOT / "M5Unified_AI_StackChan" / "src" / "main.cpp"
PLATFORMIO_INI = ROOT / "M5Unified_AI_StackChan" / "platformio.ini"
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"

_pio_candidates = [
    ROOT / ".venv" / "Scripts" / "pio.exe",
    ROOT / ".venv" / "Scripts" / "pio",
    ROOT / ".venv" / "bin" / "pio",
]
PIO_CMD = next((str(p) for p in _pio_candidates if p.exists()), shutil.which("pio") or "pio")
PIO_DIR = ROOT / "M5Unified_AI_StackChan"


# ---------------------------------------------------------------------------
# Config read / write
# ---------------------------------------------------------------------------

def read_config() -> dict:
    content = MAIN_CPP.read_text(encoding="utf-8")
    ini = PLATFORMIO_INI.read_text(encoding="utf-8")

    def find(pattern, flags=0):
        m = re.search(pattern, content, flags)
        return m.group(1) if m else ""

    def find_ini(pattern):
        m = re.search(pattern, ini)
        return m.group(1) if m else ""

    use_sdcard      = bool(re.search(r'^#define USE_SDCARD\b',      content, re.MULTILINE))
    servo_auto_move = bool(re.search(r'^#define SERVO_AUTO_MOVE\b', content, re.MULTILINE))

    return {
        "use_sdcard":         use_sdcard,
        "servo_auto_move":    servo_auto_move,
        "wifi_ssid":          find(r'^#define WIFI_SSID "([^"]*)"', re.MULTILINE),
        "wifi_pass":          find(r'^#define WIFI_PASS "([^"]*)"', re.MULTILINE),
        "openai_apikey":      find(r'^#define OPENAI_APIKEY "([^"]*)"', re.MULTILINE),
        "voicevox_apikey":    find(r'^#define VOICEVOX_APIKEY "([^"]*)"', re.MULTILINE),
        "stt_apikey":         find(r'^#define STT_APIKEY "([^"]*)"', re.MULTILINE),
        "servo_x_angle":      find(r'^#define START_DEGREE_VALUE_X (\d+)', re.MULTILINE),
        "servo_y_angle":      find(r'^#define START_DEGREE_VALUE_Y (\d+)', re.MULTILINE),
        "openai_response_buffer": find(r'^#define OPENAI_RESPONSE_BUFFER (\d+)', re.MULTILINE) or '12288',
        "openai_model":        find(r'\\"model\\": \\"([\w.-]+)\\"'),
        "openai_temperature":  find(r'\\"temperature\\": ([\d.]+)') or '0.7',
        "openai_max_tokens":   find(r'\\"max_output_tokens\\": (\d+)') or '500',
        "reasoning_effort":    find(r'\\"reasoning_effort\\": \\"(\w+)\\"') or 'medium',
        "use_web_search":      bool(re.search(r'web_search_preview', content)),
        "system_role":         find(r'^String SYSTEM_ROLE_TEXT = "([^"]*)";', re.MULTILINE),
        "board_env":           find_ini(r'default_envs\s*=\s*(\S+)'),
        **{k: (find(rf'^String {v} = "([^"]*)";', re.MULTILINE) or None)
           for k, v in _ERR_MSGS.items()},
    }


def write_config(cfg: dict) -> None:
    c = MAIN_CPP.read_text(encoding="utf-8")

    def sub(pattern, repl_fn, flags=0):
        nonlocal c
        c = re.sub(pattern, repl_fn, c, flags=flags)

    if "use_sdcard" in cfg:
        if cfg["use_sdcard"]:
            sub(r'^(?://\s*)?#define USE_SDCARD\b', lambda _: '#define USE_SDCARD', re.MULTILINE)
        else:
            sub(r'^#define USE_SDCARD\b', lambda _: '// #define USE_SDCARD', re.MULTILINE)

    if "servo_auto_move" in cfg:
        if cfg["servo_auto_move"]:
            sub(r'^(?://\s*)?#define SERVO_AUTO_MOVE\b', lambda _: '#define SERVO_AUTO_MOVE', re.MULTILINE)
        else:
            sub(r'^#define SERVO_AUTO_MOVE\b', lambda _: '// #define SERVO_AUTO_MOVE', re.MULTILINE)

    if "wifi_ssid" in cfg:
        v = cfg["wifi_ssid"]
        sub(r'^(#define WIFI_SSID ")[^"]*(")', lambda m: m.group(1) + v + m.group(2), re.MULTILINE)
    if "wifi_pass" in cfg:
        v = cfg["wifi_pass"]
        sub(r'^(#define WIFI_PASS ")[^"]*(")', lambda m: m.group(1) + v + m.group(2), re.MULTILINE)
    if "openai_apikey" in cfg:
        v = cfg["openai_apikey"]
        sub(r'^(#define OPENAI_APIKEY ")[^"]*(")', lambda m: m.group(1) + v + m.group(2), re.MULTILINE)
    if "voicevox_apikey" in cfg:
        v = cfg["voicevox_apikey"]
        sub(r'^(#define VOICEVOX_APIKEY ")[^"]*(")', lambda m: m.group(1) + v + m.group(2), re.MULTILINE)
    if "stt_apikey" in cfg:
        v = cfg["stt_apikey"]
        sub(r'^(#define STT_APIKEY ")[^"]*(")', lambda m: m.group(1) + v + m.group(2), re.MULTILINE)
    if "servo_x_angle" in cfg:
        v = str(cfg["servo_x_angle"])
        sub(r'^(#define START_DEGREE_VALUE_X )\d+', lambda m: m.group(1) + v, re.MULTILINE)
    if "servo_y_angle" in cfg:
        v = str(cfg["servo_y_angle"])
        sub(r'^(#define START_DEGREE_VALUE_Y )\d+', lambda m: m.group(1) + v, re.MULTILINE)
    if "tts_speaker_no" in cfg:
        v = str(cfg["tts_speaker_no"])
        sub(r'(String TTS_SPEAKER_NO = ")\d+(")', lambda m: m.group(1) + v + m.group(2))
    if "openai_response_buffer" in cfg:
        v = str(cfg["openai_response_buffer"])
        sub(r'^(#define OPENAI_RESPONSE_BUFFER )\d+', lambda m: m.group(1) + v, re.MULTILINE)
    if "system_role" in cfg:
        v = cfg["system_role"].replace('\\', '\\\\').replace('"', '\\"')
        sub(r'^(String SYSTEM_ROLE_TEXT = ")[^"]*(")', lambda m: m.group(1) + v + m.group(2), re.MULTILINE)
    for cfg_key, cpp_var in _ERR_MSGS.items():
        if cfg_key in cfg:
            v = cfg[cfg_key].replace('\\', '\\\\').replace('"', '\\"')
            sub(rf'^(String {cpp_var} = ")[^"]*(")',
                lambda m, v=v: m.group(1) + v + m.group(2), re.MULTILINE)
    _JSON_KEYS = {'openai_model', 'openai_temperature', 'openai_max_tokens', 'reasoning_effort', 'use_web_search'}
    if _JSON_KEYS & set(cfg.keys()):
        def _extract(pattern, default=''):
            m = re.search(pattern, c)
            return m.group(1) if m else default
        model      = str(cfg.get('openai_model',      _extract(r'\\"model\\": \\"([\w.-]+)\\"', 'gpt-4o-mini')))
        temp       = str(cfg.get('openai_temperature', _extract(r'\\"temperature\\": ([\d.]+)', '0.7')))
        tokens     = str(cfg.get('openai_max_tokens',  _extract(r'\\"max_output_tokens\\": (\d+)') or '500'))
        effort     = str(cfg.get('reasoning_effort',   _extract(r'\\"reasoning_effort\\": \\"(\w+)\\"', 'medium')))
        web_search = bool(cfg.get('use_web_search', bool(re.search(r'web_search_preview', c))))
        new_str = _build_json_chat_str(model, temp, tokens, effort, web_search)
        sub(r'^String json_ChatString = .*?;$',
            lambda _: f'String json_ChatString = "{new_str}";',
            re.MULTILINE)

    MAIN_CPP.write_text(c, encoding="utf-8")

    if "board_env" in cfg:
        ini = PLATFORMIO_INI.read_text(encoding="utf-8")
        v = cfg["board_env"]
        ini = re.sub(r'(default_envs\s*=\s*)\S+', lambda m: m.group(1) + v, ini)
        PLATFORMIO_INI.write_text(ini, encoding="utf-8")


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

async def api_get_config(request: Request) -> JSONResponse:
    return JSONResponse(read_config())


async def api_post_config(request: Request) -> JSONResponse:
    data = await request.json()
    write_config(data)
    return JSONResponse({"ok": True})


async def api_ports(request: Request) -> JSONResponse:
    ports = [{"port": p.device, "desc": p.description}
             for p in serial.tools.list_ports.comports()]
    return JSONResponse(ports)


async def _sse_stream(cmd: list, cwd: Path):
    q: queue.Queue = queue.Queue()

    def _run():
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(cwd),
        )
        for raw in proc.stdout:
            q.put(raw)
        proc.stdout.close()
        q.put({"exit": proc.wait()})

    async def generator():
        loop = asyncio.get_event_loop()
        threading.Thread(target=_run, daemon=True).start()
        while True:
            item = await loop.run_in_executor(None, q.get)
            if isinstance(item, dict):
                yield f"data: {json.dumps(item)}\n\n"
                break
            yield f"data: {json.dumps(item.decode('utf-8', errors='replace'))}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def api_voice(request: Request) -> JSONResponse:
    data = await request.json()
    speaker = data.get("speaker")
    if not isinstance(speaker, int) or not (0 <= speaker <= 60):
        return JSONResponse({"error": "speaker must be an integer 0–60"}, status_code=400)
    url = f"http://stack-chan.local/setting?speaker={speaker}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return JSONResponse({"ok": True, "response": body})
    except (urllib.error.URLError, OSError) as exc:
        return JSONResponse(
            {"error": f"デバイスが見つかりません。同一ネットワークに接続されていることを確認してください ({exc})"},
            status_code=502,
        )


async def api_build(request: Request):
    return await _sse_stream([PIO_CMD, "run"], PIO_DIR)


async def api_upload(request: Request):
    port = request.query_params.get("port", "")
    cmd = [PIO_CMD, "run", "--target", "upload"]
    if port:
        cmd += ["--upload-port", port]
    return await _sse_stream(cmd, PIO_DIR)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

routes = [
    Route("/api/config", api_get_config, methods=["GET"]),
    Route("/api/config", api_post_config, methods=["POST"]),
    Route("/api/ports", api_ports, methods=["GET"]),
    Route("/api/voice", api_voice, methods=["POST"]),
    Route("/api/build", api_build, methods=["GET"]),
    Route("/api/upload", api_upload, methods=["GET"]),
]

if FRONTEND_DIST.exists():
    routes.append(Mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True)))

app = Starlette(routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    print(f"PIO command: {PIO_CMD}")
    print(f"Serving at http://localhost:8080")
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True, reload_dirs=[str(Path(__file__).parent)])
