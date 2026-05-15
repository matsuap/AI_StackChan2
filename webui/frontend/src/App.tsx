import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

interface Config {
  use_sdcard: boolean
  servo_auto_move: boolean
  wifi_ssid: string
  wifi_pass: string
  openai_apikey: string
  voicevox_apikey: string
  stt_apikey: string
  openai_model: string
  openai_temperature: string
  openai_max_tokens: string
  reasoning_effort: string
  tts_speaker_no: string
  servo_x_angle: string
  servo_y_angle: string
  board_env: string
}

interface Port {
  port: string
  desc: string
}

type SaveState = 'idle' | 'saving' | 'ok' | 'error'
type ModelType = 'standard' | 'gpt5' | 'reasoning'

const MODEL_GROUPS: { label: string; models: string[]; type: ModelType }[] = [
  { label: 'GPT-4o シリーズ', type: 'standard', models: ['gpt-4o', 'gpt-4o-mini'] },
  { label: 'GPT-4.1 シリーズ', type: 'standard', models: ['gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano'] },
  { label: 'GPT-5 シリーズ', type: 'gpt5',     models: ['gpt-5', 'gpt-5-mini', 'gpt-5-nano', 'gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini'] },
  { label: 'O シリーズ (推論モデル)', type: 'reasoning', models: ['o4-mini', 'o3', 'o3-mini', 'o1', 'o1-mini'] },
  { label: 'レガシー', type: 'standard', models: ['gpt-4-turbo', 'gpt-3.5-turbo'] },
]

function getModelType(model: string): ModelType {
  for (const g of MODEL_GROUPS) {
    if (g.models.includes(model)) return g.type
  }
  return 'standard'
}

const TTS_SPEAKERS: { no: string; name: string }[] = [
  { no: '0',  name: '四国めたん（あまあま）' },
  { no: '1',  name: 'ずんだもん（あまあま）' },
  { no: '2',  name: '四国めたん（ノーマル）' },
  { no: '3',  name: 'ずんだもん（ノーマル）' },
  { no: '4',  name: '四国めたん（セクシー）' },
  { no: '5',  name: 'ずんだもん（セクシー）' },
  { no: '6',  name: '四国めたん（ツンツン）' },
  { no: '7',  name: 'ずんだもん（ツンツン）' },
  { no: '8',  name: '春日部つむぎ（ノーマル）' },
  { no: '9',  name: '波音リツ（ノーマル）' },
  { no: '10', name: '雨晴はう（ノーマル）' },
  { no: '11', name: '玄野武宏（ノーマル）' },
  { no: '12', name: '白上虎太郎（ふつう）' },
  { no: '13', name: '青山龍星（ノーマル）' },
  { no: '14', name: '冥鳴ひまり（ノーマル）' },
  { no: '15', name: '九州そら（あまあま）' },
  { no: '16', name: '九州そら（ノーマル）' },
  { no: '17', name: '九州そら（セクシー）' },
  { no: '18', name: '九州そら（ツンツン）' },
  { no: '19', name: '九州そら（ささやき）' },
  { no: '20', name: 'もち子(cv 明日葉よもぎ)' },
  { no: '21', name: '剣崎雌雄（ノーマル）' },
  { no: '22', name: 'ずんだもん（ささやき）' },
  { no: '23', name: 'WhiteCUL（ノーマル）' },
  { no: '24', name: 'WhiteCUL（たのしい）' },
  { no: '25', name: 'WhiteCUL（かなしい）' },
  { no: '26', name: 'WhiteCUL（びえーん）' },
  { no: '27', name: '後鬼（人間ver.）' },
  { no: '28', name: '後鬼（ぬいぐるみver.）' },
  { no: '29', name: 'No.7（ノーマル）' },
  { no: '30', name: 'No.7（アナウンス）' },
  { no: '31', name: 'No.7（読み聞かせ）' },
  { no: '32', name: '白上虎太郎（わーい）' },
  { no: '33', name: '白上虎太郎（びくびく）' },
  { no: '34', name: '白上虎太郎（おこ）' },
  { no: '35', name: '白上虎太郎（びえーん）' },
  { no: '36', name: '四国めたん（ささやき）' },
  { no: '37', name: '四国めたん（ヒソヒソ）' },
  { no: '38', name: 'ずんだもん（ヒソヒソ）' },
  { no: '39', name: '玄野武宏（喜び）' },
  { no: '40', name: '玄野武宏（ツンギレ）' },
  { no: '41', name: '玄野武宏（悲しみ）' },
  { no: '42', name: 'ちび式じい（ノーマル）' },
  { no: '43', name: '櫻歌ミコ（ノーマル）' },
  { no: '44', name: '櫻歌ミコ（第二形態）' },
  { no: '45', name: '櫻歌ミコ（ロリ）' },
  { no: '46', name: '小夜/SAYO（ノーマル）' },
  { no: '47', name: 'ナースロボ＿タイプＴ（ノーマル）' },
  { no: '48', name: 'ナースロボ＿タイプＴ（楽々）' },
  { no: '49', name: 'ナースロボ＿タイプＴ（恐怖）' },
  { no: '50', name: 'ナースロボ＿タイプＴ（内緒話）' },
  { no: '51', name: '†聖騎士 紅桜†（ノーマル）' },
  { no: '52', name: '雀松朱司（ノーマル）' },
  { no: '53', name: '麒ヶ島宗麟（ノーマル）' },
  { no: '54', name: '春歌ナナ（ノーマル）' },
  { no: '55', name: '猫使アル（ノーマル）' },
  { no: '56', name: '猫使アル（おちつき）' },
  { no: '57', name: '猫使アル（うきうき）' },
  { no: '58', name: '猫使ビィ（ノーマル）' },
  { no: '59', name: '猫使ビィ（おちつき）' },
  { no: '60', name: '猫使ビィ（人見知り）' },
]

function lineClass(line: string): string {
  if (/error|FAILED|Error/i.test(line)) return 'term-line err'
  if (/warning|Warning/i.test(line)) return 'term-line warn'
  if (/success|SUCCESS|Linking|Compiling|Finished/i.test(line)) return 'term-line ok'
  return 'term-line'
}

export default function App() {
  const [cfg, setCfg] = useState<Config>({
    use_sdcard: true,
    servo_auto_move: false,
    wifi_ssid: '', wifi_pass: '',
    openai_apikey: '', voicevox_apikey: '', stt_apikey: '',
    openai_model: 'gpt-4o-mini', openai_temperature: '0.7', openai_max_tokens: '500',
    reasoning_effort: 'medium',
    tts_speaker_no: '3',
    servo_x_angle: '90', servo_y_angle: '65',
    board_env: 'm5stack-core2',
  })
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [ports, setPorts] = useState<Port[]>([])
  const [selectedPort, setSelectedPort] = useState('')
  const [terminal, setTerminal] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const termRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    fetch('/api/config').then(r => r.json()).then(setCfg)
    loadPorts()
  }, [])

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight
  }, [terminal])

  const loadPorts = () => {
    fetch('/api/ports').then(r => r.json()).then((data: Port[]) => {
      setPorts(data)
      if (data.length > 0) setSelectedPort(p => p || data[0].port)
    })
  }

  const set = (key: keyof Config) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setCfg(prev => ({ ...prev, [key]: e.target.value }))

  const saveConfig = async () => {
    setSaveState('saving')
    try {
      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg),
      })
      setSaveState(res.ok ? 'ok' : 'error')
    } catch {
      setSaveState('error')
    }
    setTimeout(() => setSaveState('idle'), 3000)
  }

  const runStream = useCallback((url: string) => {
    esRef.current?.close()
    setTerminal([])
    setRunning(true)
    const es = new EventSource(url)
    esRef.current = es
    es.onmessage = e => {
      const data = JSON.parse(e.data) as string | { exit: number }
      if (typeof data === 'object' && 'exit' in data) {
        setTerminal(prev => [...prev, `\n[終了コード: ${data.exit}]`])
        setRunning(false)
        es.close()
      } else {
        setTerminal(prev => [...prev, data as string])
      }
    }
    es.onerror = () => { setRunning(false); es.close() }
  }, [])

  const saveLabel =
    saveState === 'saving' ? '保存中…' :
    saveState === 'ok'     ? '保存完了 ✓' :
    saveState === 'error'  ? '保存失敗 ✗' : '設定を保存'

  const modelType = getModelType(cfg.openai_model)
  const tokenLabel = modelType === 'standard' ? 'Max Tokens' : 'Max Completion Tokens'

  return (
    <div className="app">
      <header>
        <h1>AI スタックチャン 設定ツール</h1>
        <button
          className={`btn-save ${saveState}`}
          onClick={saveConfig}
          disabled={saveState === 'saving'}
        >
          {saveLabel}
        </button>
      </header>

      <main>
        {/* SD card toggle */}
        <section className="card">
          <h2>WiFi / API キー 設定ソース</h2>
          <div className="toggle-row">
            <button
              className={`toggle-btn ${cfg.use_sdcard ? 'active' : ''}`}
              onClick={() => setCfg(prev => ({ ...prev, use_sdcard: true }))}
            >
              SD カードから読む
            </button>
            <button
              className={`toggle-btn ${!cfg.use_sdcard ? 'active' : ''}`}
              onClick={() => setCfg(prev => ({ ...prev, use_sdcard: false }))}
            >
              ファームに埋め込む
            </button>
          </div>
          {cfg.use_sdcard ? (
            <p className="toggle-note">
              起動時に SD カードの <code>/wifi.txt</code> と <code>/apikey.txt</code> を読み込みます。
              以下の WiFi / API キー入力欄は使用されません。
            </p>
          ) : (
            <p className="toggle-note warn">
              WiFi パスワードと API キーがファームバイナリに埋め込まれます。
              SD カード不要になりますが、フラッシュダンプで読み出し可能です。
            </p>
          )}
        </section>

        {/* WiFi */}
        {!cfg.use_sdcard && (
          <section className="card">
            <h2>WiFi 設定</h2>
            <div className="form-grid">
              <label>SSID</label>
              <input value={cfg.wifi_ssid} onChange={set('wifi_ssid')} placeholder="MyNetwork" />
              <label>パスワード</label>
              <input type="password" value={cfg.wifi_pass} onChange={set('wifi_pass')} placeholder="password" />
            </div>
          </section>
        )}

        {/* API Keys */}
        {!cfg.use_sdcard && (
          <section className="card">
            <h2>API キー</h2>
            <div className="form-grid">
              <label>OpenAI</label>
              <input value={cfg.openai_apikey} onChange={set('openai_apikey')} placeholder="sk-..." spellCheck={false} />
              <label>VoiceVox</label>
              <input value={cfg.voicevox_apikey} onChange={set('voicevox_apikey')} placeholder="VoiceVox API Key" spellCheck={false} />
              <label>STT (Google)</label>
              <input value={cfg.stt_apikey} onChange={set('stt_apikey')} placeholder="Speech-to-Text API Key" spellCheck={false} />
            </div>
          </section>
        )}

        {/* OpenAI */}
        <section className="card">
          <h2>OpenAI 設定</h2>
          <div className="form-grid">
            <label>モデル</label>
            <select value={cfg.openai_model} onChange={set('openai_model')}>
              {MODEL_GROUPS.map(g => (
                <optgroup key={g.label} label={g.label}>
                  {g.models.map(m => <option key={m} value={m}>{m}</option>)}
                </optgroup>
              ))}
            </select>

            {/* model-type badge */}
            <label></label>
            <span className={`model-badge ${modelType}`}>
              {modelType === 'standard'  && 'temperature 対応'}
              {modelType === 'gpt5'      && 'temperature 非対応'}
              {modelType === 'reasoning' && '推論モデル — reasoning_effort 使用'}
            </span>

            {/* Temperature — standard のみ */}
            {modelType === 'standard' && (<>
              <label>Temperature</label>
              <div className="inline-row">
                <input type="range" min="0" max="2" step="0.1"
                  value={cfg.openai_temperature} onChange={set('openai_temperature')} className="slider" />
                <input type="number" min="0" max="2" step="0.1"
                  value={cfg.openai_temperature} onChange={set('openai_temperature')} className="num-small" />
              </div>
            </>)}

            {/* Reasoning effort — o-series のみ */}
            {modelType === 'reasoning' && (<>
              <label>Reasoning Effort</label>
              <div className="toggle-row compact">
                {(['low', 'medium', 'high'] as const).map(e => (
                  <button key={e}
                    className={`toggle-btn ${cfg.reasoning_effort === e ? 'active' : ''}`}
                    onClick={() => setCfg(prev => ({ ...prev, reasoning_effort: e }))}
                  >
                    {e}
                  </button>
                ))}
              </div>
            </>)}

            <label>{tokenLabel}</label>
            <input type="number" min="1" max="128000" step="1"
              value={cfg.openai_max_tokens} onChange={set('openai_max_tokens')} className="num-small" />
          </div>
        </section>

        {/* TTS */}
        <section className="card">
          <h2>TTS 設定 (VoiceVox)</h2>
          <div className="form-grid">
            <label>話者</label>
            <select
              value={cfg.tts_speaker_no}
              onChange={set('tts_speaker_no')}
            >
              {TTS_SPEAKERS.map(s => (
                <option key={s.no} value={s.no}>
                  {s.no}: {s.name}
                </option>
              ))}
            </select>
          </div>
        </section>

        {/* Hardware */}
        <section className="card">
          <h2>ハードウェア設定</h2>
          <div className="form-grid">
            <label>自発移動</label>
            <div>
              <div className="toggle-row compact">
                <button
                  className={`toggle-btn ${!cfg.servo_auto_move ? 'active' : ''}`}
                  onClick={() => setCfg(prev => ({ ...prev, servo_auto_move: false }))}
                >
                  固定（初期位置）
                </button>
                <button
                  className={`toggle-btn ${cfg.servo_auto_move ? 'active' : ''}`}
                  onClick={() => setCfg(prev => ({ ...prev, servo_auto_move: true }))}
                >
                  自発移動 ON
                </button>
              </div>
              {!cfg.servo_auto_move && (
                <p className="toggle-note" style={{ marginTop: 6 }}>
                  サーボは初期角度で固定。アバターの視線には追従しません。
                </p>
              )}
            </div>
            <label>ボード</label>
            <select value={cfg.board_env} onChange={set('board_env')}>
              <option value="m5stack-core2">M5Stack Core2</option>
              <option value="esp32-s3-devkitc-1">M5Stack CoreS3</option>
            </select>
            <label>サーボX 初期角度</label>
            <div className="inline-row">
              <input type="range" min="0" max="180" step="1"
                value={cfg.servo_x_angle} onChange={set('servo_x_angle')} className="slider" />
              <input type="number" min="0" max="180"
                value={cfg.servo_x_angle} onChange={set('servo_x_angle')} className="num-small" />
              <span className="unit">°</span>
            </div>
            <label>サーボY 初期角度</label>
            <div className="inline-row">
              <input type="range" min="0" max="180" step="1"
                value={cfg.servo_y_angle} onChange={set('servo_y_angle')} className="slider" />
              <input type="number" min="0" max="180"
                value={cfg.servo_y_angle} onChange={set('servo_y_angle')} className="num-small" />
              <span className="unit">°</span>
            </div>
          </div>
        </section>

        {/* Build & Flash */}
        <section className="card">
          <h2>ビルド & 書き込み</h2>
          <div className="flash-bar">
            <select
              value={selectedPort}
              onChange={e => setSelectedPort(e.target.value)}
              className="port-select"
            >
              {ports.length === 0
                ? <option value="">-- ポートなし --</option>
                : ports.map(p => (
                  <option key={p.port} value={p.port}>{p.port}  {p.desc}</option>
                ))
              }
            </select>
            <button className="btn-sm" onClick={loadPorts} title="ポート更新">↻</button>
            <button className="btn-build" disabled={running}
              onClick={() => runStream('/api/build')}>
              ビルド
            </button>
            <button className="btn-flash" disabled={running || !selectedPort}
              onClick={() => runStream(`/api/upload?port=${encodeURIComponent(selectedPort)}`)}>
              書き込み
            </button>
            {running && <span className="running-dot" />}
          </div>

          <div className="terminal" ref={termRef}>
            {terminal.length === 0
              ? <span className="term-empty">ビルド / 書き込みのログがここに表示されます</span>
              : terminal.map((line, i) => (
                <span key={i} className={lineClass(line)}>{line}</span>
              ))
            }
          </div>
        </section>
      </main>
    </div>
  )
}
