from flask import Flask, request, render_template
import threading
import cloudscraper
import websocket
import json

app = Flask(__name__)

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
                        calories = content.split('!calories')[1].strip()
                        print(f'command received: {content}')
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
        return f'''Now listening for chat commands for channel: {slug}.\n
        Add the URL 'https://calorie-counter-production-ca38.up.railway.app/overlay' to web-overlays
         in IRL pro.\nSet width to 350 and height to 100.\nSend !calories <number> to add calories.'''
    return '''
        <form method="post">
            Enter your kick url username: <input name="slug">
            <input type="submit" value="Start Listening">
        </form>
    '''

@app.route('/overlay')
def overlay():
    return render_template('overlay.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080)


