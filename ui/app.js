const API_BASE = '..'; // Relative path from /ui/ to /

// State
const state = {
    path: [], // [{name: 'Sites', id: null}, {name: 'UC', id: 'uc'}, ...]
};

// DOM Elements
const content = document.getElementById('content');
const breadcrumbs = document.getElementById('breadcrumbs');
const loading = document.getElementById('loading');
const error = document.getElementById('error');

// Router/Navigator
function navigateTo(view, id = null, name = null) {
    // Basic routing logic
    if (view === 'sites') {
        state.path = [{ name: 'Sites', view: 'sites', id: null }];
        fetchSites();
    } else if (view === 'site') {
        // Find if we are going back or forward
        const idx = state.path.findIndex(p => p.view === 'site' && p.id === id);
        if (idx !== -1) {
             state.path = state.path.slice(0, idx + 1);
        } else {
            state.path.push({ name: name || id, view: 'site', id: id });
        }
        fetchClusters(id);
    } else if (view === 'cluster') {
        const idx = state.path.findIndex(p => p.view === 'cluster' && p.id === id);
        if (idx !== -1) {
             state.path = state.path.slice(0, idx + 1);
        } else {
            state.path.push({ name: name || id, view: 'cluster', id: id });
        }
        fetchNodes(state.path.find(p => p.view === 'site').id, id);
    } else if (view === 'node') {
         state.path.push({ name: name || id, view: 'node', id: id });
         fetchNodeDetails(
             state.path.find(p => p.view === 'site').id,
             state.path.find(p => p.view === 'cluster').id,
             id
         );
    }
    renderBreadcrumbs();
}

function renderBreadcrumbs() {
    breadcrumbs.innerHTML = '';
    state.path.forEach((step, index) => {
        if (index > 0) {
            const separator = document.createElement('span');
            separator.textContent = '/';
            breadcrumbs.appendChild(separator);
        }
        
        if (index === state.path.length - 1) {
            const active = document.createElement('span');
            active.textContent = step.name;
            active.style.color = 'var(--text-color)';
            active.style.fontWeight = '500';
            breadcrumbs.appendChild(active);
        } else {
            const link = document.createElement('a');
            link.href = '#';
            link.textContent = step.name;
            link.onclick = (e) => {
                e.preventDefault();
                // Reconstruct path up to this point
                state.path = state.path.slice(0, index); // pop until just before
                navigateTo(step.view, step.id, step.name);
            };
            breadcrumbs.appendChild(link);
        }
    });
}

// API Calls & Renderers

async function fetchSites() {
    setLoading(true);
    try {
        const res = await fetch(`${API_BASE}/sites?limit=100`);
        const data = await res.json();
        renderGrid(data.items, 'site');
    } catch (e) {
        showError(e);
    } finally {
        setLoading(false);
    }
}

async function fetchClusters(siteId) {
    setLoading(true);
    try {
        const res = await fetch(`${API_BASE}/sites/${siteId}/clusters?limit=100`);
        const data = await res.json();
        renderGrid(data.items, 'cluster');
    } catch (e) {
        showError(e);
    } finally {
        setLoading(false);
    }
}

async function fetchNodes(siteId, clusterId) {
    setLoading(true);
    try {
        const res = await fetch(`${API_BASE}/sites/${siteId}/clusters/${clusterId}/nodes?limit=100`);
        const data = await res.json();
        renderGrid(data.items, 'node');
    } catch (e) {
        showError(e);
    } finally {
        setLoading(false);
    }
}

async function fetchNodeDetails(siteId, clusterId, nodeId) {
    setLoading(true);
    try {
        const res = await fetch(`${API_BASE}/sites/${siteId}/clusters/${clusterId}/nodes/${nodeId}`);
        const data = await res.json();
        renderNodeDetail(data);
    } catch (e) {
        showError(e);
    } finally {
        setLoading(false);
    }
}

// UI Helpers

function setLoading(isLoading) {
    if (isLoading) {
        content.innerHTML = '';
        loading.classList.remove('hidden');
        error.classList.add('hidden');
    } else {
        loading.classList.add('hidden');
    }
}

function showError(msg) {
    error.textContent = `Error: ${msg}`;
    error.classList.remove('hidden');
    content.innerHTML = '';
}

function renderGrid(items, type) {
    content.innerHTML = '';
    const grid = document.createElement('div');
    grid.className = 'grid';

    items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        
        let title = item.name || item.uid || item.id;
        let subtitle = '';

        if (type === 'site') {
            title = item.name || item.uid;
            subtitle = item.location || item.description || '';
        } else if (type === 'cluster') {
             // Cluster doesn't strictly have a name field in the list usually, just 'uid' in the collection
             title = item.uid;
             subtitle = item.type || '';
        } else if (type === 'node') {
            title = item.node_name || item.uid;
            subtitle = item.node_type || '';
        }

        card.innerHTML = `
            <h2>${title}</h2>
            <p>${subtitle}</p>
        `;
        
        card.onclick = () => {
             navigateTo(type, item.uid, title);
        };
        grid.appendChild(card);
    });

    content.appendChild(grid);
}

function renderNodeDetail(node) {
    content.innerHTML = '';
    const container = document.createElement('div');
    container.className = 'detail-view';

    // Helper to render sections safely
    const renderSection = (title, data) => {
        if (!data || Object.keys(data).length === 0) return '';
        
        let propsHtml = '<div class="property-grid">';
        for (const [key, val] of Object.entries(data)) {
            if (typeof val === 'object' && val !== null && !Array.isArray(val)) continue; // skip nested for now
            
            // Format arrays slightly nicer
            const displayVal = Array.isArray(val) ? val.length + ' items' : val;

            propsHtml += `
                <div class="property">
                    <span class="label">${key.replace(/_/g, ' ')}</span>
                    <span class="value">${displayVal}</span>
                </div>
            `;
        }
        propsHtml += '</div>';

        return `
            <div class="section">
                <h3>${title}</h3>
                ${propsHtml}
            </div>
        `;
    };

    let html = `<h1>${node.node_name || node.uid}</h1>`;
    
    // Top level info
    html += renderSection('Overview', {
        'Type': node.node_type,
        'UID': node.uid,
        'Architecture': node.architecture?.platform_type
    });

    // Hardware subsections
    if (node.chassis) html += renderSection('Chassis', node.chassis);
    if (node.processor) html += renderSection('Processor', node.processor);
    if (node.main_memory) html += renderSection('Memory', node.main_memory);
    if (node.gpu && node.gpu.gpu) html += renderSection('GPU', node.gpu);

    // Raw JSON fallback/debug
    html += `
        <div class="section">
            <h3>Raw Data</h3>
            <pre>${JSON.stringify(node, null, 2)}</pre>
        </div>
    `;

    container.innerHTML = html;
    content.appendChild(container);
}

// Init
window.addEventListener('DOMContentLoaded', () => {
    navigateTo('sites');
});
