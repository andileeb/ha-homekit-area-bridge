'use strict';

// ── State ──────────────────────────────────────────────────────────
const state = {
    areas: [],              // AreaSummary[] from /api/areas
    areaEntities: {},       // area_id -> { entities_by_domain }
    config: {},             // area_id -> AreaConfig
    yamlPreview: null,      // string
    yamlWarnings: [],       // string[]
    yamlBridges: [],        // BridgeConfig[]
};

// ── API helpers ────────────────────────────────────────────────────
async function api(method, path, body) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) {
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch(path, opts);
    if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`API ${method} ${path}: ${resp.status} ${text}`);
    }
    return resp.json();
}

// ── Toast notifications ────────────────────────────────────────────
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ── Data loading ───────────────────────────────────────────────────
async function loadAreas() {
    const areas = await api('GET', 'api/areas');
    state.areas = areas;

    // Initialize config for new areas
    for (const area of areas) {
        if (!state.config[area.area_id]) {
            state.config[area.area_id] = {
                area_id: area.area_id,
                enabled: false,
                bridge_name: `${area.name} Bridge`,
                mode: 'all_domains',
                include_domains: [],
                include_entities: [],
                exclude_entities: [],
            };
        }
    }
}

async function loadAreaEntities(areaId) {
    if (state.areaEntities[areaId]) return;
    const data = await api('GET', `api/areas/${areaId}/entities`);
    state.areaEntities[areaId] = data.entities_by_domain;
}

async function loadSavedConfig() {
    try {
        const data = await api('GET', 'api/config');
        if (data.areas) {
            for (const [areaId, config] of Object.entries(data.areas)) {
                state.config[areaId] = config;
            }
        }
    } catch (e) {
        // No saved config yet, that's fine
    }
}

async function saveConfig() {
    try {
        await api('POST', 'api/config', { areas: state.config });
    } catch (e) {
        console.error('Failed to save config:', e);
    }
}

// ── Rendering ──────────────────────────────────────────────────────
function renderAreaList() {
    const container = document.getElementById('area-list');
    if (!state.areas.length) {
        container.innerHTML = '<p style="text-align:center;color:#757575;padding:40px">No areas found in Home Assistant.</p>';
        return;
    }

    container.innerHTML = state.areas.map(area => {
        const config = state.config[area.area_id] || {};
        const enabled = config.enabled || false;
        const domainSummary = Object.entries(area.domain_counts || {})
            .map(([d, c]) => `${c} ${d}`)
            .join(', ');

        return `
        <div class="area-card ${enabled ? '' : 'disabled-area'}" data-area-id="${area.area_id}">
            <div class="area-header" onclick="toggleAreaExpand('${area.area_id}')">
                <label class="toggle area-toggle" onclick="event.stopPropagation()">
                    <input type="checkbox" ${enabled ? 'checked' : ''}
                           onchange="toggleAreaEnabled('${area.area_id}', this.checked)">
                    <span class="slider"></span>
                </label>
                <span class="area-name">${escHtml(area.name)}</span>
                <span class="area-stats">
                    <span class="badge">${area.homekit_entity_count} HomeKit</span>
                    <span>${area.entity_count} total</span>
                </span>
                <span class="area-chevron">&#9660;</span>
            </div>
            <div class="area-detail" id="detail-${area.area_id}"></div>
        </div>`;
    }).join('');
}

async function toggleAreaExpand(areaId) {
    const card = document.querySelector(`.area-card[data-area-id="${areaId}"]`);
    const isExpanded = card.classList.contains('expanded');

    if (isExpanded) {
        card.classList.remove('expanded');
        return;
    }

    // Load entities if needed
    try {
        await loadAreaEntities(areaId);
    } catch (e) {
        showToast('Failed to load entities: ' + e.message, 'error');
        return;
    }

    card.classList.add('expanded');
    renderAreaDetail(areaId);
}

function renderAreaDetail(areaId) {
    const container = document.getElementById(`detail-${areaId}`);
    const config = state.config[areaId] || {};
    const entitiesByDomain = state.areaEntities[areaId] || {};
    const area = state.areas.find(a => a.area_id === areaId);

    // Collect all domains present
    const domains = Object.keys(entitiesByDomain).sort();
    const mode = config.mode || 'all_domains';

    container.innerHTML = `
        <div class="form-group" style="margin-top:12px">
            <label>Bridge Name</label>
            <input type="text" value="${escAttr(config.bridge_name || (area.name + ' Bridge'))}"
                   onchange="updateConfig('${areaId}', 'bridge_name', this.value)"
                   maxlength="25" placeholder="Bridge name...">
        </div>

        <div class="form-group">
            <label>Entity Selection Mode</label>
            <div class="mode-selector">
                <button class="mode-btn ${mode === 'all_domains' ? 'active' : ''}"
                        onclick="setMode('${areaId}', 'all_domains')">All Supported</button>
                <button class="mode-btn ${mode === 'selected_domains' ? 'active' : ''}"
                        onclick="setMode('${areaId}', 'selected_domains')">Select Domains</button>
                <button class="mode-btn ${mode === 'manual' ? 'active' : ''}"
                        onclick="setMode('${areaId}', 'manual')">Manual</button>
            </div>
        </div>

        ${mode === 'selected_domains' ? renderDomainSelector(areaId, domains, entitiesByDomain) : ''}
        ${mode === 'manual' ? renderEntitySelector(areaId, domains, entitiesByDomain) : ''}

        <details class="exclude-section">
            <summary>Exclude specific entities (${config.exclude_entities?.length || 0} excluded)</summary>
            ${renderExcludeList(areaId, domains, entitiesByDomain)}
        </details>
    `;
}

function renderDomainSelector(areaId, domains, entitiesByDomain) {
    const config = state.config[areaId] || {};
    const selected = new Set(config.include_domains || []);

    return `
        <div class="form-group">
            <label>Domains</label>
            <div class="domain-list">
                ${domains.map(domain => {
                    const entities = entitiesByDomain[domain] || [];
                    const supported = entities.filter(e => e.homekit_supported && !e.disabled && !e.hidden && !e.entity_category);
                    if (!supported.length) return '';
                    return `
                    <div class="domain-chip ${selected.has(domain) ? 'selected' : ''}"
                         onclick="toggleDomain('${areaId}', '${domain}')">
                        <span>${domain}</span>
                        <span class="count">(${supported.length})</span>
                    </div>`;
                }).join('')}
            </div>
        </div>`;
}

function renderEntitySelector(areaId, domains, entitiesByDomain) {
    const config = state.config[areaId] || {};
    const included = new Set(config.include_entities || []);

    return `
        <div class="form-group">
            <label>Entities</label>
            <input type="text" class="entity-search" placeholder="Search entities..."
                   oninput="filterEntities('${areaId}', this.value)">
            <div class="entity-list" id="entity-list-${areaId}">
                ${domains.map(domain => {
                    const entities = (entitiesByDomain[domain] || [])
                        .filter(e => e.homekit_supported && !e.disabled && !e.hidden && !e.entity_category);
                    if (!entities.length) return '';
                    return `
                    <div class="entity-domain-group" data-domain="${domain}">
                        <h4>${domain} (${entities.length})</h4>
                        ${entities.map(e => `
                        <div class="entity-item" data-entity-id="${e.entity_id}">
                            <input type="checkbox" ${included.has(e.entity_id) ? 'checked' : ''}
                                   onchange="toggleEntity('${areaId}', '${e.entity_id}', this.checked)">
                            <span>${escHtml(e.name)}</span>
                            <span class="entity-id">${e.entity_id}</span>
                        </div>`).join('')}
                    </div>`;
                }).join('')}
            </div>
        </div>`;
}

function renderExcludeList(areaId, domains, entitiesByDomain) {
    const config = state.config[areaId] || {};
    const excluded = new Set(config.exclude_entities || []);

    let html = '<div class="entity-list" style="margin-top:8px">';
    for (const domain of domains) {
        const entities = (entitiesByDomain[domain] || [])
            .filter(e => e.homekit_supported && !e.disabled && !e.hidden && !e.entity_category);
        if (!entities.length) continue;

        html += `<div class="entity-domain-group"><h4>${domain}</h4>`;
        for (const e of entities) {
            html += `
            <div class="entity-item">
                <input type="checkbox" ${excluded.has(e.entity_id) ? 'checked' : ''}
                       onchange="toggleExclude('${areaId}', '${e.entity_id}', this.checked)">
                <span>${escHtml(e.name)}</span>
                <span class="entity-id">${e.entity_id}</span>
            </div>`;
        }
        html += '</div>';
    }
    html += '</div>';
    return html;
}

function renderYamlPreview() {
    const container = document.getElementById('yaml-preview');
    if (!state.yamlPreview) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');

    let warningsHtml = '';
    if (state.yamlWarnings.length) {
        warningsHtml = '<div class="warnings">' +
            state.yamlWarnings.map(w => `<div class="warning-item">&#9888; ${escHtml(w)}</div>`).join('') +
            '</div>';
    }

    const bridgeCount = state.yamlBridges.length;
    const totalEntities = Object.values(state.yamlPreview.entity_count_per_bridge || {})
        .reduce((sum, n) => sum + n, 0);

    container.innerHTML = `
        ${warningsHtml}
        <div class="yaml-container">
            <div class="yaml-header">
                <h3>Generated YAML — ${bridgeCount} bridge${bridgeCount !== 1 ? 's' : ''}, ${totalEntities} entities</h3>
            </div>
            <div class="yaml-content">${escHtml(state.yamlPreview.yaml_content)}</div>
        </div>`;

    document.getElementById('btn-apply').disabled = false;
}

// ── Event handlers ─────────────────────────────────────────────────
function toggleAreaEnabled(areaId, enabled) {
    state.config[areaId] = state.config[areaId] || {};
    state.config[areaId].enabled = enabled;

    const card = document.querySelector(`.area-card[data-area-id="${areaId}"]`);
    card.classList.toggle('disabled-area', !enabled);

    saveConfig();
    clearPreview();
}

function setMode(areaId, mode) {
    state.config[areaId].mode = mode;
    renderAreaDetail(areaId);
    saveConfig();
    clearPreview();
}

function updateConfig(areaId, key, value) {
    state.config[areaId][key] = value;
    saveConfig();
    clearPreview();
}

function toggleDomain(areaId, domain) {
    const config = state.config[areaId];
    const domains = new Set(config.include_domains || []);
    if (domains.has(domain)) {
        domains.delete(domain);
    } else {
        domains.add(domain);
    }
    config.include_domains = [...domains];
    renderAreaDetail(areaId);
    saveConfig();
    clearPreview();
}

function toggleEntity(areaId, entityId, checked) {
    const config = state.config[areaId];
    const entities = new Set(config.include_entities || []);
    if (checked) {
        entities.add(entityId);
    } else {
        entities.delete(entityId);
    }
    config.include_entities = [...entities];
    saveConfig();
    clearPreview();
}

function toggleExclude(areaId, entityId, checked) {
    const config = state.config[areaId];
    const excluded = new Set(config.exclude_entities || []);
    if (checked) {
        excluded.add(entityId);
    } else {
        excluded.delete(entityId);
    }
    config.exclude_entities = [...excluded];
    saveConfig();
    clearPreview();
}

function filterEntities(areaId, query) {
    const list = document.getElementById(`entity-list-${areaId}`);
    if (!list) return;
    const q = query.toLowerCase();
    for (const item of list.querySelectorAll('.entity-item')) {
        const id = item.dataset.entityId || '';
        const name = item.textContent.toLowerCase();
        item.style.display = (!q || name.includes(q) || id.includes(q)) ? '' : 'none';
    }
}

function toggleAllAreas() {
    const allEnabled = state.areas.every(a => state.config[a.area_id]?.enabled);
    const newState = !allEnabled;
    for (const area of state.areas) {
        if (state.config[area.area_id]) {
            state.config[area.area_id].enabled = newState;
        }
    }
    renderAreaList();
    updateToggleAllLabel();
    saveConfig();
    clearPreview();
}

async function applyMinimalConfig() {
    const btn = document.getElementById('btn-minimal');
    btn.disabled = true;
    btn.textContent = 'Loading...';

    try {
        // Load entities for all areas in parallel
        await Promise.all(state.areas.map(a => loadAreaEntities(a.area_id)));

        for (const area of state.areas) {
            const config = state.config[area.area_id];
            if (!config) continue;

            config.enabled = true;
            config.mode = 'manual';

            // Pick the first eligible entity
            const domains = state.areaEntities[area.area_id] || {};
            let picked = null;
            for (const domain of Object.keys(domains).sort()) {
                const entities = domains[domain] || [];
                const eligible = entities.find(e =>
                    e.homekit_supported && !e.disabled && !e.hidden && !e.entity_category
                );
                if (eligible) {
                    picked = eligible.entity_id;
                    break;
                }
            }
            config.include_entities = picked ? [picked] : [];
            config.exclude_entities = [];
        }

        renderAreaList();
        updateToggleAllLabel();
        saveConfig();
        clearPreview();
        showToast('Minimal config applied — 1 entity per bridge', 'success');
    } catch (e) {
        showToast('Failed to apply minimal config: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Minimal Config';
    }
}

function updateToggleAllLabel() {
    const btn = document.getElementById('btn-toggle-all');
    if (!btn) return;
    const allEnabled = state.areas.every(a => state.config[a.area_id]?.enabled);
    btn.textContent = allEnabled ? 'Disable All' : 'Enable All';
}

function clearPreview() {
    state.yamlPreview = null;
    state.yamlWarnings = [];
    state.yamlBridges = [];
    document.getElementById('yaml-preview').classList.add('hidden');
    document.getElementById('btn-apply').disabled = true;
}

// ── Button actions ─────────────────────────────────────────────────
async function onGenerate() {
    const btn = document.getElementById('btn-generate');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        const result = await api('POST', 'api/generate', { areas: state.config });
        state.yamlPreview = result;
        state.yamlWarnings = result.warnings || [];
        state.yamlBridges = result.bridges || [];

        if (!result.bridges.length) {
            showToast('No bridges to generate. Enable at least one area with entities.', 'info');
            clearPreview();
        } else {
            renderYamlPreview();
            showToast(`Generated ${result.bridges.length} bridge(s)`, 'success');
        }
    } catch (e) {
        showToast('Generation failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Preview YAML';
    }
}

function showResultOverlay(data) {
    const bridges = data.bridges || [];
    const entityCounts = data.entity_count_per_bridge || {};

    const bridgeRows = bridges.map(b => {
        const count = entityCounts[b.name] || 0;
        return `<tr><td>${escHtml(b.name)}</td><td class="port">${b.port}</td><td>${count}</td></tr>`;
    }).join('');

    let warningHtml = '';
    if (data.packages_configured === false) {
        warningHtml = `
            <div class="result-warning">
                <div>
                    <strong>Packages not detected in configuration.yaml</strong><br>
                    Add this to your <code>configuration.yaml</code> for HA to load the bridges:
                    <code>homeassistant:\n  packages: !include_dir_named packages</code>
                </div>
            </div>`;
    }

    const steps = [
        { title: 'Restart Home Assistant', desc: 'Go to Settings \u2192 System \u2192 Restart. Required for bridge changes to take effect.' },
        { title: 'Find pairing codes', desc: 'After restart, check Notifications in the HA sidebar. Each new bridge shows a QR code and 8-digit setup code.' },
        { title: 'Add to Apple Home', desc: 'Open the Home app on your iPhone or iPad, tap +, then "Add Accessory" and scan the QR code or enter the setup code.' },
    ];

    const stepsHtml = steps.map((s, i) => `
        <li>
            <span class="result-step-number">${i + 1}</span>
            <div class="result-step-text">
                <strong>${escHtml(s.title)}</strong>
                <span>${escHtml(s.desc)}</span>
            </div>
        </li>`).join('');

    const overlay = document.createElement('div');
    overlay.className = 'result-overlay';
    overlay.innerHTML = `
        <div class="result-overlay-content">
            <h2>Configuration Written</h2>
            ${warningHtml}
            <table class="result-bridge-table">
                <thead><tr><th>Bridge</th><th>Port</th><th>Entities</th></tr></thead>
                <tbody>${bridgeRows}</tbody>
            </table>
            <h3>Next Steps</h3>
            <ol class="result-steps">${stepsHtml}</ol>
            <div class="result-overlay-actions">
                <button class="btn btn-primary" id="btn-dismiss-result">Done</button>
            </div>
        </div>`;

    document.body.appendChild(overlay);
    overlay.querySelector('#btn-dismiss-result').addEventListener('click', () => overlay.remove());
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
}

async function onApply() {
    const btn = document.getElementById('btn-apply');
    btn.disabled = true;
    btn.textContent = 'Writing...';

    try {
        const result = await api('POST', 'api/apply', { areas: state.config });
        showResultOverlay(result);
    } catch (e) {
        showToast('Failed to write config: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Write to Config';
    }
}

async function onRefresh() {
    const btn = document.getElementById('btn-refresh');
    btn.disabled = true;
    btn.textContent = 'Refreshing...';

    try {
        await api('POST', 'api/refresh');
        state.areaEntities = {};  // Clear entity cache
        await loadAreas();
        renderAreaList();
        clearPreview();
        showToast('Data refreshed from Home Assistant', 'success');
    } catch (e) {
        showToast('Refresh failed: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Refresh from HA';
    }
}

// ── Utility ────────────────────────────────────────────────────────
function escHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escAttr(str) {
    return str.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Init ───────────────────────────────────────────────────────────
async function init() {
    const statusBar = document.getElementById('status-bar');

    try {
        statusBar.textContent = 'Loading...';
        await loadAreas();
        await loadSavedConfig();
        renderAreaList();
        updateToggleAllLabel();
        statusBar.textContent = `${state.areas.length} areas loaded`;
    } catch (e) {
        statusBar.textContent = 'Error: ' + e.message;
        statusBar.classList.add('error');
        document.getElementById('area-list').innerHTML =
            '<p style="text-align:center;color:#f44336;padding:40px">Failed to connect to Home Assistant.<br>Check the app logs.</p>';
    }

    // Wire up buttons
    document.getElementById('btn-generate').addEventListener('click', onGenerate);
    document.getElementById('btn-apply').addEventListener('click', onApply);
    document.getElementById('btn-refresh').addEventListener('click', onRefresh);
    document.getElementById('btn-toggle-all').addEventListener('click', toggleAllAreas);
    document.getElementById('btn-minimal').addEventListener('click', applyMinimalConfig);
}

init();
