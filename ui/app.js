const API_BASE = '..'; // Relative path from /ui/ to /

// State
const state = {
    path: [], 
    view: 'sites',
    facets: { node_types: [], gpu_models: [] }
};

// DOM Elements
const content = document.getElementById('content');
const breadcrumbs = document.getElementById('breadcrumbs');
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const searchLink = document.getElementById('nav-search');
const browseLink = document.getElementById('nav-browse');

// Router/Navigator
function navigateTo(view, id = null, name = null) {
    state.view = view === 'search' ? 'search' : 'sites';
    updateNavState();

    if (view === 'search') {
        state.path = [{ name: 'Search', view: 'search', id: null }];
        renderSearch();
    } else if (view === 'sites') {
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
         // arguments[3] and [4] might be site_id/cluster_id if coming from search
         const siteId = state.path.find(p => p.view === 'site')?.id || arguments[3]; 
         const clusterId = state.path.find(p => p.view === 'cluster')?.id || arguments[4];
         
         state.path.push({ name: name || id, view: 'node', id: id, siteId, clusterId });
         fetchNodeDetails(siteId, clusterId, id);
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

// Search & filters


async function fetchFacets() {
    try {
        const res = await fetch(`${API_BASE}/nodes/facets`);
        state.facets = await res.json();
    } catch (e) {
        console.error('Failed to fetch facets', e);
    }
}

async function fetchSearchResults(filters) {
    // Determine target container for loading state
    // If first load, might use full page loading. If update, maybe just overlay?
    // For now simple global loading is OK but might be flashy.
    // Let's rely on renderSearchResults to clear empty states.
    
    // We do NOT want to wipe the whole content if we are just re-filtering
    // But current structure wipes content.innerHTML in setLoading.
    // Let's optimize: only show spinner if we don't have results? 
    // Or just overlay a spinner on the results div?
    
    const resultsContainer = document.getElementById('search-results');
    if (resultsContainer) {
        resultsContainer.style.opacity = '0.5';
    }

    try {
        const params = new URLSearchParams();
        if (filters.min_gpu) params.append('min_gpu', filters.min_gpu);
        if (filters.min_ram_gb) params.append('min_ram_gb', filters.min_ram_gb);
        if (filters.architecture) params.append('architecture', filters.architecture);
        if (filters.node_type) params.append('node_type', filters.node_type);
        if (filters.gpu_model) params.append('gpu_model', filters.gpu_model);

        const res = await fetch(`${API_BASE}/nodes?${params.toString()}`);
        const items = await res.json();
        renderSearchResults(items);
    } catch (e) {
        showError(e);
    } finally {
        if (resultsContainer) resultsContainer.style.opacity = '1';
    }
}

let debounceTimer = null;
function debouncedSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        const filters = {
             min_gpu: document.getElementById('filter-gpu')?.value,
             min_ram_gb: document.getElementById('filter-ram')?.value,
             architecture: document.getElementById('filter-arch')?.value,
             node_type: document.getElementById('filter-type')?.value,
             gpu_model: document.getElementById('filter-gpu-model')?.value
        };
        fetchSearchResults(filters);
    }, 300);
}

// UI Helpers

function updateNavState() {
     if (state.view === 'search') {
         searchLink?.classList.add('active');
         browseLink?.classList.remove('active');
     } else {
         searchLink?.classList.remove('active');
         browseLink?.classList.add('active');
     }
}

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


function renderSearch() {
    // Build options
    
    // Node Types
    const typeOpts = state.facets.node_types.map(t => `<option value="${t}">${t}</option>`).join('');
    
    // GPU Models
    const gpuOpts = state.facets.gpu_models.map(m => `<option value="${m}">${m}</option>`).join('');

    content.innerHTML = `
        <div class="search-container">
            <div class="filters">
                 <div class="form-group">
                    <label>Min GPUs</label>
                    <input type="number" id="filter-gpu" min="0" placeholder="e.g. 1" oninput="debouncedSearch()">
                 </div>
                 <div class="form-group">
                    <label>Min RAM (GiB)</label>
                    <input type="number" id="filter-ram" min="0" placeholder="e.g. 128" oninput="debouncedSearch()">
                 </div>
                 <div class="form-group">
                    <label>Architecture</label>
                    <select id="filter-arch" onchange="debouncedSearch()">
                        <option value="">Any</option>
                        <option value="x86_64">x86_64</option>
                        <option value="arm64">arm64</option>
                    </select>
                 </div>
                 <div class="form-group">
                    <label>Node Type</label>
                    <select id="filter-type" onchange="debouncedSearch()">
                        <option value="">Any</option>
                        ${typeOpts}
                    </select>
                 </div>
                 <div class="form-group">
                    <label>GPU Model</label>
                    <select id="filter-gpu-model" onchange="debouncedSearch()">
                        <option value="">Any</option>
                        ${gpuOpts}
                    </select>
                 </div>
            </div>
            <div id="search-results">
                 <!-- Auto loaded -->
            </div>
        </div>
    `;

    // Trigger initial search
    debouncedSearch();
}

function renderSearchResults(nodes) {
    const container = document.getElementById('search-results');
    if (!container) return; 
    
    if (!nodes || nodes.length === 0) {
        container.innerHTML = '<div class="empty-state">No nodes found matching criteria.</div>';
        return;
    }

    // Group by Site
    const bySite = {};
    nodes.forEach(n => {
        const site = n.site_id || 'Unknown';
        if (!bySite[site]) bySite[site] = [];
        bySite[site].push(n);
    });

    let html = `<div class="results-header">Found ${nodes.length} nodes across ${Object.keys(bySite).length} sites.</div>`;

    for (const [site, siteNodes] of Object.entries(bySite)) {
        html += `
            <div class="site-group">
                <h3>Site: ${site} <span class="badge">${siteNodes.length}</span></h3>
                <div class="grid">
        `;
        
        siteNodes.forEach(node => {
            // Re-use card style but minimal
            html += `
                <div class="card mini-card" onclick="navigateTo('node', '${node.uid}', '', '${node.site_id}', '${node.cluster_id}')">
                    <h4>${node.node_name || node.uid}</h4>
                    <p>${node.node_type}</p>
                    <div class="mini-stats">
                        <span>${node.gpu && node.gpu.gpu ? (node.gpu.gpu_count || 1) + ' GPU' : 'No GPU'}</span>
                        <span>${node.architecture?.platform_type || ''}</span>
                    </div>
                </div>
            `;
        });

        html += `
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
    
    // Patch navigateTo to handle jumping to node details from search where we iterate context
    // Actually, navigateTo takes (view, id, name). WE need site_id and cluster_id for fetchNodeDetails.
    // Let's attach them to the card click logic directly above using a modified call, or changing navigateTo signature.
    // See modified card click handler above.
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
window.addEventListener('DOMContentLoaded', async () => {
    // Add event listeners for new nav if created in index.html, handled in navigateTo
    if (searchLink) searchLink.onclick = (e) => { e.preventDefault(); navigateTo('search'); };
    if (browseLink) browseLink.onclick = (e) => { e.preventDefault(); navigateTo('sites'); };

    // Prefetch facets for search experience
    fetchFacets();

    navigateTo('sites');
});
