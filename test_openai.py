"""
OpenAI API疎通テスト
使い方: python test_openai.py <APIキー> [モデル名]
"""
import json
import sys
import urllib.request
import urllib.error

api_key = sys.argv[1] if len(sys.argv) > 1 else input("OpenAI APIキー: ").strip()
model   = sys.argv[2] if len(sys.argv) > 2 else "gpt-4o-mini"

# テストするJSONパターン一覧
payloads = [
    {
        "label": "最小構成（temperature+max_tokens）",
        "body": {
            "model": model,
            "temperature": 0.7,
            "max_tokens": 100,
            "messages": [
                {"role": "system", "content": "あなたはスタックチャンです。短く答えてください。"},
                {"role": "user",   "content": "こんにちは"},
            ],
        },
    },
    {
        "label": "max_completion_tokens（GPT-5系）",
        "body": {
            "model": model,
            "max_completion_tokens": 100,
            "messages": [
                {"role": "system", "content": "あなたはスタックチャンです。短く答えてください。"},
                {"role": "user",   "content": "こんにちは"},
            ],
        },
    },
    {
        "label": "tools: web_search_preview あり",
        "body": {
            "model": model,
            "max_completion_tokens": 100,
            "tools": [{"type": "web_search_preview"}],
            "messages": [
                {"role": "system", "content": "あなたはスタックチャンです。短く答えてください。"},
                {"role": "user",   "content": "今日の天気は？"},
            ],
        },
    },
]

url = "https://api.openai.com/v1/chat/completions"

for p in payloads:
    print(f"\n{'='*60}")
    print(f"[{p['label']}]")
    data = json.dumps(p["body"]).encode()
    req  = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = json.loads(res.read())
            content = body["choices"][0]["message"].get("content", "(contentなし)")
            print(f"✓ 成功: {content[:80]}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"✗ HTTP {e.code}: {body}")
    except Exception as e:
        print(f"✗ エラー: {e}")
