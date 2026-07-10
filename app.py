import threading
from flask import Flask
import scratchattach as sa

app = Flask(__name__)

# 1. Renderのスリープを防ぐためのダミーWebページ
@app.route('/')
def home():
    return "Bot is running!"

# 2. Scratchボットのメイン処理
def run_scratch_bot():
    try:
        # アカウントログインと接続
        session = sa.login("あなたのユーザー名", "あなたのパスワード")
        client = session.connect_linked_client(project_id="あなたのプロジェクトID")

        # Scratchから「AI」というリクエストが来たら返信する例
        @client.request(name="AI")
        def on_ai_request(argument):
            user_message = argument
            # ==========================================
            # ここにAI（OpenAI APIやGemini APIなど）の処理を書く
            ai_response = f"あなたが言ったこと: {user_message}" 
            # ==========================================
            return ai_response

        print("Scratch Bot Started!")
        client.start()
    except Exception as e:
        print(f"Error: {e}")

# Flaskとは別に、バックグラウンドでScratchボットを起動する
threading.Thread(target=run_scratch_bot, daemon=True).start()

if __name__ == "__main__":
    # ローカルテスト用
    app.run(host="0.0.0.0", port=5000)
