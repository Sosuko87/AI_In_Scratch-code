import scratchattach as sa
import requests
import urllib.parse
import time
import os
import threading  # 【新機能】同時に別々の処理を走らせるためのライブラリ

# ================= [設定エリア] =================
USERNAME = os.environ.get('SCRATCH_USERNAME')
PASSWORD = os.environ.get('SCRATCH_PASSWORD')
PROJECT_ID = 1352722752

# 🕒 【ここでタイマーの時間を設定できます】 🕒
# AIの応答を何秒待つか（タイムアウト秒数）を設定してください。デフォルトは3分（180秒）です。
TIMEOUT_SECONDS = 180
# ===============================================

# ルームごとの最新タイマーIDを管理する辞書
room_timer_counts = {}

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

# タイムアウトを監視する関数
def timeout_monitor(room_num, my_count):
    # 設定エリアで指定した秒数だけ待機します
    time.sleep(TIMEOUT_SECONDS)
    
    # もし待っている間に新しい質問が来てタイマーが更新されていたら、この古いタイマーは無視して終了
    if room_timer_counts.get(room_num) != my_count:
        return
        
    trigger_var = f"trigger{room_num}"
    try:
        # まだ処理中（0に戻っていない）なら、180秒経ったのでタイムアウト（9に変える）
        if conn.get_var(trigger_var) != "0":
            print(f"⚠️ {TIMEOUT_SECONDS}秒経過したためタイムアウトします（triggerを9に変更）")
            conn.set_var(trigger_var, "9")
    except Exception as e:
        print(f"タイムアウト書き込み失敗: {e}")

# 【新機能】各ルームの処理を完全に独立して実行する中身の関数
def process_room_request(room_num, activity_value):
    trigger_var = f"trigger{room_num}"
    text_var = f"text_from_python{room_num}"
    
    # ───【最新タイマー起動システム】──
    # この部屋のタイマーIDを1つ進める
    current_count = room_timer_counts.get(room_num, 0) + 1
    room_timer_counts[room_num] = current_count
    
    # 設定された秒数後に自動で動くタイマースレッドを裏で起動
    timer_thread = threading.Thread(target=timeout_monitor, args=(room_num, current_count))
    timer_thread.daemon = True
    timer_thread.start()
    
    print(f"\n🚀 [スレッド起動] 部屋{room_num} の処理をバックグラウンドで開始します。")
    
    try:
        # 1. Scratchからの暗号を英語に戻す
        user_question = numbers_to_text(activity_value) + "(You can only use alphabets, spaces, numbers and terminal punctuations)"
        print(f"=== [部屋{room_num}] 翻訳した質問: 「{user_question}」 ===")
        
        conn.set_var(trigger_var, "1")
        
        url = f"https://text.pollinations.ai/{urllib.parse.quote(user_question)}"
        payload = {'model': 'openai'}
        
        response = requests.get(url, params=payload, timeout=60)
        print(f"=== [部屋{room_num}] AIの応答コード: {response.status_code} ===")
        
        conn.set_var(trigger_var, "3")
        
        if response.status_code == 200:
            ai_reply = response.text.strip()
            print(f"=== [部屋{room_num}] AIの生回答: 「{ai_reply}」 ===")
            
            if "<html" in ai_reply.lower() or "<doctype" in ai_reply.lower():
                print(f"❌ [部屋{room_num} エラー] AIがエラー画面(HTML)を返しました。")
                conn.set_var(trigger_var, "2")
                return
            
            number_string = text_to_numbers(ai_reply)
            
            chunk_size = 240
            total_length = len(number_string)
            
            for i in range(0, total_length, chunk_size):
                chunk = number_string[i:i+chunk_size]
                conn.set_var(text_var, chunk)
                time.sleep(0.5)
            
            conn.set_var(text_var, "1")
            time.sleep(0.5)
            print(f"✨ [部屋{room_num} 大成功] すべてのデータを送信完了しました！")
            
        else:
            print(f"❌ [部屋{room_num} エラー] サーバーエラー: {response.status_code}")
            conn.set_var(trigger_var, "2")
    except Exception as e:
        print(f"❌ [部屋{room_num} 重大エラー] クラッシュしました: {e}")
        
    finally:
        # もしタイマーが先に発動して「9」に書き換えていたら、0に戻さずにそのまま維持します
        if conn.get_var(trigger_var) != "9":
            conn.set_var(trigger_var, "0")
        print(f"🏁 [スレッド終了] 部屋{room_num} の処理が終わり、待機状態に戻りました。")


@events.event
def on_set(activity):
    if activity.var in ["trigger1", "trigger2", "trigger3", "trigger4"]:
        if len(activity.value) == 1:
            return
            
        room_num = activity.var.replace("trigger", "")
        
        # 【重要】イベントを検知したら、実際の処理は別スレッド（Thread）に丸投げする！
        # これにより、この関数自体は一瞬で終了し、次のルームの検知にすぐ戻れます。
        t = threading.Thread(target=process_room_request, args=(room_num, activity.value))
        t.daemon = True  # プログラム終了時に一緒に終了するように設定
        t.start()        # ルーム個別の並行処理をスタート！

print("Scratchからの質問入力を待っています...（4部屋完全同時・マルチスレッド版）")
events.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("プログラムを終了します。")
