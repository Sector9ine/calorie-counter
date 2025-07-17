from flask import Flask, request, render_template, jsonify
import threading
import cloudscraper
import websocket
import json
import os
import redis

app = Flask(__name__)

redis_url = os.environ.get("REDIS_URL")
rdb = redis.from_url(redis_url)

def get_chatroom_id(slug):
    endpoint = f"https://kick.com/api/v2/channels/{slug}"
    scraper = cloudscraper.create_scraper()
    r = scraper.get(endpoint)
    data = r.json()
    chatroom_id = data.get("chatroom_id")
    if not chatroom_id and "chatroom" in data:
        chatroom_id = data["chatroom"].get("id")
    return chatroom_id

def listen_to_kick_chat(chatroom_id):
    def on_message(ws, message):
        try:
            data = json.loads(message)
            if data.get("event") == "App\\Events\\ChatMessageEvent":
                msg = json.loads(data["data"])
                content = msg.get("content")
                badges = msg.get("sender", {}).get("identity", {}).get("badges", [])
                badge_types = [badge.get("type") for badge in badges]
                if 'broadcaster' in badge_types or 'moderator' in badge_types:
                    if content.startswith('!calories'):
                        if content == '!calories delete':
                            rdb.set("calories", 0)
                            print(f'command received: {content} (new total: {0})')
                            return
                        calories = content.split('!calories')[1].strip()
                        try:
                            add_value = int(calories)
                        except ValueError:
                            print(f"Invalid calorie value: {calories}")
                            return
                        # Get current value, add, and store
                        current = rdb.get("calories")
                        current_value = int(current) if current else 0
                        new_total = current_value + add_value
                        rdb.set("calories", new_total)
                        print(f'command received: {content} (new total: {new_total})')
        except Exception as e:
            print("Error:", e)

    def on_open(ws):
        ws.send(json.dumps({
            "event": "pusher:subscribe",
            "data": {
                "auth": "",
                "channel": f"chatrooms.{chatroom_id}.v2"
            }
        }))

    ws = websocket.WebSocketApp(
        "wss://ws-us2.pusher.com/app/32cbd69e4b950bf97679?protocol=7&client=js&version=8.4.0-rc2&flash=false",
        on_open=on_open,
        on_message=on_message
    )
    ws.run_forever()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        slug = request.form['slug']
        chatroom_id = get_chatroom_id(slug)
        # Start the chat listener in a background thread
        threading.Thread(target=listen_to_kick_chat, args=(chatroom_id,), daemon=True).start()
        return f"""
<html>
<head>
    <title>Kick Calorie Counter Ready</title>
    <style>
        body {{
            background: #18122B;
            color: #fff;
            font-family: 'Segoe UI', Arial, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
        }}
        .success-container {{
            background: #393053;
            padding: 32px 40px;
            border-radius: 18px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.3);
            text-align: center;
        }}
        .success-container h2 {{
            color: #7F27FF;
            margin-bottom: 18px;
        }}
        .instructions {{
            margin-top: 18px;
            font-size: 1.1em;
            line-height: 1.7;
        }}
        .url {{
            background: #7F27FF;
            color: #fff;
            padding: 4px 10px;
            border-radius: 6px;
            font-family: monospace;
            display: inline-block;
            margin: 8px 0;
        }}
    </style>
</head>
<body>
    <div class="success-container">
        <h2>✅ Success!</h2>
        <div class="instructions">
            Now listening for chat commands for channel: <b>{slug}</b>.<br><br>
            Add the URL<br>
            <span class="url">https://calorie-counter-production-ca38.up.railway.app/overlay</span><br>
            to web-overlays in IRL pro.<br><br>
            Set width to <b>350</b> and height to <b>100</b>.<br><br>
            Send <span class="url">!calories &lt;number&gt;</span> to add calories.<br>
            Send <span class="url">!calories delete</span> to reset.
        </div>
    </div>
</body>
</html>
"""
    return '''
    <html>
    <head>
        <title>Kick Calorie Counter Setup</title>
        <style>
            body {
                background: #18122B;
                color: #fff;
                font-family: 'Segoe UI', Arial, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            .form-container {
                background: #393053;
                padding: 32px 40px;
                border-radius: 18px;
                box-shadow: 0 4px 24px rgba(0,0,0,0.3);
                text-align: center;
            }
            input[type="text"] {
                padding: 10px 16px;
                border-radius: 8px;
                border: none;
                font-size: 1.1em;
                margin-bottom: 16px;
                width: 220px;
            }
            input[type="submit"] {
                background: #7F27FF;
                color: #fff;
                border: none;
                border-radius: 8px;
                padding: 10px 24px;
                font-size: 1.1em;
                cursor: pointer;
                transition: background 0.2s;
            }
            input[type="submit"]:hover {
                background: #9F70FD;
            }
            h2 {
                margin-bottom: 18px;
            }
        </style>
    </head>
    <body>
        <div class="form-container">
            <h2>Kick Calorie Counter Setup</h2>
            <form method="post">
                <input type="text" name="slug" placeholder="Enter your Kick channel username" required><br>
                <input type="submit" value="Start Listening">
            </form>
        </div>
    </body>
    </html>
'''

@app.route('/overlay')
def overlay():
    return render_template('overlay.html')

@app.route('/calories')
def get_calories():
    value = rdb.get("calories")
    calories = int(value) if value else 0
    return jsonify({'calories': calories})

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)


