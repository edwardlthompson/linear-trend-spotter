#!/usr/bin/env python3
import os
import requests
import json
import sys

bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
chat_id = os.getenv('TELEGRAM_CHAT_ID', '').strip()

if not bot_token:
    print('Missing TELEGRAM_BOT_TOKEN')
    sys.exit(1)
if not chat_id:
    print('Missing TELEGRAM_CHAT_ID')
    sys.exit(1)

base = f'https://api.telegram.org/bot{bot_token}'

print(f'Testing Telegram bot with chat_id={chat_id}')

me = requests.get(f'{base}/getMe', timeout=15)
print('\n[getMe]')
print(me.text)

chat = requests.get(f'{base}/getChat', params={'chat_id': chat_id}, timeout=15)
print('\n[getChat]')
print(chat.text)

msg = requests.post(
    f'{base}/sendMessage',
    data={'chat_id': chat_id, 'text': 'Render Telegram test message ✅'},
    timeout=15,
)
print('\n[sendMessage]')
print(msg.text)

try:
    parsed = msg.json()
    if parsed.get('ok'):
        print('\nTelegram test succeeded.')
        sys.exit(0)
except Exception:
    pass

print('\nTelegram test failed.')
sys.exit(1)
