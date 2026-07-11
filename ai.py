import scratchattach as sa
import requests
import urllib.parse
import time  # 【追加】送信の合間に少し待つためのタイマー機能

# ================= [設定エリア] =================
USERNAME = "ZZZBanana"
PASSWORD = "Walworth1"
PROJECT_ID = "1352722752"
# ===============================================

def numbers_to_text(number_string):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.?!,'"
    text = ""
    if len(number_string) % 2 != 0:
        number_string += "0"
    for i in range(0, len(number_string), 2):
        code_str = number_string[i:i+2]
        if not code_str or len(code_str) < 2:
            continue
        try:
            code = int(code_str)
            if code == 78:
                text += " "
            else:
                index = code - 9 - 1 
                if 0 <= index < len(alphabet):
                    text += alphabet[index]
        except:
            pass
    return text

def text_to_numbers(text):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.?!,'"
    encoded = ""
    for char in text:
        if char == " ":
            encoded += "78"
        elif char in alphabet:
            code = alphabet.index(char) + 1 + 9
            encoded += str(code)
        else:
            encoded += "76"
    return encoded

session = sa.login(USERNAME, PASSWORD)
conn = session.connect_cloud(PROJECT_ID)
print(f"ログイン成功: {session.username}")

events = conn.events()

@events.event
def on_set(activity):
    if activity.var == "trigger":
        if activity.value == "0" or activity.value == "":
            return
            
        print("\n=== [実況] 1. ☁ trigger への質問入力を検知しました！ ===")
        try:
            # 1. Scratchからの暗号を英語に戻す
            user_question = numbers_to_text(activity.value)+"(don't use symbols or line breaking. The answer should be lower than 850 letters)"
            print(f"=== [実況] 2. 翻訳した質問: 「{user_question}」 ===")
            
            # 【バグ修正】URLを文字で直接くっつけず、requestsに安全に組み立てさせます。
            # これにより、文字が「aihi」になって繋がらなくなるエラーを100%防ぎます。
            url = f"https://text.pollinations.ai/{urllib.parse.quote(user_question)}"
            payload = {'model': 'openai'}
            
            print(f"=== [実況] 3. 確実に届くURLでAIに接続します... ===")
            response = requests.get(url, params=payload, timeout=60)
            print(f"=== [実況] 4. AIの応答コード: {response.status_code} ===")
            
            if response.status_code == 200:
                ai_reply = response.text.strip()
                print(f"=== [実況] 5. AIの生回答: 「{ai_reply}」 ===")
                
                if "<html" in ai_reply.lower() or "<doctype" in ai_reply.lower():
                    print("❌ [エラー] AIがエラー画面(HTML)を返しました。")
                    return
                
                # アルファベット作戦で暗号化
                number_string = text_to_numbers(ai_reply)
                print(f"=== [実況] 6. 返答全体の暗号化結果 (総数字数: {len(number_string)}文字) ===")
                
                # 【新ノード】文字分割送信システム
                # Scratchの上限である256文字を超えないように、240文字ずつに切り分けます。
                chunk_size = 240
                total_length = len(number_string)
                
                print(f"=== [実況] 7. 分割送信を開始します（サイズ: {chunk_size}文字ずつ） ===")
                
                for i in range(0, total_length, chunk_size):
                    chunk = number_string[i:i+chunk_size]
                    print(f"   -> ☁ text_from_python に送信中: {chunk[:20]}...")
                    conn.set_var("text_from_python", chunk)
                    # Scratchが変数の変化を読み取るための重要なウェイト（0.5秒）
                    time.sleep(1)
                
                # 【重要】すべての分割送信が終わった合図として "00" を送る
                print("=== [実況] 8. すべてのデータを送り終えたため、終了合図 '00' を送信します ===")
                conn.set_var("text_from_python", "00")
                time.sleep(0.5)
                
                print("✨ [大成功] すべての分割データをScratchに送信完了しました！")
                
            else:
                print(f"❌ [エラー] サーバーエラー: {response.status_code}")
        except Exception as e:
            print(f"❌ [重大エラー] 処理中にクラッシュしました: {e}")
            
        finally:
            conn.set_var("trigger", "0")
            print("=== [実況] 9. triggerを0に戻し、次の待機状態に入りました ===")

print("Scratchからの質問入力を待っています...（分割送信ノード実装・URLバグ修正版）")
events.start()