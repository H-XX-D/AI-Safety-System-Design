/**
 * 9-Phase Workflow Visualization
 * ===============================
 * Handles the display and interaction with proposal workflow phases
 */

// Phase icons mapping
const PHASE_ICONS = {
    'SUBMISSION': '📝',
    'AGENT_TESTING': '🧪',
    'PEER_REVIEW': '👥',
    'ORKA_COUNTERPOINT': '⚔️',
    'AGENT_DEFENSE': '🛡️',
    'FINAL_TESTING': '✅',
    'HUMAN_NOTIFICATION': '👤',
    'VAL_VALIDATION': '🔒',
    'DEPLOYMENT': '🚀'
};

// Status icons
const STATUS_ICONS = {
    'completed': '✓',
    'active': '●',
    'pending': '○',
    'failed': '✗',
    'skipped': '⊘'
};

/**
 * Load and render workflow phases for a proposal
 */
async function loadWorkflowPhases(proposalId) {
    try {
        const response = await fetch(`/api/proposals/${proposalId}/phases`);
        if (!response.ok) {
            throw new Error('Failed to load workflow phases');
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error loading workflow phases:', error);
        return null;
    }
}

/**
 * Render the 9-phase pipeline visualization
 */
function renderPhasePipeline(containerId, phases, currentPhase) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    let html = '<div class="phase-pipeline">';
    
    phases.forEach((phase, index) => {
        const statusClass = phase.status || 'pending';
        const isActive = phase.id === currentPhase;
        
        html += `
            <div class="phase-item ${statusClass} ${isActive ? 'active' : ''}" 
                 data-phase-id="${phase.id}"
                 onclick="showPhaseDetail(${phase.id})">
                <div class="phase-node" title="${escapeHtml(phase.description)}">
                    ${phase.icon || PHASE_ICONS[phase.name] || (index + 1)}
                </div>
                <div class="phase-label">${escapeHtml(phase.label)}</div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * Render the phase timeline with history
 */
function renderPhaseTimeline(containerId, phaseHistory) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    if (!phaseHistory || phaseHistory.length === 0) {
        container.innerHTML = '<p class="text-muted">No phase history available</p>';
        return;
    }
    
    let html = `
        <div class="timeline-header">
            <h4>Phase History</h4>
            <span class="text-muted">${phaseHistory.length} transitions</span>
        </div>
        <div class="timeline-list">
    `;
    
    phaseHistory.forEach(entry => {
        const icon = PHASE_ICONS[entry.phase_name] || '📋';
        const statusIcon = STATUS_ICONS[entry.status] || '○';
        const duration = entry.completed_at && entry.started_at 
            ? formatDuration(new Date(entry.completed_at) - new Date(entry.started_at))
            : 'In progress';
        
        html += `
            <div class="timeline-item ${entry.status}">
                <div class="timeline-icon">${icon}</div>
                <div class="timeline-content">
                    <div class="timeline-phase-name">
                        ${statusIcon} ${escapeHtml(entry.label)}
                    </div>
                    <div class="timeline-description">${escapeHtml(entry.notes || '')}</div>
                    <div class="timeline-meta">
                        <span class="timeline-duration">
                            <i class="fas fa-clock"></i> ${duration}
                        </span>
                        ${entry.started_at ? `
                            <span class="timeline-time">
                                <i class="fas fa-calendar"></i> ${formatTimestamp(entry.started_at)}
                            </span>
                        ` : ''}
                        ${entry.triggered_by ? `
                            <span class="timeline-trigger">
                                <i class="fas fa-user"></i> ${escapeHtml(entry.triggered_by)}
                            </span>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * Render the progress bar
 */
function renderProgressBar(containerId, progress) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const percentage = progress.percentage || 0;
    
    container.innerHTML = `
        <div class="workflow-progress">
            <div class="progress-bar-container">
                <div class="progress-bar-fill" style="width: ${percentage}%"></div>
            </div>
            <div class="progress-text">
                <span>${progress.completed} of ${progress.total} phases completed</span>
                <span>${percentage.toFixed(0)}%</span>
            </div>
        </div>
    `;
}

/**
 * Show detailed information about a specific phase
 */
function showPhaseDetail(phaseId) {
    // This would open a modal with detailed phase information
    console.log('Show phase detail:', phaseId);
    
    // If we have phase data cached, show modal
    if (window.currentWorkflowData && window.currentWorkflowData.phases) {
        const phase = window.currentWorkflowData.phases.find(p => p.id === phaseId);
        if (phase) {
            showPhaseModal(phase);
        }
    }
}

/**
 * Show phase detail modal
 */
function showPhaseModal(phase) {
    const modalContent = `
        <div class="phase-detail-header">
            <div class="phase-detail-icon">${phase.icon || '📋'}</div>
            <div class="phase-detail-info">
                <h3>${escapeHtml(phase.label)}</h3>
                <span class="phase-detail-status ${phase.status}">${phase.status}</span>
            </div>
        </div>
        <div class="phase-detail-body">
            <div class="phase-detail-section">
                <h4>Description</h4>
                <p>${escapeHtml(phase.description)}</p>
            </div>
            ${phase.started_at ? `
                <div class="phase-detail-section">
                    <h4>Timing</h4>
                    <div class="phase-metrics">
                        <div class="phase-metric">
                            <div class="phase-metric-value">${formatTimestamp(phase.started_at)}</div>
                            <div class="phase-metric-label">Started</div>
                        </div>
                        ${phase.completed_at ? `
                            <div class="phase-metric">
                                <div class="phase-metric-value">${formatTimestamp(phase.completed_at)}</div>
                                <div class="phase-metric-label">Completed</div>
                            </div>
                            <div class="phase-metric">
                                <div class="phase-metric-value">${formatDuration(phase.duration_seconds * 1000)}</div>
                                <div class="phase-metric-label">Duration</div>
                            </div>
                        ` : `
                            <div class="phase-metric">
                                <div class="phase-metric-value">In Progress</div>
                                <div class="phase-metric-label">Status</div>
                            </div>
                        `}
                    </div>
                </div>
            ` : ''}
        </div>
    `;
    
    // Use existing modal system if available
    if (typeof showModal === 'function') {
        const modal = document.getElementById('phaseDetailModal');
        if (modal) {
            const modalBody = modal.querySelector('.modal-body');
            if (modalBody) {
                modalBody.innerHTML = modalContent;
            }
            showModal('phaseDetailModal');
        } else {
            // Create temporary modal
            showTemporaryModal('Phase Details', modalContent);
        }
    }
}

/**
 * Show a temporary modal
 */
function showTemporaryModal(title, content) {
    // Remove existing temp modal
    const existing = document.getElementById('tempPhaseModal');
    if (existing) existing.remove();
    
    const modal = document.createElement('div');
    modal.id = 'tempPhaseModal';
    modal.className = 'modal active';
    modal.innerHTML = `
        <div class="modal-content phase-detail-modal">
            <div class="modal-header">
                <h2>${escapeHtml(title)}</h2>
                <button class="modal-close" onclick="this.closest('.modal').remove()">&times;</button>
            </div>
            <div class="modal-body">
                ${content}
            </div>
        </div>
    `;
    
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
    
    document.body.appendChild(modal);
}

/**
 * Update workflow visualization in real-time
 */
function updateWorkflowVisualization(proposalId, newPhase) {
    // If we're viewing this proposal, refresh the visualization
    if (window.currentProposalId === proposalId) {
        loadAndRenderWorkflow(proposalId);
    }
}

/**
 * Load and render complete workflow for a proposal
 */
async function loadAndRenderWorkflow(proposalId) {
    const data = await loadWorkflowPhases(proposalId);
    if (!data) return;
    
    // Cache for phase detail modal
    window.currentWorkflowData = data;
    window.currentProposalId = proposalId;
    
    // Render pipeline
    renderPhasePipeline('workflowPipeline', data.phases, data.current_phase);
    
    // Render timeline
    renderPhaseTimeline('workflowTimeline', data.phase_history);
    
    // Render progress
    renderProgressBar('workflowProgress', data.progress);
    
    // Update current phase indicator
    const currentPhaseEl = document.getElementById('currentPhase');
    if (currentPhaseEl) {
        currentPhaseEl.textContent = data.current_phase_name;
    }
    
    // Update estimated completion
    const estimatedEl = document.getElementById('estimatedCompletion');
    if (estimatedEl && data.estimated_completion) {
        estimatedEl.textContent = formatTimestamp(data.estimated_completion);
    }
}

/**
 * Format duration in milliseconds to human readable
 */
function formatDuration(ms) {
    if (!ms || ms < 0) return 'N/A';
    
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) {
        return `${days}d ${hours % 24}h`;
    } else if (hours > 0) {
        return `${hours}h ${minutes % 60}m`;
    } else if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
    } else {
        return `${seconds}s`;
    }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString) {
    if (!isoString) return 'N/A';
    
    try {
        const date = new Date(isoString);
        const now = new Date();
        const diff = now - date;
        
        // Less than 1 minute
        if (diff < 60000) {
            return 'Just now';
        }
        // Less than 1 hour
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes}m ago`;
        }
        // Less than 1 day
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours}h ago`;
        }
        // More than 1 day
        return date.toLocaleDateString();
    } catch {
        return isoString;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions for use in other modules
if (typeof window !== 'undefined') {
    window.loadWorkflowPhases = loadWorkflowPhases;
    window.renderPhasePipeline = renderPhasePipeline;
    window.renderPhaseTimeline = renderPhaseTimeline;
    window.renderProgressBar = renderProgressBar;
    window.loadAndRenderWorkflow = loadAndRenderWorkflow;
    window.updateWorkflowVisualization = updateWorkflowVisualization;
    window.showPhaseDetail = showPhaseDetail;
}

