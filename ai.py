import scratchattach as sa
import requests
import urllib.parse
import time
import os
import threading 
import signal
import sys

# ================= [設定エリア] =================
USERNAME = os.environ.get('SCRATCH_USERNAME')
PASSWORD = os.environ.get('SCRATCH_PASSWORD')
PROJECT_ID = 1352722752

# AIの応答を何秒待つか（タイムアウト秒数）
TIMEOUT_SECONDS = 180

# 🕒 【新設定：このプログラム自体の寿命】 🕒
# GitHub Actionsが4時間58分（17880秒）でループを止めるため、
# Python側は4時間55分（17700秒）で安全にリスナーを停止して終了させます。
LIFETIME_SECONDS = 17700  # 295分（4時間55分）
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

conn.set_var("trigger1", "9")
conn.set_var("trigger2", "9")
conn.set_var("trigger3", "9")
conn.set_var("trigger4", "9")

events = conn.events()

# タイムアウトを監視する関数
def timeout_monitor(room_num, my_count):
    time.sleep(TIMEOUT_SECONDS)
    if room_timer_counts.get(room_num) != my_count:
        return
    trigger_var = f"trigger{room_num}"
    try:
        if conn.get_var(trigger_var) != "0":
            print(f"⚠️ {TIMEOUT_SECONDS}秒経過したためタイムアウトします（triggerを9に変更）")
            conn.set_var(trigger_var, "9")
    except Exception as e:
        print(f"タイムアウト書き込み失敗: {e}")

# 各ルームの処理を完全に独立して実行する中身の関数
def process_room_request(room_num, activity_value):
    trigger_var = f"trigger{room_num}"
    text_var = f"text_from_python{room_num}"
    
    current_count = room_timer_counts.get(room_num, 0) + 1
    room_timer_counts[room_num] = current_count
    
    # ───【最新タイマー起動システム】──
    timer_thread = threading.Thread(target=timeout_monitor, args=(room_num, current_count))
    timer_thread.daemon = True
    timer_thread.start()
    
    print(f"\n🚀 [スレッド起動] 部屋{room_num} の処理をバックグラウンドで開始します。")
    
    try:
        user_question = numbers_to_text(activity_value) + "(You can only use alphabets, spaces, numbers and terminal punctuations)"
        print(f"=== [部屋{room_num}] 翻訳した質問: 「{user_question}」 ===")
        
        safe_set_var(trigger_var, "1")  # 👈 差し替え
        
        url = f"https://text.pollinations.ai/{urllib.parse.quote(user_question)}"
        payload = {'model': 'openai'}
        
        response = requests.get(url, params=payload, timeout=60)
        print(f"=== [部屋{room_num}] AIの応答コード: {response.status_code} ===")
        
        safe_set_var(trigger_var, "3")  # 👈 差し替え
        
        if response.status_code == 200:
            ai_reply = response.text.strip()
            print(f"=== [部屋{room_num}] AIの生回答: 「{ai_reply}」 ===")
            
            if "<html" in ai_reply.lower() or "<doctype" in ai_reply.lower():
                print(f"❌ [部屋{room_num} エラー] AIがエラー画面(HTML)を返しました。")
                safe_set_var(trigger_var, "9")  # 👈 差し替え
                return
            
            number_string = text_to_numbers(ai_reply)
            
            chunk_size = 240
            total_length = len(number_string)
            
            for i in range(0, total_length, chunk_size):
                chunk = number_string[i:i+chunk_size]
                safe_set_var(text_var, chunk)  # 👈 差し替え
                time.sleep(0.4)  # safe_set_var内のウェイト(0.15s)と合わせて約0.55秒空くため安全
            
            safe_set_var(text_var, "1")  # 👈 差し替え
            time.sleep(0.5)
            print(f"✨ [部屋{room_num} 大成功] すべてのデータを送信完了しました！")
            
        else:
            print(f"❌ [部屋{room_num} エラー] サーバーエラー: {response.status_code}")
            safe_set_var(trigger_var, "9")  # 👈 差し替え
    except Exception as e:
        print(f"❌ [部屋{room_num} 重大エラー] クラッシュしました: {e}")
        
    finally:
        if safe_get_var(trigger_var) != "9":  # 👈 差し替え
            safe_set_var(trigger_var, "0")    # 👈 差し替え
        print(f"🏁 [スレッド終了] 部屋{room_num} の処理が終わり、待機状態に戻りました。")


@events.event
def on_set(activity):
    if activity.var in ["trigger1", "trigger2", "trigger3", "trigger4"]:
        if len(activity.value) == 1:
            return
            
        room_num = activity.var.replace("trigger", "")
        
        t = threading.Thread(target=process_room_request, args=(room_num, activity.value))
        t.daemon = True
        t.start()

def emergency_shutdown(signum, frame):
    print(f"\n🛑 手動停止（シグナル {signum}）を検知しました！緊急シャットダウンを開始します。")
    reset_scratch_variables()
    sys.exit(0)

signal.signal(signal.SIGINT, emergency_shutdown)
signal.signal(signal.SIGTERM, emergency_shutdown)

def reset_scratch_variables():
    # 安全な関数（safe_set_var）を使うとロックがデッドロックを起こすリスクがあるため、
    # 緊急リセット時だけは直接connを叩く（ただしスリープを入れて安全性を高める）
    global conn
    try:
        if 'conn' in globals() and conn is not None:
            print("🔄 Scratchのトリガーをすべて99にリセットしています...")
            conn.set_var("trigger1", "99")
            time.sleep(0.2)
            conn.set_var("trigger2", "99")
            time.sleep(0.2)
            conn.set_var("trigger3", "99")
            time.sleep(0.2)
            conn.set_var("trigger4", "99")
            print("✅ リセット完了しました。")
    except Exception as e_final:
        print(f"⚠️ 変数リセットに失敗しました（通信切断のため無視します）: {e_final}")


# ==================== 【メインループ】 ====================
print("Scratchからの質問入力を待っています...（4部屋完全同時・マルチスレッド安全版）")
start_time = time.time()

try:
    while True:
        elapsed = time.time() - start_time
        if elapsed >= LIFETIME_SECONDS:
            print(f"⏰ 予定の稼働時間（{LIFETIME_SECONDS}秒）に達しました。安全に終了します。")
            break

        if events is None or not events.running:
            print("🔄 Scratchへの接続を開始（または再接続）します...")
            try:
                session = sa.login(USERNAME, PASSWORD)
                conn = session.connect_cloud(PROJECT_ID)
                events = conn.events()

                @events.event
                def on_set(activity):
                    if activity.var in ["trigger1", "trigger2", "trigger3", "trigger4"]:
                        if len(activity.value) == 1:
                            return
                        room_num = activity.var.replace("trigger", "")
                        t = threading.Thread(target=process_room_request, args=(room_num, activity.value))
                        t.daemon = True
                        t.start()

                try:
                    events.start(thread=True)
                    print("✅ 接続に成功しました。監視中です。")
                except Exception as e_start:
                    print(f"⚠️ 起動時に通信エラーが発生しました: {e_start}")
                    events = None
                    time.sleep(10)
                    continue
                    
            except Exception as e:
                print(f"❌ 接続失敗（Scratchサーバーの混雑など）: {e}。10秒後に再試行します。")
                events = None
                time.sleep(10)
                continue

        time.sleep(1)

except Exception as e_main:
    print(f"🚨 ループ内で予期せぬ重大なエラーが発生しました: {e_main}")

finally:
    print("👋 プログラムの終了処理を実行します...")
    reset_scratch_variables()

print("👋 すべての処理を正常終了しました。")

