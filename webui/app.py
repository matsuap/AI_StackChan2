import asyncio
import json
import re
import shutil
from pathlib import Path

import serial.tools.list_ports
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

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

# Messages placeholder as it appears in the .cpp file
_MSGS = ',\\"messages\\": [{\\"role\\": \\"user\\", \\"content\\": \\"' + '""' + '\\"' + '}]}'

def _build_json_chat_str(model: str, temperature: str, max_tokens: str, reasoning_effort: str) -> str:
    mt = _model_type(model)
    if mt == 'reasoning':
        params = f'\\"model\\": \\"{model}\\",\\"max_completion_tokens\\": {max_tokens},\\"reasoning_effort\\": \\"{reasoning_effort}\\"'
    elif mt == 'gpt5':
        params = f'\\"model\\": \\"{model}\\",\\"max_completion_tokens\\": {max_tokens}'
    else:
        params = f'\\"model\\": \\"{model}\\",\\"temperature\\": {temperature},\\"max_tokens\\": {max_tokens}'
    return '{' + params + _MSGS


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
        "tts_speaker_no":     find(r'String TTS_SPEAKER_NO = "(\d+)";'),
        "openai_model":        find(r'\\"model\\": \\"([\w.-]+)\\"'),
        "openai_temperature":  find(r'\\"temperature\\": ([\d.]+)') or '0.7',
        "openai_max_tokens":   (find(r'\\"max_tokens\\": (\d+)') or
                                find(r'\\"max_completion_tokens\\": (\d+)') or '500'),
        "reasoning_effort":    find(r'\\"reasoning_effort\\": \\"(\w+)\\"') or 'medium',
        "board_env":           find_ini(r'default_envs\s*=\s*(\S+)'),
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
    _JSON_KEYS = {'openai_model', 'openai_temperature', 'openai_max_tokens', 'reasoning_effort'}
    if _JSON_KEYS & set(cfg.keys()):
        def _extract(pattern, default=''):
            m = re.search(pattern, c)
            return m.group(1) if m else default
        model     = str(cfg.get('openai_model',      _extract(r'\\"model\\": \\"([\w.-]+)\\"', 'gpt-4o-mini')))
        temp      = str(cfg.get('openai_temperature', _extract(r'\\"temperature\\": ([\d.]+)', '0.7')))
        tokens    = str(cfg.get('openai_max_tokens',  _extract(r'\\"max_tokens\\": (\d+)') or
                                                      _extract(r'\\"max_completion_tokens\\": (\d+)') or '500'))
        effort    = str(cfg.get('reasoning_effort',   _extract(r'\\"reasoning_effort\\": \\"(\w+)\\"', 'medium')))
        new_str   = _build_json_chat_str(model, temp, tokens, effort)
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
    async def generator():
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(cwd),
        )
        async for line in proc.stdout:
            text = line.decode("utf-8", errors="replace")
            yield f"data: {json.dumps(text)}\n\n"
        code = await proc.wait()
        yield f"data: {json.dumps({'exit': code})}\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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
    uvicorn.run(app, host="0.0.0.0", port=8080)
