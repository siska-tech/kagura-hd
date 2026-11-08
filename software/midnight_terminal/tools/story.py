"""MIDNIGHT TERMINAL script: every text and its timing (ms). Shared by the
visuals (generated/script.inc) and the synthesizer (typing clicks, cues)."""

CHAR_MS = 45           # dialogue typing speed
TERM_CHAR_MS = 32      # terminal typing speed

TITLE = "MIDNIGHT TERMINAL"
SUBTITLE = "雨の夜、閉店まであと少し。"

# (start_ms, speaker, text)  speaker: 'mio' or '' (narration)
DIALOGUE = [
    (13500, 'mio', "いらっしゃいませ。……雨、ひどくなってきましたね。"),
    (19500, 'mio', "終電、もう行っちゃいましたよ。始発まで、ゆっくりしていってください。"),
    (26500, 'mio', "何か、お出ししましょうか？"),
    (39000, 'mio', "あれは……前のオーナーが残していった端末なんです。"),
    (86000, 'mio', "……お客さん？"),
    (90000, 'mio', "……ご注文は、お決まりですか？"),
]
SPEAKER = "ミオ"

CHOICES = ["ブレンドを一杯", "この店のこと", "あの古い端末"]
CHOICE_SHOW, CHOICE_MOVES, CHOICE_PICK = 31500, (33500, 35000), 37000

# terminal close-up: (start_ms, text); typed at TERM_CHAR_MS
TERMINAL = [
    (46200, "NOCT TERMINAL  v0.9"),
    (47200, "MEMORY ARCHIVE  READY"),
    (48600, "> LOGIN guest"),
    (50000, "> 来店記録を検索しています"),
    (51800, "  0047件目：雨の夜、カウンター席"),
    (53400, "  照合中……"),
    (55000, "  照合結果：あなたは既に退店しています"),
]
GLITCH_START = 56000

# anomaly flood (misaki 8px), cycled
LOGS = ["SYSTEM ANOMALY // 0x09", "警告：記憶領域に不明な応答を検出", "第四観測層との同期に失敗しました",
        "復旧処理を開始します", "ERR_0x04F2 : 存在しない座標", "ERR_0x04F3 : 認識不能な音声",
        "ERR_0x04F4 : 未定義の観測者", "FRAMEBUFFER DESYNC", "PSRAM BANK 01 : UNKNOWN",
        "CURSOR POSITION : OUT OF REALITY", "AUDIO CHANNEL 02 : VOICE DETECTED", "接続先：■■■■■■■■",
        "応答者：該当なし", "この画面を閉じないでください", "SYSTEM RECONSTRUCTION...",
        "MEMORY INTEGRITY : UNKNOWN", "時刻補正：昨日の明日を参照しています", "雨音の所有者が見つかりません",
        "空席から注文を受信しました", "記録には存在しない会話です", "観測者の輪郭を再計算しています",
        "帰還先：閉店後の午前零時", "保存された沈黙が上限を超えました", "未送信の返事を検出しました",
        "店内人数：一名／影の数：二名", "名前のない記憶を保護しています", "出口の座標は移動しています",
        "同じ質問を繰り返さないでください", "あなたの到着を再生しています", "受信時刻：まだ起きていない夜",
        "観測終了を拒否されました"]
ANOMALY_START, ANOMALY_FULL, ANOMALY_END = 58500, 63000, 74000

MESSAGE = "警告：この記憶はあなたのものではありません"
MESSAGE_START, MESSAGE_CHAR_MS, MESSAGE_END = 75500, 110, 83000

RESTORE_START = 83000
RED_EYES = (94500, 94800)
END_CARD = 96500
END_LINES = ["MIDNIGHT TERMINAL", "FM SYNTHESIS / 4 OPERATORS X 7 VOICES / 48 KHZ STREAM",
             "KAGURA-HD  -  TANG NANO 9K + RP2040"]
END_MS = 104000

# scene boundaries (ms)
SCENES = [("title", 0), ("bar", 11000), ("terminal", 45000), ("anomaly", ANOMALY_START),
          ("message", 74000), ("restore", RESTORE_START), ("end", END_CARD)]

def all_text():
    parts = [SUBTITLE, SPEAKER]+[t for _, _, t in DIALOGUE]+CHOICES+[t for _, t in TERMINAL]+[MESSAGE]
    return ''.join(parts), ''.join(LOGS)
