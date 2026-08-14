"""
Telegram Session Generator - Vercel Serverless API
"""

import os
import json
import asyncio
from flask import Flask, request, jsonify, send_from_directory
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import PhoneCodeInvalidError, PasswordHashInvalidError

# ============================================
# Flask App
# ============================================

app = Flask(__name__, static_folder='../static', static_url_path='')

# Store active sessions (in-memory - for demo only, use Redis in production)
active_sessions = {}

# ============================================
# Telegram Handlers (Async)
# ============================================

async def send_code_async(api_id, api_hash, phone):
    """Send verification code"""
    session = StringSession('')
    client = TelegramClient(session, int(api_id), api_hash)
    
    try:
        await client.connect()
        result = await client.send_code_request(phone)
        
        # Store session for later
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
        return {
            'success': False,
            'error': str(e)
        }

async def verify_code_async(session_id, code):
    """Verify the OTP code"""
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
        
        # Check if 2FA is required
        if hasattr(result, '_') and result._ == 'auth.password':
            return {
                'success': True,
                'data': {
                    'needs_password': True,
                    'session_id': session_id
                }
            }
        
        # Login successful
        session_string = session_data['session'].save()
        return {
            'success': True,
            'data': {
                'session_string': session_string,
                'needs_password': False
            }
        }
    except PhoneCodeInvalidError:
        return {'success': False, 'error': 'Invalid verification code'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def verify_2fa_async(session_id, password):
    """Verify 2FA password"""
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
    except PasswordHashInvalidError:
        return {'success': False, 'error': 'Invalid 2FA password'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================
# Flask Routes
# ============================================

@app.route('/')
def serve_index():
    """Serve the HTML page"""
    return send_from_directory('../static', 'index.html')

@app.route('/api/send-code', methods=['POST'])
def send_code():
    """Send verification code"""
    try:
        data = request.json
        api_id = data.get('api_id')
        api_hash = data.get('api_hash')
        phone = data.get('phone')
        
        if not all([api_id, api_hash, phone]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(send_code_async(api_id, api_hash, phone))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-code', methods=['POST'])
def verify_code():
    """Verify the OTP code"""
    try:
        data = request.json
        session_id = data.get('session_id')
        code = data.get('code')
        
        if not all([session_id, code]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(verify_code_async(session_id, code))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify-2fa', methods=['POST'])
def verify_2fa():
    """Verify 2FA password"""
    try:
        data = request.json
        session_id = data.get('session_id')
        password = data.get('password')
        
        if not all([session_id, password]):
            return jsonify({'success': False, 'error': 'Missing required fields'})
        
        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(verify_2fa_async(session_id, password))
        loop.close()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# Vercel Handler
# ============================================

# For Vercel serverless deployment
def handler(event, context):
    return app(event, context)

# ============================================
# Local Development
# ============================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
