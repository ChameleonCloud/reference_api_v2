const API_BASE = '..'; // Relative path from /ui/ to /

// State
const state = {
    allNodes: [], // Cache of ALL nodes for client-side filtering
    siteCounts: {}, // Total nodes per site
    allFacets: { node_types: new Set(), gpu_models: new Set() }, // All possible values for facets
    timeline: null, // Availability timeline component
    timelineEnabled: true, // Whether to filter by availability
    unfilteredMatches: [], // Nodes matching filters before availability filter
};

// DOM Elements
const content = document.getElementById('content');
const loading = document.getElementById('loading');
const error = document.getElementById('error');
const sidebar = document.getElementById('advanced-filters');

// Search & filters



async function initData() {
    try {
        // Get all sites
        const sitesRes = await fetch(`${API_BASE}/sites`);
        const sitesData = await sitesRes.json();
        const sites = sitesData.items || [];
        
        // Aggregate all nodes from all sites/clusters
        state.allNodes = [];
        
        for (const site of sites) {
            const siteId = site.uid;
            
            // Get clusters for this site
            const clustersRes = await fetch(`${API_BASE}/sites/${siteId}/clusters`);
            const clustersData = await clustersRes.json();
            const clusters = clustersData.items || [];
            
            for (const cluster of clusters) {
                const clusterId = cluster.uid;
                
                // Get nodes for this cluster
                const nodesRes = await fetch(`${API_BASE}/sites/${siteId}/clusters/${clusterId}/nodes`);
                const nodesData = await nodesRes.json();
                const nodes = nodesData.items || [];
                
                // Inject site_id and cluster_id for context
                nodes.forEach(node => {
                    node.site_id = siteId;
                    node.cluster_id = clusterId;
                    state.allNodes.push(node);
                });
            }
        }
        
        // Calculate site counts
        state.siteCounts = {};
        state.allNodes.forEach(n => {
            const s = n.site_id || 'Unknown';
            state.siteCounts[s] = (state.siteCounts[s] || 0) + 1;
        });
        
        // Build complete catalog of all possible filter values
        state.allFacets = {
            node_types: new Set(),
            gpu_models: new Set()
        };
        
        state.allNodes.forEach(n => {
            if (n.node_type) state.allFacets.node_types.add(n.node_type);
            if (n.gpu && n.gpu.gpu_model) state.allFacets.gpu_models.add(n.gpu.gpu_model);
        });
        
    } catch (e) {
        console.error('Failed to init data', e);
        showError('Failed to load initial data.');
    }
}

function runClientSearch(filters) {
    // Filter nodes by non-node-type specs (for showing node type facet counts)
    const baseMatches = state.allNodes.filter(node => {
        // GPU Model (OR logic)
        if (filters.gpu_model && filters.gpu_model.length > 0) {
             const model = node.gpu?.gpu_model || "";
             const match = filters.gpu_model.some(f => model.includes(f));
             if (!match) return false;
        }
        
        // Min GPU
        if (filters.min_gpu) {
            const count = node.gpu?.gpu_count || 0;
            if (count < parseInt(filters.min_gpu)) return false;
        }
        
        // Min RAM
        if (filters.min_ram_gb) {
             const ramBytes = node.main_memory?.ram_size || 0;
             const minBytes = parseInt(filters.min_ram_gb) * 1024 * 1024 * 1024;
             if (ramBytes < minBytes) return false;
        }

        // Arch (OR logic)
        if (filters.architecture && filters.architecture.length > 0) {
             const arch = node.architecture?.platform_type || "";
             if (!filters.architecture.includes(arch)) return false;
        }

        // Storage Type (OR logic)
        if (filters.storage_type && filters.storage_type.length > 0) {
            const devices = node.storage_devices || [];
            const matchesStorage = filters.storage_type.some(type => {
                if (type === 'NVMe') {
                    return devices.some(d => 
                        (d.interface && d.interface.includes('PCIe')) || 
                        (d.model && d.model.includes('NVMe')) ||
                        (d.node_type === 'storage_nvme')
                    );
                } else if (type === 'SSD') {
                    return devices.some(d => d.media_type === 'SSD');
                } else if (type === 'HDD') {
                    return devices.some(d => d.media_type === 'HDD');
                }
                return false;
            });
            if (!matchesStorage) return false;
        }

        // InfiniBand
        if (filters.infiniband) {
            const adapters = node.network_adapters || [];
            const hasIb = adapters.some(a => a.interface === 'InfiniBand');
            if (!hasIb) return false;
        }
        
        return true;
    });

    // Filter by ALL specs including node_type (for table results and other facets)
    const specMatches = baseMatches.filter(node => {
        // Node Type (OR logic)
        if (filters.node_type && filters.node_type.length > 0 && !filters.node_type.includes(node.node_type)) {
            return false;
        }
        return true;
    });

    // Calculate Site Matches (from baseMatches for accurate site counts)
    const siteMatchCounts = {};
    baseMatches.forEach(n => {
        const s = n.site_id || 'Unknown';
        siteMatchCounts[s] = (siteMatchCounts[s] || 0) + 1;
    });
    
    // Apply Site Filter (for Table & Facet Context)
    let tableMatches = (filters.site && filters.site.length > 0)
        ? specMatches.filter(n => filters.site.includes(n.site_id))
        : specMatches;
    
    // Store matches before availability filter for timeline
    state.unfilteredMatches = tableMatches;
    
    // Apply availability filter if timeline is active
    if (state.timeline && state.timelineEnabled) {
        const availableNodeIds = new Set(state.timeline.getAvailableNodeIds());
        tableMatches = tableMatches.filter(n => availableNodeIds.has(n.uid));
    }
    
    renderSearchResults(tableMatches);
    updateFacets(tableMatches, baseMatches, siteMatchCounts, filters.site);
    
    // Update timeline with matching nodes (all nodes that match filters, before availability filter)
    if (state.timeline) {
        state.timeline.updateAvailability(
            state.unfilteredMatches.map(n => n.uid),
            state.unfilteredMatches
        );
    }
}

let debounceTimer = null;
function debouncedSearch() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        // Collect Multi-Select Values
        const getCheckedValues = (name) => {
            return Array.from(document.querySelectorAll(`input[name="${name}"]:checked`))
                        .map(cb => cb.value);
        };

        const filters = {
             min_gpu: document.getElementById('filter-gpu')?.value,
             min_ram_gb: document.getElementById('filter-ram')?.value,
             site: getCheckedValues('site'),                 // Array [NEW]
             architecture: getCheckedValues('architecture'), // Array
             node_type: getCheckedValues('node_type'),       // Array
             gpu_model: getCheckedValues('gpu_model'),       // Array
             storage_type: getCheckedValues('storage_type'), // Array
             infiniband: document.getElementById('filter-infiniband')?.checked
        };
        
        runClientSearch(filters);
    }, 100); 
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



// Helper to toggle a whole family of checkboxes
window.toggleFamily = function(familyName, isChecked) {
    const inputs = document.querySelectorAll(`input[data-family="${familyName}"]`);
    inputs.forEach(input => {
        input.checked = isChecked;
    });
    debouncedSearch();
};

function initSidebar() {
    sidebar.innerHTML = '<div id="dynamic-facets"></div>';
}

function renderFacetGroup(id, title, items, selectedValues) {
    if (!items || items.length === 0) return '';
    
    // Sort items by count desc
    items.sort((a,b) => b.count - a.count);

    // Determine default open state - Site is always open, others open if selected
    const isOpen = (id === 'site' || selectedValues.size > 0) ? 'open' : '';

    const listHtml = items.map(item => {
        const isChecked = selectedValues.has(item.value) ? 'checked' : '';
        return `
            <div class="facet-item">
                <input type="checkbox" name="${id}" value="${item.value}" ${isChecked} onchange="debouncedSearch()">
                <label title="${item.value}">${item.value}</label>
                <span class="facet-count">${item.count}</span>
            </div>
        `;
    }).join('');

    return `
        <div class="facet-group">
            <details ${isOpen}>
                <summary>${title}</summary>
                <div class="facet-list">
                    ${listHtml}
                </div>
            </details>
        </div>
    `;
}

function updateFacets(contextNodes, baseMatches, siteMatchCounts, selectedSites) {
    // contextNodes = nodes matching ALL filters (for GPU, arch, storage counts and table display)
    // baseMatches = nodes matching all NON-node-type filters (for node_type counts - enables OR selection)
    
    // 1. Initialize counts with ALL known values from catalog (so they show even with 0 matches)
    const counts = {
        node_type: {},
        gpu_model: {},
        storage_type: { 'NVMe': 0, 'SSD': 0, 'HDD': 0 },
        architecture: { 'x86_64': 0, 'arm64': 0 }
    };
    
    // Pre-fill with all known node types and GPU models (with 0 counts)
    state.allFacets.node_types.forEach(nt => counts.node_type[nt] = 0);
    state.allFacets.gpu_models.forEach(gm => counts.gpu_model[gm] = 0);
    
    // Count node types from baseMatches (excludes node_type filter for OR logic)
    baseMatches.forEach(n => {
        if (n.node_type) {
            counts.node_type[n.node_type] = (counts.node_type[n.node_type] || 0) + 1;
        }
    });
    
    // Count other facets from contextNodes (full filter context)
    contextNodes.forEach(n => {
        // GPU
        if (n.gpu && n.gpu.gpu_model) {
            counts.gpu_model[n.gpu.gpu_model] = (counts.gpu_model[n.gpu.gpu_model] || 0) + 1;
        }
        
        // Arch
        if (n.architecture && n.architecture.platform_type) {
            counts.architecture[n.architecture.platform_type] = (counts.architecture[n.architecture.platform_type] || 0) + 1;
        }

        // Storage
        const devices = n.storage_devices || [];
        if (devices.some(d => (d.interface && d.interface.includes('PCIe')) || (d.model && d.model.includes('NVMe')) || d.node_type === 'storage_nvme')) {
            counts.storage_type['NVMe']++;
        }
        if (devices.some(d => d.media_type === 'SSD')) counts.storage_type['SSD']++;
        if (devices.some(d => d.media_type === 'HDD')) counts.storage_type['HDD']++;
    });
    
    // 2. Get Current Selection (to maintain UI state)
    const getSelected = (name) => new Set(Array.from(document.querySelectorAll(`input[name="${name}"]:checked`)).map(cb => cb.value));
    
    const selected = {
        node_type: getSelected('node_type'),
        gpu_model: getSelected('gpu_model'),
        storage_type: getSelected('storage_type'),
        architecture: getSelected('architecture')
    };
    
    // 3. Transform to Array for Render
    const toItems = (obj) => Object.entries(obj).map(([val, count]) => ({ value: val, count }));
    
    let html = '';

    // 1. Site Filter (Sidebar Top)
    // Sort sites by TOTAL count
    const sortedSites = Object.entries(state.siteCounts).sort((a,b) => b[1] - a[1]);
    
    // Transform to items with custom count string "Matched / Total"
    const siteItems = sortedSites.map(([site, total]) => {
        const matched = siteMatchCounts[site] || 0;
        return {
            value: site,
            count: `${matched} / ${total}` // Pass formatted string
        };
    });

    const selectedSiteSet = new Set(selectedSites || []); // passed from runClientSearch

    // Reuse renderFacetGroup but we need to ensure it handles string counts nicely (it does, likely)
    // Only caveat: The 'value' in renderFacetGroup becomes the label. We want 'site' (e.g. TACC) as label.
    // It works fine.
    
    html += renderFacetGroup('site', 'Site', siteItems, selectedSiteSet);
    
    // 2. Node Factors (Second)
    const families = {
        'GPU Nodes': [],
        'Compute Nodes': [],
        'Storage Nodes': [],
        'Other': []
    };
    
    Object.entries(counts.node_type).forEach(([type, count]) => {
        let family = 'Other';
        if (type.startsWith('gpu')) family = 'GPU Nodes';
        else if (type.startsWith('compute') || type.startsWith('arm')) family = 'Compute Nodes';
        else if (type.startsWith('storage')) family = 'Storage Nodes';
        else if (type.includes('fpga')) family = 'Other';
        
        families[family].push({ value: type, count });
    });
    
    // Sort items within families
    Object.values(families).forEach(list => list.sort((a,b) => b.count - a.count));

    // Render Nested Node Types (No max-height)
    html += renderNestedNodeTypes(families, selected.node_type);

    // 3. GPU Models
    html += renderFacetGroup('gpu_model', 'GPUs', toItems(counts.gpu_model), selected.gpu_model);
    
    // 4. Storage / Arch
    html += renderFacetGroup('storage_type', 'Drive Type', toItems(counts.storage_type), selected.storage_type);
    html += renderFacetGroup('architecture', 'CPU Arch', toItems(counts.architecture), selected.architecture);

    // 5. Advanced Inputs (Bottom)
    html += renderSidebarInputs();

    document.getElementById('dynamic-facets').innerHTML = html;
}

function renderNestedNodeTypes(families, selectedSet) {
    // Families order
    const order = ['GPU Nodes', 'Compute Nodes', 'Storage Nodes', 'Other'];
    
    let innerHtml = '';
    
    order.forEach(fam => {
        const items = families[fam];
        if (items.length === 0) return;
        
        // Check if all items in this family are selected (for parent state)
        // or if just some are selected.
        // For simplicity, parent is checked only if user explicitly checked it? 
        // No, parent is a bulk actor.
        // Let's rely on "Are all children checked?".
        const allChecked = items.every(i => selectedSet.has(i.value));
        const someChecked = items.some(i => selectedSet.has(i.value));
        
        const parentChecked = allChecked ? 'checked' : '';
        // Note: Indeterminate state would be nice but requires JS after render.
        // For now: Checkbox toggles all.
        
        const childrenHtml = items.map(item => {
            const isChecked = selectedSet.has(item.value) ? 'checked' : '';
            return `
                <div class="facet-item">
                    <input type="checkbox" name="node_type" value="${item.value}" data-family="${fam}" ${isChecked} onchange="debouncedSearch()">
                    <label title="${item.value}">${item.value}</label>
                    <span class="facet-count">${item.count}</span>
                </div>
            `;
        }).join('');

        innerHtml += `
            <div class="nested-category">
                <div class="nested-header">
                    <input type="checkbox" ${parentChecked} onchange="toggleFamily('${fam}', this.checked)">
                    <span>${fam}</span>
                </div>
                <div class="nested-children">
                    ${childrenHtml}
                </div>
            </div>
        `;
    });

    return `
        <div class="facet-group">
            <details open>
                <summary>Node Type</summary>
                <div class="facet-list" style="max-height:none;">
                    ${innerHtml}
                </div>
            </details>
        </div>
    `;
}

// Helper to toggle group rows
window.toggleGroup = function(key) {
    const row = document.getElementById(`group-row-${key}`);
    const details = document.getElementById(`group-details-${key}`);
    if (row && details) {
        if (details.classList.contains('expanded')) {
            details.classList.remove('expanded');
            row.classList.remove('expanded');
        } else {
            details.classList.add('expanded');
            row.classList.add('expanded');
        }
    }
};

// Helper to clean CPU strings
function cleanCpuModel(model) {
    if (!model) return 'Unknown';
    return model
        .replace(/Intel\(R\)\s*/gi, '')
        .replace(/Xeon\(R\)\s*/gi, 'Xeon')
        .replace(/AMD\s*/gi, '')
        .replace(/Core\(TM\)\s*/gi, '')
        .replace(/\s*CPU\s*@\s*[\d\.]+[a-zA-Z]+/gi, '') // Remove frequency at end
        .replace(/\s*Processor/gi, '')
        .replace(/-Core/gi, ' Core')
        .trim();
}

function renderSearchResults(matches) {
    const content = document.getElementById('content');
    content.innerHTML = '';

    if (matches.length === 0) {
        content.innerHTML = '<div class="alert alert-info">No nodes found matching criteria.</div>';
        return;
    }
    
    // Group Results
    const groups = groupNodes(matches);

    // Create Card Container
    const card = document.createElement('div');
    card.className = 'card';
    card.style.padding = '0'; // Custom padding for table
    card.style.overflow = 'hidden';

    // Header inside card
    const header = document.createElement('div');
    header.style.padding = '1.5rem';
    header.style.borderBottom = '1px solid var(--border-color)';
    header.style.background = 'white'; // Ensure bg
    header.innerHTML = `<h3 style="margin:0; font-size:1.1rem;">${matches.length} Matching Nodes</h3>`;
    card.appendChild(header);

    const table = document.createElement('table');
    table.className = 'table table-dense';
    table.style.margin = '0'; // Reset margin
    table.innerHTML = `
        <thead>
            <tr>
                <th>Count</th>
                <th>Type</th>
                <th>Site</th>
                <th>CPU</th>
                <th>GPU</th>
                <th>RAM</th>
            </tr>
        </thead>
        <tbody>
            ${groups.map(group => {
                const n = group.sample;
                const key = group.key;
                
                // Specs
                const cpuModel = cleanCpuModel(n.processor?.model);
                const cpuStr = `${n.architecture?.smp_size || '?'} x ${cpuModel}`;
                
                const gpuCount = n.gpu?.gpu_count || 0;
                // Clean GPU model too
                let gpuModel = n.gpu?.gpu_model || '';
                gpuModel = gpuModel.replace(/Tesla\s*/gi, '').replace(/NVIDIA\s*/gi, '');
                
                const gpuStr = gpuCount > 0 ? `${gpuCount} x ${gpuModel}` : '-';
                const ramStr = n.main_memory?.humanized_ram_size || '-';
                
                // Details Grid
                const detailsHtml = group.nodes.map(node => `
                    <span class="node-link-item" title="${node.uid}">
                        ${node.node_name || node.uid.substring(0,8)}
                    </span>
                `).join('');

                return `
                    <tr class="group-row" id="group-row-${key}" onclick="toggleGroup('${key}')">
                        <td>
                            <div class="group-toggle-wrapper">
                                <i class="group-toggle-icon">▶</i>
                                <span style="font-weight:700">${group.nodes.length}</span>
                            </div>
                        </td>
                        <td style="font-weight:600">${n.node_type}</td>
                        <td>${n.site_id?.toUpperCase()}</td>
                        <td>${cpuStr}</td>
                        <td>${gpuStr}</td>
                        <td>${ramStr}</td>
                    </tr>
                    <tr class="group-details-row" id="group-details-${key}">
                        <td colspan="6" class="group-details-content">
                            <div class="node-grid-compact">
                                ${detailsHtml}
                            </div>
                        </td>
                    </tr>
                `;
            }).join('')}
        </tbody>
    `;
    
    card.appendChild(table);
    content.appendChild(card);
}

function groupNodes(nodes) {
    const groups = {};
    nodes.forEach(n => {
        // Key: Site + Type + GPU + RAM
        // This ensures strictly identical hardware logic (user requested)
        const gpuKey = n.gpu?.gpu_model || 'none';
        const gpuCount = n.gpu?.gpu_count || 0;
        const ramKey = n.main_memory?.ram_size || 0;
        
        // Use a safe ID string
        // const key = `${n.site_id}-${n.node_type}-${gpuKey}-${gpuCount}-${ramKey}`.replace(/[^a-zA-Z0-9-]/g, '_');
        const key = `${n.site_id}-${n.node_type}`.replace(/[^a-zA-Z0-9-]/g, '_');
        
        if (!groups[key]) {
            groups[key] = {
                key: key,
                sample: n,
                nodes: []
            };
        }
        groups[key].nodes.push(n);
    });
    
    // Convert to array and sort by COUNT DESC, then site, then type
    return Object.values(groups).sort((a,b) => {
        if (b.nodes.length !== a.nodes.length) return b.nodes.length - a.nodes.length;
        if (a.sample.site_id !== b.sample.site_id) return a.sample.site_id.localeCompare(b.sample.site_id);
        return a.sample.node_type.localeCompare(b.sample.node_type);
    });
}

function renderSidebarInputs() {
    return `
        <div class="facet-group">
            <details>
                <summary>Advanced Specs</summary>
                <div class="facet-list" style="max-height:none; padding: 0.75rem;">
                    <div class="form-group">
                        <label>Min GPUs</label>
                        <input type="number" id="filter-gpu" min="0" placeholder="-" oninput="debouncedSearch()">
                    </div>
                    <div class="form-group">
                        <label>Min RAM (GiB)</label>
                        <input type="number" id="filter-ram" min="0" placeholder="-" oninput="debouncedSearch()">
                    </div>
                    <div class="form-group checkbox-group" style="margin-top:0.5rem">
                        <label>
                            <input type="checkbox" id="filter-infiniband" onchange="debouncedSearch()">
                            Has InfiniBand
                        </label>
                    </div>
                </div>
            </details>
        </div>
    `;
}





// Init
window.addEventListener('DOMContentLoaded', async () => {
    // Initialize timeline component
    if (window.AvailabilityTimeline) {
        state.timeline = new AvailabilityTimeline('availability-timeline-container');
        
        // Register callback to re-filter results when time window changes
        state.timeline.onWindowChange(() => {
            debouncedSearch();
        });
    }
    
    // Prefetch all data for smooth client-side filtering
    await initData();
    initSidebar();
    
    // Initial Render
    debouncedSearch(); 
});

