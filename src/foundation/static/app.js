// WebSocket chat client
class ChatClient {
    constructor() {
        this.conversations = new Map();
        this.agents = new Map();  // agent_id -> {ws, element, status}
        this.activeView = 'chat';
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

        // Navigation - use event delegation for dynamic tabs
        const navTabs = document.getElementById('navTabs');
        navTabs.addEventListener('click', (e) => {
            const navItem = e.target.closest('.nav-item');
            if (!navItem) return;

            const view = navItem.dataset.view;
            this.switchView(view);

            // Update active state
            navTabs.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            navItem.classList.add('active');
        });

        // Close button for agent tabs
        navTabs.addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-close')) {
                e.stopPropagation();
                const agentId = e.target.dataset.agentId;
                this.closeAgent(agentId);
            }
        });

        // New agent button
        const newAgentBtn = document.getElementById('newAgentBtn');
        newAgentBtn.addEventListener('click', () => this.createAgent());
    }

    switchView(view) {
        this.activeView = view;

        // Hide all views
        document.getElementById('chatView').style.display = 'none';
        document.getElementById('toolsView').style.display = 'none';

        // Hide all agent views
        this.agents.forEach((agent) => {
            if (agent.element) {
                agent.element.style.display = 'none';
            }
        });

        // Show selected view
        if (view === 'chat') {
            document.getElementById('chatView').style.display = 'flex';
        } else if (view === 'tools') {
            document.getElementById('toolsView').style.display = 'block';
            this.loadToolsView();
        } else if (view.startsWith('agent-')) {
            const agent = this.agents.get(view);
            if (agent && agent.element) {
                agent.element.style.display = 'flex';
            }
        }
    }

    async createAgent() {
        try {
            const response = await fetch('/api/agents', { method: 'POST' });
            const data = await response.json();
            const agentId = data.id;

            // Create agent tab
            const navTabs = document.getElementById('navTabs');
            const tabDiv = document.createElement('div');
            tabDiv.className = 'nav-item agent-tab';
            tabDiv.dataset.view = agentId;
            tabDiv.innerHTML = `${agentId} <span class="tab-close" data-agent-id="${agentId}">×</span>`;
            navTabs.appendChild(tabDiv);

            // Clone agent template
            const template = document.getElementById('agentTemplate');
            const agentView = template.content.cloneNode(true).querySelector('.agent-view');
            agentView.id = `view-${agentId}`;
            agentView.style.display = 'none';
            document.querySelector('.container').appendChild(agentView);

            // Store agent reference
            this.agents.set(agentId, {
                ws: null,
                element: agentView,
                status: 'ready'
            });

            // Setup agent controls
            this.setupAgentControls(agentId, agentView);

            // Connect WebSocket
            this.connectAgent(agentId);

            // Switch to agent view
            navTabs.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
            tabDiv.classList.add('active');
            this.switchView(agentId);

        } catch (error) {
            console.error('Failed to create agent:', error);
        }
    }

    setupAgentControls(agentId, element) {
        const contractInput = element.querySelector('.agent-contract');
        const startBtn = element.querySelector('.btn-start');
        const stopBtn = element.querySelector('.btn-stop');
        const restartBtn = element.querySelector('.btn-restart');

        startBtn.addEventListener('click', () => {
            const agent = this.agents.get(agentId);
            if (agent && agent.ws) {
                // Send contract first
                agent.ws.send(JSON.stringify({
                    type: 'set_contract',
                    contract: contractInput.value
                }));
                // Then start
                agent.ws.send(JSON.stringify({ type: 'start' }));
            }
        });

        stopBtn.addEventListener('click', () => {
            const agent = this.agents.get(agentId);
            if (agent && agent.ws) {
                agent.ws.send(JSON.stringify({ type: 'stop' }));
            }
        });

        restartBtn.addEventListener('click', () => {
            const agent = this.agents.get(agentId);
            if (agent && agent.ws) {
                agent.ws.send(JSON.stringify({ type: 'restart' }));
                // Clear output
                element.querySelector('.agent-output').innerHTML = '';
            }
        });
    }

    connectAgent(agentId) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/agent/${agentId}`);
        const agent = this.agents.get(agentId);

        ws.onopen = () => {
            console.log(`Connected to agent: ${agentId}`);
            agent.ws = ws;
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleAgentMessage(agentId, data);
        };

        ws.onerror = (error) => {
            console.error(`Agent ${agentId} WebSocket error:`, error);
        };

        ws.onclose = () => {
            console.log(`Disconnected from agent: ${agentId}`);
        };

        agent.ws = ws;
    }

    handleAgentMessage(agentId, data) {
        const agent = this.agents.get(agentId);
        if (!agent) return;

        const element = agent.element;
        const outputDiv = element.querySelector('.agent-output');
        const statusSpan = element.querySelector('.agent-status');
        const contractInput = element.querySelector('.agent-contract');
        const startBtn = element.querySelector('.btn-start');
        const stopBtn = element.querySelector('.btn-stop');
        const restartBtn = element.querySelector('.btn-restart');

        switch (data.type) {
            case 'init':
                if (data.contract) {
                    contractInput.value = data.contract;
                }
                break;

            case 'status':
                agent.status = data.content;
                statusSpan.textContent = data.content.charAt(0).toUpperCase() + data.content.slice(1);
                statusSpan.className = `agent-status status-${data.content}`;

                // Update button visibility
                if (data.content === 'running') {
                    startBtn.style.display = 'none';
                    stopBtn.style.display = 'inline-block';
                    restartBtn.style.display = 'none';
                    contractInput.disabled = true;
                } else if (data.content === 'ready') {
                    startBtn.style.display = 'inline-block';
                    stopBtn.style.display = 'none';
                    restartBtn.style.display = 'none';
                    contractInput.disabled = false;
                } else {
                    // stopped or completed
                    startBtn.style.display = 'none';
                    stopBtn.style.display = 'none';
                    restartBtn.style.display = 'inline-block';
                    contractInput.disabled = true;
                }
                break;

            case 'assistant':
            case 'system':
            case 'error':
                this.addAgentOutput(outputDiv, data.type, data.content);
                break;

            case 'tool':
                if (data.tool_call) {
                    this.addAgentOutput(outputDiv, 'tool', `[Tool: ${data.tool_call}]`);
                }
                break;
        }
    }

    addAgentOutput(outputDiv, type, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `agent-message ${type}`;
        msgDiv.textContent = content;
        outputDiv.appendChild(msgDiv);

        // Auto-scroll
        const container = outputDiv.parentElement;
        container.scrollTop = container.scrollHeight;
    }

    closeAgent(agentId) {
        const agent = this.agents.get(agentId);
        if (!agent) return;

        // Close WebSocket
        if (agent.ws) {
            agent.ws.close();
        }

        // Remove element
        if (agent.element) {
            agent.element.remove();
        }

        // Remove tab
        const tab = document.querySelector(`.nav-item[data-view="${agentId}"]`);
        if (tab) {
            tab.remove();
        }

        // Remove from map
        this.agents.delete(agentId);

        // Delete from server
        fetch(`/api/agents/${agentId}`, { method: 'DELETE' });

        // Switch to chat view
        if (this.activeView === agentId) {
            const chatTab = document.querySelector('.nav-item[data-view="chat"]');
            chatTab.classList.add('active');
            this.switchView('chat');
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
