// MCP Client Web UI - Chat Interface JavaScript

// API Base URL
const API_BASE = '/api';

// Current state
let currentConversationId = null;
let isProcessing = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    init();
});

async function init() {
    // Setup event listeners
    setupEventListeners();

    // Restore sidebar state from localStorage
    restoreSidebarState();

    // Check service health
    await checkHealth();

    // Load conversations list
    await loadConversations();

    // Load tools list
    await loadTools();

    // Don't create conversation until first message is sent
    // Show welcome message without creating empty conversation
    showWelcomeMessage();

    // Update context stats periodically
    setInterval(updateContextStats, 5000);
}

function showWelcomeMessage() {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML = `
        <div class="message system-message">
            <div class="message-content">
                <h2>Welcome to Job Chat!</h2>
                <p>Control your job search system with natural language.</p>
                <ul>
                    <li>Create and manage profiles</li>
                    <li>Search for jobs</li>
                    <li>Match jobs against your resume</li>
                    <li>View statistics and reports</li>
                </ul>
                <p><strong>Try:</strong> "Show me my current profile" or "List all available tools"</p>
            </div>
        </div>
    `;
}

function setupEventListeners() {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const newChatBtn = document.getElementById('new-chat-btn');
    const settingsBtn = document.getElementById('settings-btn');
    const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileBackdrop = document.getElementById('mobile-backdrop');

    // Send button
    sendBtn.addEventListener('click', sendMessage);

    // Enter to send, Shift+Enter for newline
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Enable/disable send button based on input
    userInput.addEventListener('input', () => {
        const hasText = userInput.value.trim().length > 0;
        sendBtn.disabled = !hasText || isProcessing;
    });

    // Auto-resize textarea
    userInput.addEventListener('input', () => {
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';
    });

    // New chat button
    newChatBtn.addEventListener('click', createNewConversation);

    // Settings button
    settingsBtn.addEventListener('click', openSettings);

    // Toggle sidebar button (desktop)
    toggleSidebarBtn.addEventListener('click', toggleSidebar);

    // Mobile menu button
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', toggleMobileSidebar);
    }

    // Mobile backdrop click - close sidebar
    if (mobileBackdrop) {
        mobileBackdrop.addEventListener('click', closeMobileSidebar);
    }
}

async function checkHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        if (data.success) {
            const health = data.data;
            updateServiceStatus('llama', health.llama_server, health.llama_message);
            updateServiceStatus('mcp', health.mcp_server, health.mcp_message);
        }
    } catch (error) {
        console.error('Health check failed:', error);
        updateServiceStatus('llama', 'offline', 'Health check failed');
        updateServiceStatus('mcp', 'offline', 'Health check failed');
    }
}

function updateServiceStatus(service, status, message) {
    const statusDot = document.getElementById(`${service}-status`);
    if (statusDot) {
        // Update status indicator class (online/loading/offline)
        statusDot.className = `status-dot ${status}`;

        // Update tooltip/title with detailed message
        const statusContainer = statusDot.parentElement;
        if (statusContainer) {
            statusContainer.title = message || status;
        }
    }
}

async function loadConversations() {
    try {
        const response = await fetch(`${API_BASE}/conversations?limit=10`);
        const data = await response.json();

        if (data.success) {
            displayConversations(data.data.conversations);
        }
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

function displayConversations(conversations) {
    const list = document.getElementById('conversations-list');

    if (conversations.length === 0) {
        list.innerHTML = '<p class="text-secondary">No conversations yet</p>';
        return;
    }

    list.innerHTML = conversations.map(conv => `
        <div class="conversation-item ${conv.id === currentConversationId ? 'active' : ''}" data-conv-id="${conv.id}">
            <div class="conversation-main" onclick="loadConversation('${conv.id}')">
                <div class="conversation-title"
                     ondblclick="event.stopPropagation(); startEditConversation('${conv.id}')">
                    ${escapeHtml(conv.title)}
                </div>
                <div class="conversation-meta">${conv.message_count} messages</div>
            </div>
            <div class="conversation-actions">
                <button class="btn-edit-conversation"
                        onclick="event.stopPropagation(); startEditConversation('${conv.id}')"
                        title="Rename conversation">
                    ✏️
                </button>
                <button class="btn-delete-conversation"
                        onclick="event.stopPropagation(); deleteConversation('${conv.id}')"
                        title="Delete conversation">
                    🗑️
                </button>
            </div>
        </div>
    `).join('');
}

async function loadTools() {
    try {
        const response = await fetch(`${API_BASE}/tools`);
        const data = await response.json();

        if (data.success) {
            displayTools(data.data.by_category);
        }
    } catch (error) {
        console.error('Failed to load tools:', error);
    }
}

function displayTools(toolsByCategory) {
    const list = document.getElementById('tools-list');

    const html = Object.entries(toolsByCategory).map(([category, tools]) => `
        <div class="tool-category">
            <div class="tool-category-name">${category.replace('_', ' ')}</div>
            ${tools.map(tool => `
                <div class="tool-item clickable"
                     onclick="insertToolTemplate('${tool}')"
                     title="Click to insert template">
                    • ${tool}
                </div>
            `).join('')}
        </div>
    `).join('');

    list.innerHTML = html;
}

async function createNewConversation() {
    try {
        const response = await fetch(`${API_BASE}/conversation/new`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: `Chat ${new Date().toLocaleString()}`
            })
        });

        const data = await response.json();

        if (data.success) {
            currentConversationId = data.data.conversation_id;

            // Clear messages and show welcome
            showWelcomeMessage();

            // Reload conversations list
            await loadConversations();

            // Focus input
            document.getElementById('user-input').focus();
        }
    } catch (error) {
        console.error('Failed to create conversation:', error);
        throw error; // Re-throw so caller can handle
    }
}

async function loadConversation(convId) {
    try {
        const response = await fetch(`${API_BASE}/conversation/${convId}`);
        const data = await response.json();

        if (data.success) {
            currentConversationId = convId;
            const conversation = data.data;

            // Get list of excluded message indices
            const excludedIndices = new Set(conversation.excluded_messages || []);

            // Display messages
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML = '';

            conversation.messages.forEach((msg, index) => {
                const isExcluded = excludedIndices.has(index);
                appendMessage(msg.role, msg.content, msg.name, index, isExcluded);
            });

            // Update conversations list
            await loadConversations();

            // Update context stats
            await updateContextStats();

            // Scroll to bottom
            scrollToBottom();
        }
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

async function sendMessage() {
    if (isProcessing) return;

    const userInput = document.getElementById('user-input');
    const message = userInput.value.trim();

    if (!message) return;

    // Create conversation if this is the first message
    if (currentConversationId === null) {
        try {
            await createNewConversation();
        } catch (error) {
            console.error('Failed to create conversation:', error);
            appendMessage('system', 'Error: Failed to create conversation');
            return;
        }
    }

    // Clear input
    userInput.value = '';
    userInput.style.height = 'auto';

    // Set processing state
    isProcessing = true;

    // Show user message
    appendMessage('user', message);

    // Show loading indicators
    showLoading(true);
    showTypingIndicator();
    setInputState(false);

    scrollToBottom();

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await response.json();

        // Hide typing indicator
        hideTypingIndicator();

        if (data.success) {
            // Show tool calls first (if any)
            if (data.data.tool_calls && data.data.tool_calls.length > 0) {
                for (const toolCall of data.data.tool_calls) {
                    appendMessage('tool', toolCall.content, toolCall.tool_name);
                }
            }

            // Show assistant response
            appendMessage('assistant', data.data.response);

            // Update context stats
            updateContextStatsFromData(data.data.context_stats);

            // Show pointers if any
            if (data.data.pointers && data.data.pointers.length > 0) {
                showPointers(data.data.pointers);
            }

            // Reload conversations list to show the new conversation
            await loadConversations();

            scrollToBottom();
        } else {
            appendMessage('system', `Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Failed to send message:', error);
        hideTypingIndicator();
        appendMessage('system', `Error: ${error.message}`);
    } finally {
        isProcessing = false;
        showLoading(false);
        setInputState(true);

        userInput.focus();
    }
}

function appendMessage(role, content, toolName = null, messageIndex = null, isExcluded = false) {
    const messagesDiv = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    // Add excluded class if message is excluded from context
    if (isExcluded) {
        messageDiv.classList.add('excluded');
    }

    if (role === 'tool') {
        // Tool call message
        messageDiv.className = 'message tool-call';
        messageDiv.innerHTML = `
            <div class="tool-call-header">
                <span>🔧 Tool: ${toolName}</span>
            </div>
            <div class="tool-call-params">${escapeHtml(content)}</div>
        `;
    } else {
        // Regular message
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (role === 'assistant' || role === 'system') {
            // Render markdown
            contentDiv.innerHTML = marked.parse(content);

            // Highlight code blocks
            contentDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        } else {
            contentDiv.textContent = content;
        }

        messageDiv.appendChild(contentDiv);

        // Add exclude/restore button for user and assistant messages
        if ((role === 'user' || role === 'assistant') && messageIndex !== null && currentConversationId) {
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';

            if (isExcluded) {
                actionsDiv.innerHTML = `
                    <button class="btn-restore-message"
                            onclick="restoreMessageToContext(${messageIndex})"
                            title="Restore to context">
                        ↩️ Restore
                    </button>
                    <span class="excluded-badge">Not in context</span>
                `;
            } else {
                actionsDiv.innerHTML = `
                    <button class="btn-exclude-message"
                            onclick="excludeMessageFromContext(${messageIndex})"
                            title="Exclude from context">
                        ⊖ Exclude
                    </button>
                `;
            }

            messageDiv.appendChild(actionsDiv);
        }
    }

    messagesDiv.appendChild(messageDiv);
}

function showPointers(pointers) {
    const messagesDiv = document.getElementById('messages');
    const pointerDiv = document.createElement('div');
    pointerDiv.className = 'message system-message';

    const summaries = pointers.map(p => `• ${p.summary} (${p.count} messages, ${p.token_count} tokens)`).join('<br>');

    pointerDiv.innerHTML = `
        <div class="message-content">
            <strong>📦 Archived Messages:</strong><br>
            ${summaries}
        </div>
    `;

    messagesDiv.appendChild(pointerDiv);
}

async function updateContextStats() {
    try {
        const response = await fetch(`${API_BASE}/context/stats`);
        const data = await response.json();

        if (data.success) {
            updateContextStatsFromData(data.data);
        }
    } catch (error) {
        console.error('Failed to update context stats:', error);
    }
}

function updateContextStatsFromData(stats) {
    // Token count
    const tokenCount = document.getElementById('token-count');
    if (tokenCount) {
        tokenCount.textContent = `${stats.total_tokens || 0} / ${stats.max_tokens || 8192}`;
    }

    // Message count
    const messageCount = document.getElementById('message-count');
    if (messageCount) {
        messageCount.textContent = stats.message_count || 0;
    }

    // Health indicator
    const healthIndicator = document.getElementById('context-health');
    if (healthIndicator) {
        const health = stats.health || 'healthy';
        healthIndicator.className = `health-indicator ${health}`;

        const usagePercent = stats.usage_percent || 0;
        let dots;

        if (usagePercent < 30) {
            dots = '●●●●●';
        } else if (usagePercent < 50) {
            dots = '●●●●○';
        } else if (usagePercent < 70) {
            dots = '●●●○○';
        } else if (usagePercent < 85) {
            dots = '●●○○○';
        } else {
            dots = '●○○○○';
        }

        healthIndicator.textContent = dots;
    }
}

function showLoading(show) {
    const indicator = document.getElementById('loading-indicator');
    if (show) {
        indicator.classList.remove('hidden');
    } else {
        indicator.classList.add('hidden');
    }
}

function showTypingIndicator() {
    // Remove existing typing indicator if any
    hideTypingIndicator();

    const messagesDiv = document.getElementById('messages');
    const typingDiv = document.createElement('div');
    typingDiv.id = 'typing-indicator';
    typingDiv.className = 'message typing-message';
    typingDiv.innerHTML = `
        <div class="typing-bubble">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
            <span class="typing-text">AI is thinking...</span>
        </div>
    `;

    messagesDiv.appendChild(typingDiv);
    scrollToBottom();
}

function hideTypingIndicator() {
    const typingDiv = document.getElementById('typing-indicator');
    if (typingDiv) {
        typingDiv.remove();
    }
}

function setInputState(enabled) {
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');

    if (enabled) {
        userInput.disabled = false;
        userInput.classList.remove('input-disabled');
        userInput.placeholder = 'Type your message here...';
        sendBtn.disabled = userInput.value.trim().length === 0;
    } else {
        userInput.disabled = true;
        userInput.classList.add('input-disabled');
        userInput.placeholder = 'Processing...';
        sendBtn.disabled = true;
    }
}

function scrollToBottom() {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function toggleSection(sectionName) {
    const section = document.querySelector(`.${sectionName}-section`);
    if (section) {
        section.classList.toggle('collapsed');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function deleteConversation(convId) {
    // Confirmation dialog
    if (!confirm('Are you sure you want to delete this conversation? This action cannot be undone.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/conversation/${convId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            // If deleted conversation was active, clear current conversation
            if (currentConversationId === convId) {
                currentConversationId = null;
                showWelcomeMessage();
            }

            // Reload conversations list
            await loadConversations();

            console.log(`Conversation ${convId} deleted successfully`);
        } else {
            console.error('Failed to delete conversation:', data.error);
            alert(`Failed to delete conversation: ${data.error}`);
        }
    } catch (error) {
        console.error('Error deleting conversation:', error);
        alert(`Error deleting conversation: ${error.message}`);
    }
}

async function openSettings() {
    // Create modal if it doesn't exist
    let modal = document.getElementById('settings-modal');

    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'settings-modal';
        modal.className = 'modal';
        document.body.appendChild(modal);
    }

    // Fetch current health/stats to display in settings
    let healthInfo = '';
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        if (data.success) {
            const health = data.data;
            healthInfo = `
                <div class="settings-section">
                    <h3>🏥 Service Status</h3>
                    <div class="settings-item">
                        <span>llama-server:</span>
                        <span class="status-badge status-${health.llama_server}">${health.llama_server}</span>
                    </div>
                    <div class="settings-item-detail">${health.llama_message}</div>
                    <div class="settings-item">
                        <span>MCP server:</span>
                        <span class="status-badge status-${health.mcp_server}">${health.mcp_server}</span>
                    </div>
                    <div class="settings-item-detail">${health.mcp_message}</div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to fetch health info:', error);
    }

    // Get conversation stats
    let conversationStats = '';
    try {
        const response = await fetch(`${API_BASE}/conversations`);
        const data = await response.json();

        if (data.success) {
            conversationStats = `
                <div class="settings-section">
                    <h3>💬 Conversation Stats</h3>
                    <div class="settings-item">
                        <span>Total conversations:</span>
                        <span>${data.data.count}</span>
                    </div>
                </div>
            `;
        }
    } catch (error) {
        console.error('Failed to fetch conversation stats:', error);
    }

    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>🛈 Information</h2>
                <button class="btn-close" onclick="closeSettings()">×</button>
            </div>
            <div class="modal-body">
                ${healthInfo}
                ${conversationStats}
                <div class="settings-section">
                    <h3>🗑️ Data Management</h3>
                    <button class="btn btn-danger" onclick="clearAllConversations()">
                        Clear All Conversations
                    </button>
                    <p class="settings-hint">This will delete all saved conversations permanently.</p>
                </div>
                <div class="settings-section">
                    <h3>🛈 About</h3>
                    <p>Job Search AI Assistant</p>
                    <p class="settings-hint">Powered by local LLM via llama-server</p>
                </div>
            </div>
        </div>
    `;

    modal.style.display = 'flex';
}

function closeSettings() {
    const modal = document.getElementById('settings-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function clearAllConversations() {
    if (!confirm('Are you sure you want to delete ALL conversations? This action cannot be undone!')) {
        return;
    }

    try {
        // Get all conversations
        const response = await fetch(`${API_BASE}/conversations`);
        const data = await response.json();

        if (data.success) {
            const conversations = data.data.conversations;

            // Delete each conversation
            for (const conv of conversations) {
                await fetch(`${API_BASE}/conversation/${conv.id}`, {
                    method: 'DELETE'
                });
            }

            // Clear current conversation
            currentConversationId = null;
            showWelcomeMessage();

            // Reload conversations list
            await loadConversations();

            // Close settings
            closeSettings();

            alert('All conversations have been deleted.');
        }
    } catch (error) {
        console.error('Error clearing conversations:', error);
        alert(`Error clearing conversations: ${error.message}`);
    }
}

// ============================================================================
// Feature: Message Context Exclusion
// ============================================================================

async function excludeMessageFromContext(messageIndex) {
    if (!currentConversationId) {
        console.error('No active conversation');
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE}/conversation/${currentConversationId}/message/${messageIndex}/exclude`,
            { method: 'POST' }
        );

        const data = await response.json();

        if (data.success) {
            // Reload conversation to reflect exclusion
            await loadConversation(currentConversationId);
            console.log(`Message ${messageIndex} excluded from context`);
        } else {
            console.error('Failed to exclude message:', data.error);
            alert(`Failed to exclude message: ${data.error}`);
        }
    } catch (error) {
        console.error('Error excluding message:', error);
        alert(`Error excluding message: ${error.message}`);
    }
}

async function restoreMessageToContext(messageIndex) {
    if (!currentConversationId) {
        console.error('No active conversation');
        return;
    }

    try {
        const response = await fetch(
            `${API_BASE}/conversation/${currentConversationId}/message/${messageIndex}/restore`,
            { method: 'POST' }
        );

        const data = await response.json();

        if (data.success) {
            // Reload conversation to reflect restoration
            await loadConversation(currentConversationId);
            console.log(`Message ${messageIndex} restored to context`);
        } else {
            console.error('Failed to restore message:', data.error);
            alert(`Failed to restore message: ${data.error}`);
        }
    } catch (error) {
        console.error('Error restoring message:', error);
        alert(`Error restoring message: ${error.message}`);
    }
}

// ============================================================================
// Feature: Conversation Renaming
// ============================================================================

function startEditConversation(convId) {
    // Find conversation item by data attribute
    const conversationItem = document.querySelector(`.conversation-item[data-conv-id="${convId}"]`);
    if (!conversationItem) {
        console.error(`Conversation item not found: ${convId}`);
        return;
    }

    const titleDiv = conversationItem.querySelector('.conversation-title');
    if (!titleDiv) {
        console.error('Title div not found');
        return;
    }

    // Get current title text
    const currentTitle = titleDiv.textContent.trim();

    // Store original state
    const originalHTML = titleDiv.innerHTML;
    titleDiv.dataset.originalHtml = originalHTML;

    // Replace with input field
    titleDiv.innerHTML = `
        <input type="text"
               class="conversation-title-input"
               value="${escapeHtml(currentTitle)}"
               onclick="event.stopPropagation()"
               onkeydown="handleConversationRenameKeydown(event, '${convId}')"
               onblur="cancelEditConversation(this)" />
    `;

    // Focus and select text
    const input = titleDiv.querySelector('input');
    if (input) {
        input.focus();
        input.select();
    }
}

function handleConversationRenameKeydown(event, convId) {
    if (event.key === 'Enter') {
        event.preventDefault();
        saveConversationTitle(convId, event.target.value);
    } else if (event.key === 'Escape') {
        cancelEditConversation(event.target);
    }
}

async function saveConversationTitle(convId, newTitle) {
    const trimmedTitle = newTitle.trim();

    if (!trimmedTitle) {
        alert('Conversation title cannot be empty');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/conversation/${convId}/title`, {
            method: 'PATCH',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title: trimmedTitle })
        });

        const data = await response.json();

        if (data.success) {
            // Reload conversations list to show updated title
            await loadConversations();
            console.log(`Conversation ${convId} renamed to "${trimmedTitle}"`);
        } else {
            console.error('Failed to rename conversation:', data.error);
            alert(`Failed to rename conversation: ${data.error}`);
            // Reload to restore original state
            await loadConversations();
        }
    } catch (error) {
        console.error('Error renaming conversation:', error);
        alert(`Error renaming conversation: ${error.message}`);
        // Reload to restore original state
        await loadConversations();
    }
}

function cancelEditConversation(input) {
    const titleDiv = input.parentElement;
    if (titleDiv.dataset.originalHtml) {
        titleDiv.innerHTML = titleDiv.dataset.originalHtml;
        delete titleDiv.dataset.originalHtml;
    }
}

// ============================================================================
// Feature: Tool Template Pre-population
// ============================================================================

async function insertToolTemplate(toolName) {
    try {
        // Generate human-readable instruction for the LLM
        const humanReadableText = `Please use the ${toolName} tool`;

        const userInput = document.getElementById('user-input');
        userInput.value = humanReadableText;
        userInput.focus();

        // Trigger input event to enable send button
        userInput.dispatchEvent(new Event('input'));

        // Auto-resize textarea
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';

        console.log(`Tool template for "${toolName}" inserted`);
    } catch (error) {
        console.error('Error inserting tool template:', error);
    }
}

// Close modal when clicking outside
document.addEventListener('click', (e) => {
    const modal = document.getElementById('settings-modal');
    if (modal && e.target === modal) {
        closeSettings();
    }
});

// ============================================================================
// Feature: Sidebar Toggle
// ============================================================================

function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar-btn');

    // Detect mobile viewport
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        sidebar.classList.toggle('open');
        toggleBtn.textContent = sidebar.classList.contains('open') ? '◀' : '▶';
        toggleBtn.title = sidebar.classList.contains('open') ? 'Hide sidebar' : 'Show sidebar';
    } else {
        sidebar.classList.toggle('collapsed');
        toggleBtn.textContent = sidebar.classList.contains('collapsed') ? '▶' : '◀';
        toggleBtn.title = sidebar.classList.contains('collapsed') ? 'Show sidebar' : 'Hide sidebar';
        localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
    }
}


function restoreSidebarState() {
    const sidebar = document.querySelector('.sidebar');
    const toggleBtn = document.getElementById('toggle-sidebar-btn');

    // Only restore on desktop (not mobile)
    const isMobile = window.innerWidth <= 768;

    if (!isMobile) {
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';

        if (isCollapsed) {
            sidebar.classList.add('collapsed');
            toggleBtn.textContent = '▶';
            toggleBtn.title = 'Show sidebar';
        } else {
            sidebar.classList.remove('collapsed');
            toggleBtn.textContent = '◀';
            toggleBtn.title = 'Hide sidebar';
        }
    }
}

// ============================================================================
// Feature: Mobile Sidebar Controls
// ============================================================================

function toggleMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('mobile-backdrop');

    if (sidebar.classList.contains('open')) {
        closeMobileSidebar();
    } else {
        openMobileSidebar();
    }
}

function openMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('mobile-backdrop');

    sidebar.classList.add('open');
    backdrop.classList.add('visible');

    // Prevent body scroll when sidebar is open
    document.body.style.overflow = 'hidden';
}

function closeMobileSidebar() {
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('mobile-backdrop');

    sidebar.classList.remove('open');
    backdrop.classList.remove('visible');

    // Restore body scroll
    document.body.style.overflow = '';
}

// Close mobile sidebar when switching conversations
const originalLoadConversation = loadConversation;
loadConversation = async function(convId) {
    await originalLoadConversation(convId);

    // Close sidebar on mobile after selecting conversation
    const isMobile = window.innerWidth <= 768;
    if (isMobile) {
        closeMobileSidebar();
    }
};
