// WebSocket chat client
class ChatClient {
    constructor() {
        this.conversations = new Map();
        this.activeConversation = 'chat';
        this.setupUI();
        this.connect(this.activeConversation);
        this.loadTools();
    }

    setupUI() {
        // Send button
        const sendBtn = document.getElementById('sendBtn');
        const messageInput = document.getElementById('messageInput');

        sendBtn.addEventListener('click', () => this.sendMessage());

        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        messageInput.addEventListener('input', (e) => {
            e.target.style.height = 'auto';
            e.target.style.height = e.target.scrollHeight + 'px';
        });

        // Navigation
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const view = item.dataset.view;
                this.switchView(view);

                // Update active state
                navItems.forEach(i => i.classList.remove('active'));
                item.classList.add('active');
            });
        });

        // New agent button (Phase 3)
        const newAgentBtn = document.getElementById('newAgentBtn');
        newAgentBtn.addEventListener('click', () => {
            alert('Agent spawning coming in Phase 3');
        });
    }

    switchView(view) {
        // Hide all views
        document.getElementById('chatView').style.display = 'none';
        document.getElementById('toolsView').style.display = 'none';

        // Show selected view
        if (view === 'chat') {
            document.getElementById('chatView').style.display = 'flex';
        } else if (view === 'tools') {
            document.getElementById('toolsView').style.display = 'block';
            this.loadToolsView();
        }
    }

    connect(conversationId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${conversationId}`);

        ws.onopen = () => {
            console.log(`Connected to conversation: ${conversationId}`);
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.addMessage('error', 'Connection error. Check that your LLM server is running.');
        };

        ws.onclose = () => {
            console.log(`Disconnected from conversation: ${conversationId}`);
            this.addMessage('system', 'Disconnected from server');
        };

        this.conversations.set(conversationId, ws);
    }

    handleMessage(data) {
        switch (data.type) {
            case 'system':
                this.addMessage('system', data.content);
                break;
            case 'message':
                this.addMessage(data.role, data.content, data.tool_call);
                break;
            case 'reasoning':
                this.addReasoning(data.content);
                break;
            case 'error':
                this.addMessage('error', data.content);
                break;
            case 'loading':
                this.showLoading(data.content);
                break;
            case 'loading_done':
                this.hideLoading();
                break;
        }
    }

    addMessage(role, content, toolCall = null) {
        const messagesDiv = document.getElementById('messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        if (toolCall) {
            // Truncate tool calls to 80 characters
            const truncated = toolCall.length > 80
                ? toolCall.substring(0, 77) + '...'
                : toolCall;
            messageDiv.textContent = `[Tool: ${truncated}]`;
            messageDiv.className = 'message tool';
        } else {
            messageDiv.textContent = content;
        }

        messagesDiv.appendChild(messageDiv);

        // Auto-scroll to bottom
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    showLoading(message) {
        const messagesDiv = document.getElementById('messages');

        // Remove any existing loading indicator
        const existing = messagesDiv.querySelector('.message.loading');
        if (existing) {
            existing.remove();
        }

        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message loading';
        loadingDiv.innerHTML = `<span class="loading-dots">${message}</span>`;
        messagesDiv.appendChild(loadingDiv);

        // Auto-scroll to bottom
        const chatContainer = document.getElementById('chatContainer');
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    hideLoading() {
        const messagesDiv = document.getElementById('messages');
        const loadingDiv = messagesDiv.querySelector('.message.loading');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }

    addReasoning(content) {
        const reasoningDiv = document.getElementById('reasoningMessages');

        // Remove empty state
        const emptyState = reasoningDiv.querySelector('.empty-reasoning');
        if (emptyState) {
            emptyState.remove();
        }

        const reasoningItem = document.createElement('div');
        reasoningItem.className = 'reasoning-item thinking';
        reasoningItem.textContent = content;
        reasoningDiv.appendChild(reasoningItem);

        // Auto-scroll to bottom
        const reasoningContainer = document.getElementById('reasoningContainer');
        reasoningContainer.scrollTop = reasoningContainer.scrollHeight;
    }

    sendMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();

        if (!content) return;

        const ws = this.conversations.get(this.activeConversation);
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            this.addMessage('error', 'Not connected to server');
            return;
        }

        // Send message
        ws.send(JSON.stringify({
            type: 'message',
            content: content
        }));

        // Clear input
        input.value = '';
        input.style.height = 'auto';
    }

    async loadTools() {
        // This is now handled by loadToolsView
    }

    async loadToolsView() {
        try {
            const response = await fetch('/api/tools');
            const data = await response.json();

            const serversList = document.getElementById('serversList');
            const toolsDetails = document.getElementById('toolsDetails');

            // Display servers
            if (!data.servers || data.servers.length === 0) {
                serversList.innerHTML = '<div class="loading">No MCP servers configured</div>';
                toolsDetails.innerHTML = '<div class="loading">No tools available</div>';
                return;
            }

            // Render servers
            const serverItems = data.servers.map(server => {
                const statusClass = server.status === 'active' ? 'active' : 'broken';
                const statusIcon = server.status === 'active' ? '✓' : '✗';
                return `
                    <div class="server-item ${statusClass}">
                        <div class="server-name">${statusIcon} ${server.name}</div>
                        <div class="server-status">${server.tools} tools • ${server.status}</div>
                    </div>
                `;
            }).join('');
            serversList.innerHTML = serverItems;

            // Render tools
            if (!data.tools || data.tools.length === 0) {
                toolsDetails.innerHTML = '<div class="loading">No tools available</div>';
                return;
            }

            const toolItems = data.tools.map(tool => {
                return `
                    <div class="tool-detail">
                        <div class="tool-name">${tool.name}</div>
                        <div class="tool-description">${tool.description}</div>
                        <div class="tool-server">from ${tool._server}</div>
                    </div>
                `;
            }).join('');
            toolsDetails.innerHTML = toolItems;

        } catch (error) {
            console.error('Failed to load tools:', error);
            document.getElementById('serversList').innerHTML = '<div class="loading">Failed to load tools</div>';
            document.getElementById('toolsDetails').innerHTML = '<div class="loading">Failed to load tools</div>';
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatClient();
});
