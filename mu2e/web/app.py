"""
Flask web application for mu2eDocChat
Provides both direct DocDB search and chat interfaces
"""

import os
import asyncio
import argparse
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from mu2e.chat_mcp import MCPClient,Chat
import json
from datetime import datetime
from mu2e.tools import getDefaultCollection, load2, getOpenAIClient, start_background_generate, get_last_generate_info
from mu2e.search import search, search_fulltext
from mu2e.utils import list_to_search_result
from mu2e import docdb, anl

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variables for services

active_chats = {}  # session_id -> Chat instance

'''
@app.route('/')
def index():
    """Main page with navigation to both interfaces"""
    return render_template('index.html')
'''

@app.route('/')
@app.route('/search')
def search_page():
    """Direct DocDB search interface"""
    return render_template('search.html')

@app.route('/chat')
def chat_page():
    """Chat interface with LLM"""
    return render_template('chat.html')

@app.route('/document')
def document_page():
    """Document lookup interface"""
    return render_template('document.html')

@app.route('/api/search', methods=['POST'])
def search_api():
    """Direct DocDB search API endpoint"""
    try:
        data = request.get_json()
        type = data.get('type', None)
        collection_name = data.get('collection', None)
        query = data.get('query', '')
        n_results = data.get('n_results', 5)
        filters = data.get('filters', None)
        #date_range = data.get('date_range', None)

        if type != 'list' and not query:
            return jsonify({'error': 'Query is required'}), 400

        if collection_name in ['argo']:
            collection = anl.get_collection(url="http://localhost:55019/v1/embed")
        else:
            collection = getDefaultCollection() 

        print(type)
        if type == 'search':
            results = search(query, 
                            collection=collection,
                            n_results=n_results, 
                            filters=filters)
        elif type == 'fulltext':
            results = search_fulltext(query, 
                                      collection=collection,
                                      n_results=n_results, 
                                      filters=filters)
        elif type == 'list':
            db = docdb()
            results = list_to_search_result(db.list_latest(days=n_results))

        else:
            return jsonify({'error': 'Invalid search type'}), 400
        
        print(results)
        return results
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/document/<string:docid>')
def get_document(docid):
    """Get specific document by ID"""
    try:
        print(docid);
        doc = load2(docid, nodb=True) #collection=)
        print(doc)
        return jsonify(doc)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/summary/<string:docid>', methods=['POST'])
def get_document_summary(docid):
    """Get summary of document by ID"""
    try:
        data = request.get_json()
        index = data.get('fileIndex', 0)
        instructions = data.get('instructions', 'You are a helpful assistant that summarizes documents in one paragraph. Do not include any other text than the summary.')
        doc = load2(docid, nodb=True) #collection=)
        content = doc['files'][index]['text']
        client = getOpenAIClient()
        response = client.chat.completions.create(
            model="argo:gpt-4o",
            messages=[{"role": "system", "content": instructions},
                      {"role": "user", "content": content}]
        )
        print(response)
        return jsonify(response.choices[0].message.content)
    
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/generate-info')
def get_generate_info():
    """Get last generate timestamp info"""
    try:
        info = get_last_generate_info('default')
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def trigger_generate():
    """Trigger manual generate"""
    try:
        def run_generate():
            db = docdb()
            db.generate(days=1)

            # temporary
            db_argo = docdb(collection=anl.get_collection(url="http://localhost:55019/v1/embed"))
            db_argo.generate(days=1)
        
        # Run in background thread
        import threading
        threading.Thread(target=run_generate, daemon=True).start()
        
        return jsonify({'status': 'started', 'message': 'Generate started in background'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('start_chat')
def handle_start_chat(data):
    """Handle WebSocket chat start request"""
    try:
        session_id = data.get('session_id')
        doc_id = data.get('doc_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        # Prepare user context
        user_context = {}
        if doc_id:
            # Load document to provide context
            doc = load2(doc_id, nodb=True)
            user_context = {
                'interface':"web",
                'document_id': doc_id,
                'document_title': doc.get('title', 'Unknown'),
                'document_content': doc.get('content', ''),  # Added the missing value
                'document_url': doc.get('link', ''),
                'document_files': [
                    {
                        'filename': file.get('filename', 'N/A'),
                        'content': file.get('text', 'N/A')
                    }
                    for idx, file in enumerate(doc.get('files', []))
                ],
                'document_date': doc.revised_content.get('date') if hasattr(doc, 'revised_content') and doc.revised_content else None,
                'document_context': f"User is asking about document: {doc.get('title', 'Unknown')} (ID: {doc_id}). The document contains {len(doc.get('files', []))} file(s)."
            }
            print(user_context)
        
        # Create new chat instance
        chat = Chat(user_context=user_context)
        active_chats[session_id] = chat
        
        emit('chat_started', {
            'success': True,
            'session_id': session_id,
            'document_context': user_context
        })
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('send_message')
def handle_send_message(data):
    """Handle WebSocket message sending"""
    try:
        session_id = data.get('session_id')
        message = data.get('message')
        
        if not session_id or not message:
            emit('error', {'message': 'Session ID and message are required'})
            return
        
        if session_id not in active_chats:
            emit('error', {'message': 'Chat session not found'})
            return
        
        chat = active_chats[session_id]
        
        # Run the async chat method in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(chat.chat(message))
            emit('message_response', {
                'response': response,
                'session_id': session_id
            })
        finally:
            loop.close()
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('end_chat')
def handle_end_chat(data):
    """Handle WebSocket chat end request"""
    try:
        session_id = data.get('session_id')
        
        if not session_id:
            emit('error', {'message': 'Session ID is required'})
            return
        
        if session_id in active_chats:
            chat = active_chats[session_id]
            
            # Cleanup chat session
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(chat.cleanup())
            except Exception as cleanup_error:
                print(f"Warning: Error during chat cleanup: {cleanup_error}")
            finally:
                loop.close()
            
            del active_chats[session_id]
        
        emit('chat_ended', {'success': True})
        
    except Exception as e:
        emit('error', {'message': str(e)})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print('Client disconnected')

def main():
    parser = argparse.ArgumentParser(description='Mu2e DocDB Web Interface')
    parser.add_argument('--port', type=int, default=5000,
                       help='Port to run the web server on (default: 5000)')
    
    args = parser.parse_args()
    
    # Start background generation
    start_background_generate(interval_minutes=5, days=1)
    #start_background_generate(interval_minutes=5, days=1, from_local=True,)
    
    print(f"Starting Mu2e DocDB Web Interface on http://127.0.0.1:{args.port}")
    socketio.run(app, debug=True, host='127.0.0.1', port=args.port)

if __name__ == '__main__':
    main()