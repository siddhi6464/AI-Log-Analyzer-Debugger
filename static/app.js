/**
 * AI Log Analyzer & Debugger — Frontend Application
 * Handles log input, API calls, SSE streaming, and dynamic UI rendering.
 */

// ── DOM Elements ──────────────────────────────────────────

const logInput = document.getElementById('log-input');
const sampleSelect = document.getElementById('sample-select');
const btnAnalyze = document.getElementById('btn-analyze');
const btnStream = document.getElementById('btn-stream');
const btnClear = document.getElementById('btn-clear');
const lineCount = document.getElementById('line-count');
const dropzone = document.getElementById('dropzone');
const resultsSection = document.getElementById('results-section');
const loadingOverlay = document.getElementById('loading-overlay');
const loaderText = document.getElementById('loader-text');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');

// Summary value elements
const valTotal = document.getElementById('val-total');
const valErrors = document.getElementById('val-errors');
const valWarnings = document.getElementById('val-warnings');
const valAnomalies = document.getElementById('val-anomalies');
const valPatterns = document.getElementById('val-patterns');
const valFormat = document.getElementById('val-format');

// Tab content elements
const patternsList = document.getElementById('patterns-list');
const anomaliesList = document.getElementById('anomalies-list');
const suggestionsList = document.getElementById('suggestions-list');
const aiAnalysisContent = document.getElementById('ai-analysis-content');
const streamLog = document.getElementById('stream-log');

// ── State ─────────────────────────────────────────────────

let isProcessing = false;
let eventSource = null;

// ── Initialization ────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    loadSamples();
    setupEventListeners();
    updateLineCount();
});

function setupEventListeners() {
    // Buttons
    btnAnalyze.addEventListener('click', handleBatchAnalysis);
    btnStream.addEventListener('click', handleStreamAnalysis);
    btnClear.addEventListener('click', handleClear);

    // Line count
    logInput.addEventListener('input', updateLineCount);

    // Sample selector
    sampleSelect.addEventListener('change', handleSampleLoad);

    // Drag and drop
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
    });
    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('drag-over');
    });
    dropzone.addEventListener('drop', handleFileDrop);

    // Also allow clicking dropzone
    dropzone.addEventListener('click', () => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.log,.txt,.out';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) readFile(file);
        };
        input.click();
    });

    // Tab navigation
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
}

// ── Sample Loading ────────────────────────────────────────

async function loadSamples() {
    try {
        const res = await fetch('/api/samples');
        const data = await res.json();
        data.samples.forEach(sample => {
            const opt = document.createElement('option');
            opt.value = sample.name;
            opt.textContent = `${sample.name} (${sample.size_display})`;
            sampleSelect.appendChild(opt);
        });
    } catch (err) {
        console.error('Failed to load samples:', err);
    }
}

async function handleSampleLoad() {
    const name = sampleSelect.value;
    if (!name) return;

    try {
        setStatus('loading', `Loading ${name}...`);
        const res = await fetch(`/api/samples/${name}`);
        const data = await res.json();
        logInput.value = data.content;
        updateLineCount();
        setStatus('ready', 'Sample loaded');
    } catch (err) {
        setStatus('error', 'Failed to load sample');
    }
}

// ── File Handling ─────────────────────────────────────────

function handleFileDrop(e) {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) readFile(file);
}

function readFile(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        logInput.value = e.target.result;
        updateLineCount();
        setStatus('ready', `Loaded: ${file.name}`);
    };
    reader.readAsText(file);
}

// ── Batch Analysis ────────────────────────────────────────

async function handleBatchAnalysis() {
    const text = logInput.value.trim();
    if (!text) {
        alert('Please paste or upload log text first.');
        return;
    }

    if (isProcessing) return;
    isProcessing = true;

    setStatus('processing', 'Analyzing...');
    showLoading('Analyzing logs with AI...');
    disableButtons(true);

    try {
        const res = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ log_text: text }),
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Analysis failed');
        }

        const report = await res.json();
        renderReport(report);
        setStatus('ready', 'Analysis complete');
    } catch (err) {
        console.error('Analysis error:', err);
        setStatus('error', `Error: ${err.message}`);
        alert(`Analysis failed: ${err.message}`);
    } finally {
        hideLoading();
        disableButtons(false);
        isProcessing = false;
    }
}

// ── Stream Analysis ───────────────────────────────────────

async function handleStreamAnalysis() {
    const text = logInput.value.trim();
    if (!text) {
        alert('Please paste or upload log text first.');
        return;
    }

    if (isProcessing) return;
    isProcessing = true;

    setStatus('processing', 'Streaming analysis...');
    disableButtons(true);
    resultsSection.style.display = 'block';
    switchTab('stream-log');
    streamLog.innerHTML = '';
    addStreamEntry('status', '▶ Starting analysis pipeline...');

    try {
        const res = await fetch('/api/analyze/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ log_text: text }),
        });

        if (!res.ok) throw new Error('Stream request failed');

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let aiText = '';
        let finalReport = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const event = JSON.parse(line.slice(6));
                        handleStreamEvent(event);

                        if (event.event_type === 'ai_chunk') {
                            aiText += event.data.chunk;
                        }

                        if (event.event_type === 'complete') {
                            finalReport = event.data;
                        }
                    } catch (e) {
                        // Skip malformed events
                    }
                }
            }
        }

        // Render final report
        if (finalReport) {
            renderReport(finalReport);
            addStreamEntry('complete', '✓ Analysis complete!');
        }

        setStatus('ready', 'Stream analysis complete');
    } catch (err) {
        console.error('Stream error:', err);
        addStreamEntry('error', `✗ Error: ${err.message}`);
        setStatus('error', `Stream error: ${err.message}`);
    } finally {
        disableButtons(false);
        isProcessing = false;
    }
}

function handleStreamEvent(event) {
    switch (event.event_type) {
        case 'status':
            addStreamEntry('status', `⟫ ${event.data.message} [Step ${event.data.step}/${event.data.total}]`);
            loaderText && (loaderText.textContent = event.data.message);
            break;

        case 'parsed':
            addStreamEntry('status', `✓ Parsed ${event.data.total_entries} entries (${event.data.format} format), ${event.data.error_count} errors found`);
            break;

        case 'patterns':
            addStreamEntry('status', `✓ Detected ${event.data.count} error patterns`);
            // Live-update patterns
            if (event.data.patterns) {
                renderPatterns(event.data.patterns);
            }
            break;

        case 'anomalies':
            addStreamEntry('status', `✓ Found ${event.data.count} anomalies`);
            if (event.data.anomalies) {
                renderAnomalies(event.data.anomalies);
            }
            break;

        case 'ai_chunk':
            // Show small indicator — the full text accumulates
            break;

        case 'error':
            addStreamEntry('error', `✗ ${event.data.message}`);
            break;
    }
}

function addStreamEntry(type, text) {
    const div = document.createElement('div');
    div.className = `stream-entry ${type}`;
    div.textContent = `[${new Date().toLocaleTimeString()}] ${text}`;
    streamLog.appendChild(div);
    streamLog.scrollTop = streamLog.scrollHeight;
}

// ── Report Rendering ──────────────────────────────────────

function renderReport(report) {
    resultsSection.style.display = 'block';

    // Summary cards
    if (report.summary) {
        animateValue(valTotal, report.summary.total_lines);
        animateValue(valErrors, report.summary.error_count);
        animateValue(valWarnings, report.summary.warning_count);
        valFormat.textContent = report.summary.log_format || '—';
    }

    // Patterns
    if (report.patterns) {
        valPatterns.textContent = report.patterns.length;
        renderPatterns(report.patterns);
    }

    // Anomalies
    if (report.anomalies) {
        animateValue(valAnomalies, report.anomalies.length);
        renderAnomalies(report.anomalies);
    }

    // AI Suggestions
    if (report.suggestions) {
        renderSuggestions(report.suggestions);
    }

    // Raw AI Analysis
    if (report.raw_ai_analysis) {
        aiAnalysisContent.textContent = report.raw_ai_analysis;
        aiAnalysisContent.classList.remove('empty-state');
    }
}

function renderPatterns(patterns) {
    if (!patterns.length) {
        patternsList.innerHTML = '<p class="empty-state">No error patterns detected.</p>';
        return;
    }

    patternsList.innerHTML = patterns.map(p => `
        <div class="pattern-card">
            <div class="pattern-header">
                <span class="pattern-name">${escHtml(p.pattern_name)}</span>
                <div class="pattern-meta">
                    <span class="badge badge-${p.severity}">${p.severity}</span>
                    <span class="pattern-count">${p.count}×</span>
                </div>
            </div>
            <p class="pattern-desc">${escHtml(p.description)}</p>
            ${p.sample_lines && p.sample_lines.length ? `
                <div class="pattern-samples">${p.sample_lines.map(s => escHtml(s.substring(0, 200))).join('\n')}</div>
            ` : ''}
        </div>
    `).join('');
}

function renderAnomalies(anomalies) {
    if (!anomalies.length) {
        anomaliesList.innerHTML = '<p class="empty-state">No anomalies detected.</p>';
        return;
    }

    anomaliesList.innerHTML = anomalies.map(a => `
        <div class="anomaly-card">
            <div class="pattern-header">
                <span class="anomaly-title">${escHtml(a.title)}</span>
                <span class="badge badge-${a.severity}">${a.severity}</span>
            </div>
            <p class="anomaly-desc">${escHtml(a.description)}</p>
            ${a.evidence && a.evidence.length ? `
                <div class="anomaly-evidence">${a.evidence.map(e => escHtml(e)).join('\n')}</div>
            ` : ''}
            ${a.time_range ? `<div style="margin-top:0.4rem;font-size:0.72rem;color:var(--text-muted);">⏱ ${escHtml(a.time_range)}</div>` : ''}
        </div>
    `).join('');
}

function renderSuggestions(suggestions) {
    if (!suggestions.length) {
        suggestionsList.innerHTML = '<p class="empty-state">No suggestions generated.</p>';
        return;
    }

    suggestionsList.innerHTML = suggestions.map(s => {
        const confPercent = Math.round((s.confidence || 0) * 100);
        const confColor = confPercent >= 80 ? 'var(--accent-green)' :
            confPercent >= 50 ? 'var(--accent-amber)' : 'var(--accent-red)';

        return `
            <div class="suggestion-card">
                <div class="suggestion-header">
                    <span class="suggestion-class">💡 ${escHtml(s.error_class)}</span>
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span class="badge badge-${s.priority || 'medium'}">${s.priority || 'medium'}</span>
                        <div class="confidence-bar">
                            <div class="confidence-fill">
                                <div class="confidence-fill-inner" style="width:${confPercent}%;background:${confColor};"></div>
                            </div>
                            <span>${confPercent}%</span>
                        </div>
                    </div>
                </div>

                <div class="suggestion-section">
                    <div class="suggestion-label">Root Cause</div>
                    <p class="suggestion-text">${escHtml(s.root_cause)}</p>
                </div>

                <div class="suggestion-section">
                    <div class="suggestion-label">Suggested Fix</div>
                    <div class="suggestion-fix">${escHtml(s.suggested_fix)}</div>
                </div>

                ${s.related_patterns && s.related_patterns.length ? `
                    <div style="margin-top:0.5rem;font-size:0.72rem;color:var(--text-muted);">
                        Related: ${s.related_patterns.map(p => `<span style="color:var(--accent-cyan)">${escHtml(p)}</span>`).join(', ')}
                    </div>
                ` : ''}
            </div>
        `;
    }).join('');
}

// ── UI Helpers ────────────────────────────────────────────

function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

    const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
    const pane = document.getElementById(`tab-${tabName}`);
    if (tab) tab.classList.add('active');
    if (pane) pane.classList.add('active');
}

function updateLineCount() {
    const text = logInput.value;
    const count = text ? text.split('\n').length : 0;
    lineCount.textContent = `${count} line${count !== 1 ? 's' : ''}`;
}

function setStatus(type, text) {
    statusDot.className = 'status-dot';
    if (type === 'processing') statusDot.classList.add('processing');
    if (type === 'error') statusDot.classList.add('error');
    statusText.textContent = text;
}

function showLoading(text) {
    loaderText.textContent = text;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

function disableButtons(disabled) {
    btnAnalyze.disabled = disabled;
    btnStream.disabled = disabled;
}

function handleClear() {
    logInput.value = '';
    sampleSelect.value = '';
    updateLineCount();
    resultsSection.style.display = 'none';
    setStatus('ready', 'Ready');

    // Clear all results
    patternsList.innerHTML = '<p class="empty-state">No patterns detected yet.</p>';
    anomaliesList.innerHTML = '<p class="empty-state">No anomalies detected yet.</p>';
    suggestionsList.innerHTML = '<p class="empty-state">No suggestions generated yet.</p>';
    aiAnalysisContent.innerHTML = '<p class="empty-state">Run analysis to see AI insights.</p>';
    streamLog.innerHTML = '<p class="empty-state">Use "Stream Analysis" to see real-time updates.</p>';
}

function animateValue(el, target) {
    const duration = 600;
    const start = parseInt(el.textContent) || 0;
    const startTime = performance.now();

    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        el.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) requestAnimationFrame(update);
    }

    requestAnimationFrame(update);
}

function escHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
