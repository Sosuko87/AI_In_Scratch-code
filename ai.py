import scratchattach as sa
import requests
import urllib.parse
import time
import os

# ================= [設定エリア] =================
USERNAME = "ZZZBanana"
PASSWORD = "Walworth2013"
PROJECT_ID = 1352722752
# ===============================================

# 変換ロジックは前回同様
def numbers_to_text(number_string):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.?!,'"
    text = ""
    if len(number_string) % 2 != 0: number_string += "0"
    for i in range(0, len(number_string), 2):
        code_str = number_string[i:i+2]
        try:
            code = int(code_str)
            if code == 78: text += " "
            else:
                index = code - 9 - 1 
                if 0 <= index < len(alphabet): text += alphabet[index]
        except: pass
    return text

def text_to_numbers(text):
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.?!,'"
    encoded = ""
    for char in text:
        if char == " ": encoded += "78"
        elif char in alphabet: encoded += str(alphabet.index(char) + 1 + 9)
        else: encoded += "76"
    return encoded

session = sa.login(USERNAME, PASSWORD)
conn = session.connect_cloud(PROJECT_ID)
print(f"ログイン成功: {session.username}")

events = conn.events()

@events.event
def on_set(activity):
    if activity.var == "trigger":
        val = str(activity.value).strip()
        
        # === 【最重要】バグを強制ストップする超厳格ブレーキ ===
        # 1. 変更したのが自分（Bot）なら処理しない
        # 2. 空、1桁以下、状態管理用（0,1,2,3,00）、奇数長さなら処理しない
        if activity.user == USERNAME or not val or len(val) <= 1 or val in ["0", "1", "2", "3", "00"] or len(val) % 2 != 0:
            return
        # ===================================================
        
        print(f"\n✅ 有効な質問を検知: {val[:10]}...")
        try:
            user_question = numbers_to_text(val) + "(don't use symbols or line breaking.)"
            conn.set_var("trigger", "1")
            
            url = f"https://pollinations.ai/{urllib.parse.quote(user_question)}"
            response = requests.get(url, params={'model': 'openai'}, timeout=60)
            conn.set_var("trigger", "3")
            
            if response.status_code == 200:
                ai_reply = response.text.strip()
                number_string = text_to_numbers(ai_reply)
                
                # 分割送信
                for i in range(0, len(number_string), 240):
                    conn.set_var("text_from_python", number_string[i:i+240])
                    time.sleep(2)
                conn.set_var("text_from_python", "00")
            else:
                conn.set_var("trigger", "2")
                
        except Exception as e: print(f"❌ エラー: {e}")
        finally: conn.set_var("trigger", "0")

print("待機中...")
events.start(blocking=True)
