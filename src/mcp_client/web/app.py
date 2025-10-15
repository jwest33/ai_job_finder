"""
Flask Web Application for MCP Client

Provides web-based interface for interacting with the MCP client.
"""

import os
import sys
import json
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from mcp_client.client import MCPClient
from mcp_client.context_manager import DynamicContextManager
from mcp_client.conversation_store import EnhancedConversationStore

load_dotenv()

logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    CORS(app)  # Enable CORS for local development

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Parse LLAMA_SERVER_URL - if multiple URLs (comma-separated), use the first one
    llama_url = os.getenv('LLAMA_SERVER_URL', 'http://localhost:8080')
    if ',' in llama_url:
        llama_url = llama_url.split(',')[0].strip()
    app.config['LLAMA_URL'] = llama_url

    app.config['MCP_URL'] = os.getenv('MCP_SERVER_URL', 'http://localhost:3000')
    app.config['MCP_TOKEN'] = os.getenv('MCP_AUTH_TOKEN')

    # Initialize components
    mcp_client = MCPClient(
        llama_url=app.config['LLAMA_URL'],
        mcp_url=app.config['MCP_URL'],
        mcp_token=app.config['MCP_TOKEN'],
    )

    context_manager = DynamicContextManager()
    conversation_store = EnhancedConversationStore()

    # Store in app context
    app.mcp_client = mcp_client
    app.context_manager = context_manager
    app.conversation_store = conversation_store
    app.current_conversation_id = None

    @app.route('/')
    def index():
        """Main chat interface"""
        return render_template('chat.html')

    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Check health of all services"""
        try:
            health = mcp_client.health_check()
            return jsonify({
                'success': True,
                'data': health
            })
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/tools', methods=['GET'])
    def list_tools():
        """List all available MCP tools"""
        try:
            tools = mcp_client.list_tools()

            # Group by category
            by_category = {}
            for tool in tools:
                category = tool.split(".")[0]
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(tool)

            return jsonify({
                'success': True,
                'data': {
                    'tools': tools,
                    'by_category': by_category,
                    'count': len(tools)
                }
            })
        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversations', methods=['GET'])
    def list_conversations():
        """List all conversations"""
        try:
            limit = request.args.get('limit', type=int)
            profile = request.args.get('profile')

            conversations = conversation_store.list_conversations(
                limit=limit,
                profile=profile
            )

            return jsonify({
                'success': True,
                'data': {
                    'conversations': [
                        {
                            'id': conv.id,
                            'title': conv.title,
                            'created_at': conv.created_at,
                            'updated_at': conv.updated_at,
                            'message_count': conv.message_count,
                            'total_tokens': conv.total_tokens,
                            'archived_count': conv.archived_count,
                            'profile': conv.profile,
                        }
                        for conv in conversations
                    ],
                    'count': len(conversations)
                }
            })
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversation/new', methods=['POST'])
    def new_conversation():
        """Create new conversation"""
        try:
            data = request.json or {}
            title = data.get('title')
            profile = data.get('profile')

            conv_id = conversation_store.create_conversation(
                title=title,
                profile=profile
            )

            app.current_conversation_id = conv_id

            # Clear client conversation history
            mcp_client.clear_conversation()

            return jsonify({
                'success': True,
                'data': {
                    'conversation_id': conv_id
                }
            })
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversation/<conv_id>', methods=['GET'])
    def load_conversation(conv_id):
        """Load conversation"""
        try:
            conversation = conversation_store.load_conversation(conv_id)

            if conversation is None:
                return jsonify({
                    'success': False,
                    'error': 'Conversation not found'
                }), 404

            app.current_conversation_id = conv_id

            # Restore messages to client
            mcp_client.messages = conversation.get('messages', [])

            return jsonify({
                'success': True,
                'data': conversation
            })
        except Exception as e:
            logger.error(f"Failed to load conversation: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversation/<conv_id>', methods=['DELETE'])
    def delete_conversation(conv_id):
        """Delete conversation"""
        try:
            conversation_store.delete_conversation(conv_id)

            if app.current_conversation_id == conv_id:
                app.current_conversation_id = None
                mcp_client.clear_conversation()

            return jsonify({
                'success': True,
                'data': {'deleted': conv_id}
            })
        except Exception as e:
            logger.error(f"Failed to delete conversation: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/chat', methods=['POST'])
    def chat():
        """Send chat message"""
        try:
            data = request.json
            user_message = data.get('message')

            if not user_message:
                return jsonify({
                    'success': False,
                    'error': 'No message provided'
                }), 400

            # Ensure we have a conversation
            if app.current_conversation_id is None:
                app.current_conversation_id = conversation_store.create_conversation()

            conv_id = app.current_conversation_id

            # Add user message to store
            conversation_store.add_message(
                conv_id,
                role='user',
                content=user_message
            )

            # Get current messages
            all_messages = conversation_store.get_messages(conv_id)

            # Get excluded message indices
            excluded_indices = conversation_store.get_excluded_messages(conv_id)

            # Estimate tokens for current query
            query_tokens = len(user_message) // 4

            # Optimize context with excluded messages
            optimized_messages, pointers, stats = context_manager.optimize_context(
                messages=all_messages[:-1],  # Exclude current message
                current_query=user_message,
                current_query_tokens=query_tokens,
                excluded_indices=excluded_indices
            )

            # Update client with optimized messages
            mcp_client.messages = optimized_messages

            # Track starting message count to identify new messages during this request
            message_count_before = len(mcp_client.messages)

            # Get response from LLM
            response = mcp_client.chat(user_message, verbose=False)

            # Extract tool calls that occurred during this request
            # Tool messages are everything between the start and the final assistant response
            tool_calls = []
            new_messages = mcp_client.messages[message_count_before:-1]  # Exclude final assistant response

            for msg in new_messages:
                if msg.get("role") == "tool":
                    tool_calls.append({
                        "tool_name": msg.get("name", "unknown"),
                        "content": msg.get("content", ""),
                        "role": "tool"
                    })

            # Add tool calls to conversation store BEFORE assistant response
            for tool_call in tool_calls:
                conversation_store.add_message(
                    conv_id,
                    role='tool',
                    content=tool_call['content'],
                    name=tool_call['tool_name']
                )

            # Add assistant response to store
            conversation_store.add_message(
                conv_id,
                role='assistant',
                content=response
            )

            # Update context in store
            updated_messages = conversation_store.get_messages(conv_id)
            conversation_store.update_context(
                conv_id,
                messages=updated_messages,
                pointers=pointers,
                stats=stats
            )

            # Get context stats
            context_stats = context_manager.get_context_stats(
                messages=updated_messages,
                pointers=pointers
            )

            return jsonify({
                'success': True,
                'data': {
                    'response': response,
                    'tool_calls': tool_calls,
                    'conversation_id': conv_id,
                    'context_stats': context_stats,
                    'pointers': pointers
                }
            })
        except Exception as e:
            logger.error(f"Chat failed: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversation/<conv_id>/message/<int:message_index>/exclude', methods=['POST'])
    def exclude_message(conv_id, message_index):
        """Exclude message from context"""
        try:
            conversation_store.exclude_message_from_context(conv_id, message_index)

            return jsonify({
                'success': True,
                'data': {
                    'conversation_id': conv_id,
                    'message_index': message_index,
                    'excluded': True
                }
            })
        except Exception as e:
            logger.error(f"Failed to exclude message: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversation/<conv_id>/message/<int:message_index>/restore', methods=['POST'])
    def restore_message(conv_id, message_index):
        """Restore message to context"""
        try:
            conversation_store.restore_message_to_context(conv_id, message_index)

            return jsonify({
                'success': True,
                'data': {
                    'conversation_id': conv_id,
                    'message_index': message_index,
                    'excluded': False
                }
            })
        except Exception as e:
            logger.error(f"Failed to restore message: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/conversation/<conv_id>/title', methods=['PATCH'])
    def update_conversation_title(conv_id):
        """Update conversation title"""
        try:
            data = request.json
            new_title = data.get('title')

            if not new_title:
                return jsonify({
                    'success': False,
                    'error': 'No title provided'
                }), 400

            conversation_store.update_title(conv_id, new_title)

            return jsonify({
                'success': True,
                'data': {
                    'conversation_id': conv_id,
                    'title': new_title
                }
            })
        except Exception as e:
            logger.error(f"Failed to update conversation title: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/tools/<tool_name>/template', methods=['GET'])
    def get_tool_template(tool_name):
        """Get tool call template for pre-population"""
        try:
            # Get tool schema from MCP client
            tools = mcp_client.list_tools()

            if tool_name not in tools:
                return jsonify({
                    'success': False,
                    'error': f'Tool not found: {tool_name}'
                }), 404

            # Generate template with placeholder parameters
            # Format: tool_name(param1=value1, param2=value2)
            template = f"{tool_name}("

            # TODO: If we have tool schemas available, parse parameters
            # For now, just return basic template
            template += ")"

            return jsonify({
                'success': True,
                'data': {
                    'tool_name': tool_name,
                    'template': template
                }
            })
        except Exception as e:
            logger.error(f"Failed to get tool template: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/context/stats', methods=['GET'])
    def context_stats():
        """Get current context statistics"""
        try:
            if app.current_conversation_id is None:
                return jsonify({
                    'success': True,
                    'data': {
                        'total_tokens': 0,
                        'message_count': 0,
                        'health': 'healthy',
                        'context_filtering_enabled': mcp_client.enable_context_filtering,
                    }
                })

            # Get all messages and excluded indices
            messages = conversation_store.get_messages(app.current_conversation_id)
            excluded_indices = conversation_store.get_excluded_messages(app.current_conversation_id)

            # Filter out excluded messages for accurate stats
            excluded_set = set(excluded_indices)
            active_messages = [
                msg for i, msg in enumerate(messages)
                if i not in excluded_set
            ]

            # Get pointers (archived messages)
            pointers = conversation_store.get_pointers(app.current_conversation_id)

            # Calculate stats on active messages only
            stats = context_manager.get_context_stats(active_messages, pointers)

            # Add context filtering info
            stats['context_filtering_enabled'] = mcp_client.enable_context_filtering

            return jsonify({
                'success': True,
                'data': stats
            })
        except Exception as e:
            logger.error(f"Failed to get context stats: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/context/filtering', methods=['POST'])
    def toggle_context_filtering():
        """Enable/disable context filtering"""
        try:
            data = request.json
            enabled = data.get('enabled', True)

            mcp_client.set_context_filtering(enabled)

            return jsonify({
                'success': True,
                'data': {
                    'context_filtering_enabled': enabled,
                    'message': f"Context filtering {'enabled' if enabled else 'disabled'}"
                }
            })
        except Exception as e:
            logger.error(f"Failed to toggle context filtering: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/context/filtering', methods=['GET'])
    def get_context_filtering():
        """Get context filtering status"""
        try:
            stats = mcp_client.get_context_stats()

            return jsonify({
                'success': True,
                'data': stats
            })
        except Exception as e:
            logger.error(f"Failed to get context filtering status: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            'success': False,
            'error': 'Endpoint not found'
        }), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500

    return app


if __name__ == '__main__':
    app = create_app()

    # Read configuration from environment
    host = os.getenv('MCP_WEB_CLIENT_HOST', 'localhost')
    port = int(os.getenv('MCP_WEB_CLIENT_PORT', '5000'))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    app.run(host=host, port=port, debug=debug)
