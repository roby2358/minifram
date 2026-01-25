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

        // Tools button
        const toolsBtn = document.getElementById('toolsBtn');
        const toolsPanel = document.getElementById('toolsPanel');

        toolsBtn.addEventListener('click', () => {
            const isVisible = toolsPanel.style.display !== 'none';
            toolsPanel.style.display = isVisible ? 'none' : 'block';
        });

        // New agent button (Phase 3)
        const newAgentBtn = document.getElementById('newAgentBtn');
        newAgentBtn.addEventListener('click', () => {
            alert('Agent spawning coming in Phase 3');
        });
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
            case 'error':
                this.addMessage('error', data.content);
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
        try {
            const response = await fetch('/api/tools');
            const data = await response.json();

            const toolsList = document.getElementById('toolsList');

            if (data.tools.length === 0) {
                toolsList.innerHTML = '<div class="tool-item">No tools configured</div>';
                return;
            }

            toolsList.innerHTML = data.tools.map(tool =>
                `<div class="tool-item ${tool.status}">${tool.name} (${tool.status})</div>`
            ).join('');
        } catch (error) {
            console.error('Failed to load tools:', error);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new ChatClient();
});
