import os
import json
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient
from telethon.sessions import StringSession

app = Flask(__name__, static_folder='../static')

# Store sessions (in-memory - use Redis for production)
active_sessions = {}

async def send_code_async(api_id, api_hash, phone):
    session = StringSession('')
    client = TelegramClient(session, int(api_id), api_hash)
    
    try:
        await client.connect()
        result = await client.send_code_request(phone)
        
        session_id = str(len(active_sessions) + 1)
        active_sessions[session_id] = {
            'client': client,
            'session': session,
            'phone': phone,
            'phone_code_hash': result.phone_code_hash,
            'api_id': api_id,
            'api_hash': api_hash
        }
        
        return {
            'success': True,
            'data': {
                'session_id': session_id,
                'phone_code_hash': result.phone_code_hash
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def verify_code_async(session_id, code):
    session_data = active_sessions.get(session_id)
    if not session_data:
        return {'success': False, 'error': 'Session not found'}
    
    client = session_data['client']
    
    try:
        result = await client.sign_in(
            session_data['phone'],
            code,
            phone_code_hash=session_data['phone_code_hash']
        )
        
        if hasattr(result, '_') and result._ == 'auth.password':
            return {
                'success': True,
                'data': {
                    'needs_password': True,
                    'session_id': session_id
                }
            }
        
        session_string = session_data['session'].save()
        return {
            'success': True,
            'data': {
                'session_string': session_string,
                'needs_password': False
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def verify_2fa_async(session_id, password):
    session_data = active_sessions.get(session_id)
    if not session_data:
        return {'success': False, 'error': 'Session not found'}
    
    client = session_data['client']
    
    try:
        await client.sign_in(password=password)
        session_string = session_data['session'].save()
        return {
            'success': True,
            'data': {
                'session_string': session_string
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/')
def serve_index():
    return send_from_directory('../static', 'index.html')

@app.route('/api/send-code', methods=['POST'])
def send_code():
    try:
        data = request.json
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        phone = data.get('phone')
        
        if not all([api_id, api_hash, phone]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_code_async(api_id, api_hash, phone))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    try:
        data = request.json
        session_id = data.get('session_id')
        code = data.get('code')
        
        if not all([session_id, code]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(verify_code_async(session_id, code))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-2fa', methods=['POST'])
def verify_2fa():
    try:
        data = request.json
        session_id = data.get('session_id')
        password = data.get('password')
        
        if not all([session_id, password]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(verify_2fa_async(session_id, password))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Vercel handler
def handler(request, context):
    return app(request, context)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
