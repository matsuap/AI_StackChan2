# AI スタックチャン 設定 Web UI

## セットアップ

### 1. フロントエンドビルド（初回のみ）

```powershell
cd webui\frontend
npm install
npm run build
```

### 2. バックエンド起動

```powershell
cd C:\Users\taish\Development\AI_StackChan2
.venv\Scripts\python webui\app.py
```

ブラウザで `http://localhost:8080` を開く。

---

## 開発モード（ホットリロードあり）

ターミナル 1:
```powershell
cd C:\Users\taish\Development\AI_StackChan2
.venv\Scripts\python webui\app.py
```

ターミナル 2:
```powershell
cd webui\frontend
npm run dev
```

ブラウザで `http://localhost:5173` を開く（Vite dev server、API は :8080 にプロキシ）。

---

## 設定内容

| 項目 | 変更先ファイル |
|------|---------------|
| WiFi SSID / Pass | `src/main.cpp` の `#define` |
| API キー | `src/main.cpp` の `#define` |
| OpenAI モデル / temperature / max_tokens | `src/main.cpp` の `json_ChatString` |
| TTS スピーカー番号 | `src/main.cpp` の `TTS_SPEAKER_NO` |
| サーボ初期角度 X/Y | `src/main.cpp` の `#define START_DEGREE_VALUE_*` |
| ボード選択 | `platformio.ini` の `default_envs` |

**保存後はビルド & 書き込みが必要。**
