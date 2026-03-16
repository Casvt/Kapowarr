class AirDCCSource {
    constructor() {
        this.name = 'AirDCC++';
        this.type = 'airdcc';
        this.enabled = false;
        this.config = {
            server_url: 'http://localhost:5115',
            username: '',
            password: '',
            timeout: 30,
            max_results: 100
        };
    }
    
    async search(query, filters = {}) {
        try {
            const response = await fetch('/api/sources/airdcc/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query, filters })
            });
            
            const data = await response.json();
            return data.results || [];
        } catch (error) {
            console.error('AirDCC++ search error:', error);
            return [];
        }
    }
    
    async testConnection() {
        try {
            const response = await fetch('/api/sources/airdcc/test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            return data.connected || false;
        } catch (error) {
            console.error('AirDCC++ connection test error:', error);
            return false;
        }
    }
    
    renderSettings() {
        return `
            <div class="source-settings" id="airdcc-settings">
                <h3>AirDCC++ Settings</h3>
                <div class="form-group">
                    <label for="airdcc-server-url">Server URL:</label>
                    <input type="text" id="airdcc-server-url" value="${this.config.server_url}" 
                           class="form-control" placeholder="http://localhost:5115">
                </div>
                <div class="form-group">
                    <label for="airdcc-username">Username:</label>
                    <input type="text" id="airdcc-username" value="${this.config.username}" 
                           class="form-control">
                </div>
                <div class="form-group">
                    <label for="airdcc-password">Password:</label>
                    <input type="password" id="airdcc-password" value="${this.config.password}" 
                           class="form-control">
                </div>
                <div class="form-group">
                    <label for="airdcc-timeout">Timeout (seconds):</label>
                    <input type="number" id="airdcc-timeout" value="${this.config.timeout}" 
                           class="form-control" min="5" max="300">
                </div>
                <div class="form-group">
                    <label for="airdcc-max-results">Max Results:</label>
                    <input type="number" id="airdcc-max-results" value="${this.config.max_results}" 
                           class="form-control" min="10" max="1000">
                </div>
                <button class="btn btn-primary" onclick="testAirDCCConnection()">Test Connection</button>
            </div>
        `;
    }
}

// Add to source manager
const sourceManager = {
    sources: {
        airdcc: new AirDCCSource()
    }
};

async function testAirDCCConnection() {
    const source = sourceManager.sources.airdcc;
    const isConnected = await source.testConnection();
    
    if (isConnected) {
        showNotification('AirDCC++ connection successful!', 'success');
    } else {
        showNotification('AirDCC++ connection failed!', 'error');
    }
}
