Import("env")
import serial.tools.list_ports
import sys

try:
    from SCons.Script import COMMAND_LINE_TARGETS
    is_upload = any("upload" in str(t).lower() for t in COMMAND_LINE_TARGETS)
except Exception:
    is_upload = "upload" in " ".join(sys.argv).lower()

if is_upload:
    try:
        port = env.GetProjectOption("upload_port")
    except Exception:
        port = None

    available = [p.device for p in serial.tools.list_ports.comports()]

    if port:
        if port not in available:
            sys.stderr.write(
                f"\n[ERROR] Upload port '{port}' not found — build aborted.\n"
                f"        Available: {available or ['(none)']}\n\n"
            )
            env.Exit(1)
        else:
            print(f"[check_port] {port} OK")
    else:
        # Auto-detect M5Stack (CP2104: VID=0x10C4, CH340/CH9102: VID=0x1A86)
        m5 = [p for p in serial.tools.list_ports.comports()
              if p.vid in (0x10C4, 0x1A86)]
        if not m5:
            sys.stderr.write(
                f"\n[ERROR] M5Stack not connected — build aborted.\n"
                f"        Available ports: {available or ['(none)']}\n\n"
            )
            env.Exit(1)
        print(f"[check_port] M5Stack found at {m5[0].device}")
