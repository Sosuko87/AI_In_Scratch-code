import scratchattach as sa
import requests
import urllib.parse
import time
import os

# ================= [設定エリア] =================
USERNAME = os.environ.get('SCRATCH_USERNAME')
PASSWORD = os.environ.get('SCRATCH_PASSWORD')
PROJECT_ID = 1352722752
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
            encoded += "79"
    return encoded

session = sa.login(USERNAME, PASSWORD)
conn = session.connect_cloud(PROJECT_ID)
print(f"ログイン成功: {session.username}")

events = conn.events()

@events.event
def on_set(activity):
    # どのトリガー変数が変わったかを判定する (trigger1, trigger2, trigger3, trigger4)
    if activity.var in ["trigger1", "trigger2", "trigger3", "trigger4"]:
        if len(activity.value) == 1:
            return
            
        # 変数名から現在の部屋番号（1〜4）を自動抽出する
        room_num = activity.var.replace("trigger", "")
        trigger_var = f"trigger{room_num}"
        text_var = f"text_from_python{room_num}"
        
        print(f"\n=== [実況] 1. ☁ {trigger_var} (部屋{room_num}) への質問入力を検知しました！ ===")
        
        try:
            # Scratch側の room_id と現在処理中の部屋番号が一致しているか確認、または上書き
            # (Scratch側の部屋切り替え同期をより安全にするための保険)
            conn.set_var("room_id", room_num)
            time.sleep(0.1)

            # 1. Scratchからの暗号を英語に戻す
            user_question = numbers_to_text(activity.value) + "(You can only use alphabets, spaces, numbers and terminal punctuations)"
            print(f"=== [実況] 2. 部屋{room_num} 翻訳した質問: 「{user_question}」 ===")
            
            # 状態を「1 (処理中)」に更新
            conn.set_var(trigger_var, "1")
            
            url = f"https://text.pollinations.ai/{urllib.parse.quote(user_question)}"
            payload = {'model': 'openai'}
            
            print(f"=== [実況] 3. 確実に届くURLでAIに接続します... ===")
            response = requests.get(url, params=payload, timeout=60)
            print(f"=== [実況] 4. AIの応答コード: {response.status_code} ===")
            
            # 状態を「3 (送信中/データ準備完了)」に更新
            conn.set_var(trigger_var, "3")
            
            if response.status_code == 200:
                ai_reply = response.text.strip()
                print(f"=== [実況] 5. AIの生回答: 「{ai_reply}」 ===")
                
                if "<html" in ai_reply.lower() or "<doctype" in ai_reply.lower():
                    print(f"❌ [エラー] 部屋{room_num}: AIがエラー画面(HTML)を返しました。")
                    conn.set_var(trigger_var, "2")
                    return
                
                # アルファベット作戦で暗号化
                number_string = text_to_numbers(ai_reply)
                print(f"=== [実況] 6. 部屋{room_num} 返答全体の暗号化結果 (総数字数: {len(number_string)}文字) ===")
                
                # 【新ノード】文字分割送信システム
                chunk_size = 240
                total_length = len(number_string)
                
                print(f"=== [実況] 7. 部屋{room_num} 分割送信を開始します（サイズ: {chunk_size}文字ずつ） ===")
                
                for i in range(0, total_length, chunk_size):
                    chunk = number_string[i:i+chunk_size]
                    print(f"   -> ☁ {text_var} に送信中: {chunk[:20]}...")
                    
                    # 部屋番号に応じた変数にデータをセット
                    conn.set_var(text_var, chunk)
                    # Scratchが変数の変化を読み取るための重要なウェイト
                    time.sleep(0.5)
                
                # 【重要】すべての分割送信が終わった合図として "1" を送る
                print(f"=== [実況] 8. 部屋{room_num} すべてのデータを送り終えたため、終了合図 '1' を送信します ===")
                conn.set_var(text_var, "1")
                time.sleep(0.5)
                
                print(f"✨ [大成功] 部屋{room_num} のすべての分割データをScratchに送信完了しました！")
                
            else:
                print(f"❌ [エラー] 部屋{room_num}: サーバーエラー: {response.status_code}")
                conn.set_var(trigger_var, "2")
        except Exception as e:
            print(f"❌ [重大エラー] 部屋{room_num} 処理中にクラッシュしました: {e}")
            
        finally:
            # 最後にtriggerを0に戻して次の待機へ
            conn.set_var(trigger_var, "0")
            print(f"=== [実況] 9. {trigger_var} を0に戻し、次の待機状態に入りました ===")

print("Scratchからの質問入力を待っています...（4部屋マルチ・分割送信ノード実装版）")
# 前のターンで解説した「勝手に終わるバグ」を防ぐため thread=False を指定しています
events.start(thread=False)
