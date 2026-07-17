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

# 🕒 【このプログラム自体の寿命】 🕒
LIFETIME_SECONDS = 17700  # 295分（4時間55分）
# ===============================================

# グローバル変数の初期化
conn = None
events = None
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

# タイムアウトを監視する関数
def timeout_monitor(room_num, my_count):
    time.sleep(TIMEOUT_SECONDS)
    if room_timer_counts.get(room_num) != my_count:
        return
    trigger_var = f"trigger{room_num}"
    try:
        if conn and conn.get_var(trigger_var) != "0":
            print(f"⚠️ {TIMEOUT_SECONDS}秒経過したためタイムアウトします（triggerを9に変更）")
            conn.set_var(trigger_var, "9")
    except Exception as e:
        print(f"タイムアウト書き込み失敗: {e}")

# 各ルームの処理を完全に独立して実行する関数
def process_room_request(room_num, activity_value):
    trigger_var = f"trigger{room_num}"
    text_var = f"text_from_python{room_num}"
    
    current_count = room_timer_counts.get(room_num, 0) + 1
    room_timer_counts[room_num] = current_count
    
    timer_thread = threading.Thread(target=timeout_monitor, args=(room_num, current_count))
    timer_thread.daemon = True
    timer_thread.start()
    
    print(f"\n🚀 [スレッド起動] 部屋{room_num} の処理をバックグラウンドで開始します。")
    
    has_error = False
    
    try:
        user_question = numbers_to_text(activity_value) + " (You can only use alphabets, spaces, numbers and terminal punctuations)"
        print(f"=== [部屋{room_num}] 翻訳した質問: 「{user_question}」 ===")
        
        conn.set_var(trigger_var, "1")
        
        url = f"https://pollinations.ai{urllib.parse.quote(user_question)}"
        payload = {'model': 'openai'}
        
        response = requests.get(url, params=payload, timeout=60)
        print(f"=== [部屋{room_num}] AIの応答コード: {response.status_code} ===")
        
        conn.set_var(trigger_var, "3")
        
        if response.status_code == 200:
            ai_reply = response.text.strip()
            print(f"=== [部屋{room_num}] AIの生回答: 「{ai_reply}」 ===")
            
            if "<html" in ai_reply.lower() or "<doctype" in ai_reply.lower():
                print(f"❌ [部屋{room_num} エラー] AIがエラー画面(HTML)を返しました。")
                has_error = True
                conn.set_var(trigger_var, "9")
                return
            
            number_string = text_to_numbers(ai_reply)
            
            chunk_size = 200 
            total_length = len(number_string)
            
            for i in range(0, total_length, chunk_size):
                chunk = number_string[i:i+chunk_size]
                conn.set_var(text_var, chunk)
                time.sleep(0.7)
            
            conn.set_var(text_var, "1")
            time.sleep(0.7)
            print(f"✨ [部屋{room_num} 大成功] すべてのデータを送信完了しました！")
            
        else:
            print(f"❌ [部屋{room_num} エラー] サーバーエラー: {response.status_code}")
            has_error = True
            conn.set_var(trigger_var, "9")
    except Exception as e:
        print(f"❌ [部屋{room_num} 重大エラー] クラッシュしました: {e}")
        has_error = True
        try:
            conn.set_var(trigger_var, "9")
        except:
            pass
        
    finally:
        try:
            if not has_error:
                conn.set_var(trigger_var, "0")
            print(f"🏁 [スレッド終了] 部屋{room_num} の処理が終わり、待機状態に戻りました。")
        except Exception as ef:
            print(f"⚠️ [部屋{room_num} 終了処理エラー] 変数リセットに失敗: {ef}")


# ==================== 【共通のリセット関数】 ====================
def reset_scratch_variables():
    """Scratchのトリガー変数をすべて強制的に99にリセットする関数"""
    global conn
    print("🔄 Scratchのトリガーをすべて99にリセットしています...")
    
    # メイン接続（conn）が切れている、または未接続の可能性に備え、ここで新たにログインして確実に書き込む
    try:
        emergency_session = sa.login(USERNAME, PASSWORD)
        emergency_conn = emergency_session.connect_cloud(PROJECT_ID)
        emergency_conn.set_var("trigger1", "99")
        emergency_conn.set_var("trigger2", "99")
        emergency_conn.set_var("trigger3", "99")
        emergency_conn.set_var("trigger4", "99")
        print("✅ トリガー変数をすべて99にリセットしました。")
    except Exception as e_final:
        print(f"⚠️ 終了時の変数リセットに失敗しました（Scratchサーバー混雑など）: {e_final}")


# ==================== 【手動停止をキャッチする設定】 ====================
def emergency_shutdown(signum, frame):
    print(f"\n🛑 手動停止（シグナル {signum}）を検知しました！緊急リセットを開始します。")
    reset_scratch_variables()
    sys.exit(0)

signal.signal(signal.SIGINT, emergency_shutdown)   # Ctrl+C 用
signal.signal(signal.SIGTERM, emergency_shutdown)  # GitHubの「Cancel run」用


# ==================== 【メインループと接続処理】 ====================
def handle_on_set(activity):
    if activity.var in ["trigger1", "trigger2", "trigger3", "trigger4"]:
        if len(activity.value) == 1:
            return
            
        room_num = activity.var.replace("trigger", "")
        t = threading.Thread(target=process_room_request, args=(room_num, activity.value))
        t.daemon = True
        t.start()

print("Scratchからの質問入力を待っています...（4部屋完全同時・マルチスレッド版）")
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
                
                # 起動・再接続時は、部屋を稼働状態にするため一時的に「9」にする
                conn.set_var("trigger1", "9")
                conn.set_var("trigger2", "9")
                conn.set_var("trigger3", "9")
                conn.set_var("trigger4", "9")
                
                events = conn.events()
                events.event(handle_on_set, name="on_set")

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
    # 予期せぬ重大なエラーでメインループがクラッシュした場合もここを通る
    print(f"🚨 ループ内で予期せぬ重大なエラーが発生しました: {e_main}")

finally:
    # 正常終了（寿命）およびクラッシュ終了のどちらでも、最後に必ずここが実行される
    print("👋 プログラムの終了処理を実行します...")
    reset_scratch_variables()

print("👋 すべての処理を正常終了しました。")
