from telethon import TelegramClient, events, sync
import sys
import os

# Credentials from provided screenshot
api_id = 36993844
api_hash = '27443bac2a89e15ee1940302046a8d57'

client = TelegramClient('session_name', api_id, api_hash)

async def main():
    # Get target user from command line argument (required)
    if len(sys.argv) < 3:
        print("Usage: python main.py <file_path> <target_user>")
        return

    target_user = sys.argv[2]

    # Check for file path argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # Check if same file (name + size) already exists in chat
        async for message in client.iter_messages(target_user, limit=200):
            if message.file and message.file.name == file_name and message.file.size == file_size:
                print(f"SKIP: {file_name} ({file_size} bytes) already exists")
                return

        print(f"Uploading {file_name} to {target_user}...")
        try:
            def callback(current, total):
                print('Uploaded', current, 'out of', total,
                      'bytes: {:.2%}'.format(current / total))

            await client.send_file(target_user, file_path, progress_callback=callback)
            print("\nUpload complete!")
        except Exception as e:
            print(f"Error uploading file: {e}")
        return

    # Fetch messages from a specific user
    print(f"Fetching messages from {target_user}...")
    try:
        entity = await client.get_entity(target_user)
        async for message in client.iter_messages(entity, limit=20):
            content = message.text
            if not content and message.media:
                media_type = type(message.media).__name__
                content = f"[Media: {media_type}]"
                if hasattr(message, 'file') and message.file and message.file.name:
                    content += f" Filename: {message.file.name}"
            elif not content:
                content = "[Empty Message]"

            print(f"ID: {message.id} | Date: {message.date} | Content: {content}")
    except Exception as e:
        print(f"Error fetching messages: {e}")

with client:
    client.loop.run_until_complete(main())
