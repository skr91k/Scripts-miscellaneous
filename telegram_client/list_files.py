
from telethon import TelegramClient, events, sync, utils
import sys
import os

# Credentials from main.py
api_id = 36993844
api_hash = '27443bac2a89e15ee1940302046a8d57'

# Reuse 'session_name' so we don't need to re-login
client = TelegramClient('session_name', api_id, api_hash)

async def main():
    target_channel = '@adhaaaaan'
    
    print(f"Connecting to Telegram...")
    await client.start()
    
    print(f"Fetching messages from {target_channel}...")
    try:
        entity = await client.get_entity(target_channel)
        
        # Iterate over messages
        # Adjust limit as needed, or remove limit=... to get all
        async for message in client.iter_messages(entity, limit=100):
            if message.file:
                # Get the file ID
                # Telethon abstracts file access, but we can print the file object or specific attributes
                # To get a persistent ID suitable for bot API, we might need utils, 
                # but for client API, the input_file or media object is key.
                # Here we will list ID, name, size and date.
                
                file_name = message.file.name if message.file.name else "Unknown"
                file_size = message.file.size
                date = message.date
                msg_id = message.id
                
                # Get Bot API File ID
                # This returns the file_id string used by bots
                bot_file_id = utils.pack_bot_file_id(message.media)
                
                print(f"---")
                print(f"Message ID: {msg_id}")
                print(f"Date: {date}")
                print(f"File Name: {file_name}")
                print(f"File Size: {file_size} bytes")
                print(f"Bot File ID: {bot_file_id}")

                # To get the full download link, you need a Bot Token.
                # 1. Get a token from @BotFather
                # 2. Replace 'YOUR_BOT_TOKEN' below
                # 3. The bot must have access to the file (e.g. be in the channel or the file forwarded to it)
                
                bot_token = 'YOUR_BOT_TOKEN' 
                
                if bot_token != 'YOUR_BOT_TOKEN':
                    # If we had a token, we could do this:
                    import requests
                    try:
                        r = requests.get(f"https://api.telegram.org/bot{bot_token}/getFile?file_id={bot_file_id}")
                        if r.status_code == 200:
                            file_path = r.json()['result']['file_path']
                            download_link = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
                            print(f"Download Link: {download_link}")
                        else:
                            print(f"Could not fetch path (Bot may not have access): {r.text}")
                    except ImportError:
                        print("requests module not found, cannot fetch path.")
                else:
                    print(f"Link Template: https://api.telegram.org/bot<TOKEN>/getFile?file_id={bot_file_id}")
                
    except Exception as e:
        print(f"Error: {e}")

with client:
    client.loop.run_until_complete(main())
