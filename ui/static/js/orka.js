/**
 * ORKASTRATOR Oversight Tab - JavaScript
 * =======================================
 * Handles ORKASTRATOR tab functionality, USB transfers, and proposal details
 */

// Current proposal being viewed
let currentProposal = null;

// ===== HTML SANITIZATION HELPERS =====
function _h(txt){
    if(txt === null || txt === undefined) return '';
    return String(txt)
        .replace(/&/g,'&amp;')
        .replace(/</g,'&lt;')
        .replace(/>/g,'&gt;')
        .replace(/"/g,'&quot;')
        .replace(/'/g,'&#39;');
}
function _classFrom(value, allow){
    const v = String(value || '').toLowerCase();
    return allow.includes(v) ? v : allow[0];
}

// ===== TAB SWITCHING =====

function switchTab(tabName) {
    // Hide all tab panes
    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.style.display = 'none';
    });

    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const selectedTab = document.getElementById(`tab-${tabName}`);
    if (selectedTab) {
        selectedTab.style.display = 'block';
    }

    // Add active class to clicked button
    event.target.classList.add('active');
}

// ===== PROPOSAL VIEWING =====

async function viewProposal(proposalId) {
    try {
        showToast('Loading proposal details...', 'info', 2000);

        // Fetch full proposal data (via global helper for consistent headers/banners)
        currentProposal = await fetchJSON(`/api/proposals/${proposalId}`);

        // Populate modal with data
        populateProposalModal(currentProposal);

        // Show modal
        showModal('proposalDetailModal');

    } catch (error) {
        console.error('Error loading proposal:', error);
        showToast('Failed to load proposal details', 'error');
    }
}

function populateProposalModal(proposal) {
    // Basic info
    document.getElementById('proposalId').textContent = proposal.id;
    document.getElementById('detail-id').textContent = proposal.id;
    document.getElementById('detail-agent').innerHTML = `<span class="agent-badge ${proposal.agent_id.toLowerCase()}">${proposal.agent_id}</span>`;
    document.getElementById('detail-component').textContent = proposal.component || 'N/A';
    document.getElementById('detail-status').innerHTML = `<span class="status-badge ${proposal.status}">${proposal.status}</span>`;
    document.getElementById('detail-timestamp').textContent = new Date(proposal.timestamp).toLocaleString();
    document.getElementById('detail-description').textContent = proposal.description || '';

    // Risk scores
    const riskScore = proposal.risks?.overall_risk_score || proposal.deception_confidence || 0;
    document.getElementById('risk-score').textContent = `Overall Risk: ${(riskScore * 100).toFixed(1)}%`;
    document.getElementById('risk-fill').style.width = `${riskScore * 100}%`;

    const deceptionScore = proposal.deception_analysis?.deception_confidence || proposal.deception_confidence || 0;
    document.getElementById('deception-score').innerHTML = `<strong>${(deceptionScore * 100).toFixed(1)}%</strong>`;

    const alignmentScore = proposal.deception_analysis?.alignment_score || 0.85;
    document.getElementById('alignment-score').innerHTML = `<strong>${(alignmentScore * 100).toFixed(1)}%</strong>`;

    const trustScore = proposal.deception_analysis?.trust_score || 0.90;
    document.getElementById('trust-score').innerHTML = `<strong>${(trustScore * 100).toFixed(1)}%</strong>`;

    // Static code scan evidence (if provided by backend)
    try {
        const staticScan = proposal.deception_analysis?.evidence?.static_scan;
        const scanDiv = document.getElementById('static-scan-evidence');
        if (scanDiv && staticScan && Array.isArray(staticScan.issues)) {
            const items = staticScan.issues.map(i => `<li>${_h(i)}</li>`).join('') || '<li>None</li>';
            scanDiv.innerHTML = `
                <h4><i class="fas fa-shield-alt"></i> Static Code Scan</h4>
                <ul>${items}</ul>
            `;
        }
    } catch (e) { /* ignore */ }

    // Approval rate
    const approvalRate = proposal.peer_reviews?.approval_rate || 1.0;
    document.getElementById('approval-rate').innerHTML = `
        <div class="approval-bar large">
            <div class="approval-fill" style="width: ${approvalRate * 100}%"></div>
            <span>${(approvalRate * 100).toFixed(0)}% Approval</span>
        </div>
    `;

    // Signatures
    document.getElementById('sig-proposer').textContent = proposal.agent_id;
    document.getElementById('sig-orka').textContent = 'ORKASTRATOR';
    document.getElementById('sig-val').textContent = proposal.status === 'approved' ? 'VAL' : 'Pending';

    // Populate other tabs
    populateIdeaTab(proposal);
    populateRisksTab(proposal);
    populateExperimentsTab(proposal);
    populateReviewsTab(proposal);
    populateOrkaTab(proposal);
    populateDefenseTab(proposal);
    populateTestingTab(proposal);
    populateValTab(proposal);
    populateCodeTab(proposal);
}

function populateIdeaTab(proposal) {
    const idea = proposal.idea || {
        description: proposal.description,
        motivation: "Improve system capabilities",
        technical_approach: "Implementation details not available",
        expected_benefits: ["Enhanced functionality"],
        scope: proposal.component || "Unknown",
        dependencies: []
    };

    const html = `
        <div class="info-section">
            <h4>Description</h4>
            <p>${_h(idea.description)}</p>
        </div>
        <div class="info-section">
            <h4>Motivation</h4>
            <p>${_h(idea.motivation)}</p>
        </div>
        <div class="info-section">
            <h4>Technical Approach</h4>
            <p>${_h(idea.technical_approach)}</p>
        </div>
        <div class="info-section">
            <h4>Expected Benefits</h4>
            <ul>
                ${idea.expected_benefits.map(b => `<li>${_h(b)}</li>`).join('')}
            </ul>
        </div>
        <div class="info-grid">
            <div class="info-item">
                <span class="label">Scope:</span>
                <span class="value">${_h(idea.scope)}</span>
            </div>
            <div class="info-item">
                <span class="label">Dependencies:</span>
                <span class="value">${idea.dependencies.length > 0 ? _h(idea.dependencies.join(', ')) : 'None'}</span>
            </div>
        </div>
    `;

    document.getElementById('idea-content').innerHTML = html;
}

function populateRisksTab(proposal) {
    const risks = proposal.risks || {
        technical_risks: [],
        safety_risks: [],
        alignment_risks: [],
        overall_risk_score: proposal.deception_confidence || 0
    };

    const html = `
        <div class="risk-overview">
            <h4>Overall Risk Score: ${(risks.overall_risk_score * 100).toFixed(1)}%</h4>
            <div class="risk-meter large">
                <div class="meter-bar">
                    <div class="meter-fill" style="width: ${risks.overall_risk_score * 100}%"></div>
                </div>
            </div>
        </div>

        <div class="risk-category">
            <h4><i class="fas fa-wrench"></i> Technical Risks</h4>
            ${risks.technical_risks.length > 0 ? risks.technical_risks.map(r => {
                const sev = _classFrom(r.severity, ['low','medium','high','critical']);
                const like = _h(r.likelihood || '');
                return `
                <div class="risk-item-card">
                    <div class="risk-header">
                        <span class="risk-severity ${sev}">${_h(r.severity)}</span>
                        <span class="risk-likelihood">${like} likelihood</span>
                    </div>
                    <p class="risk-description"><strong>Risk:</strong> ${_h(r.risk)}</p>
                    <p class="mitigation"><strong>Mitigation:</strong> ${_h(r.mitigation)}</p>
                </div>
            `}).join('') : '<p class="empty-state">No technical risks identified</p>'}
        </div>

        <div class="risk-category">
            <h4><i class="fas fa-shield-alt"></i> Safety Risks</h4>
            ${risks.safety_risks.length > 0 ? risks.safety_risks.map(r => {
                const sev = _classFrom(r.severity, ['low','medium','high','critical']);
                const like = _h(r.likelihood || '');
                return `
                <div class="risk-item-card">
                    <div class="risk-header">
                        <span class="risk-severity ${sev}">${_h(r.severity)}</span>
                        <span class="risk-likelihood">${like} likelihood</span>
                    </div>
                    <p class="risk-description"><strong>Risk:</strong> ${_h(r.risk)}</p>
                    <p class="mitigation"><strong>Mitigation:</strong> ${_h(r.mitigation)}</p>
                </div>
            `}).join('') : '<p class="empty-state">No safety risks identified</p>'}
        </div>

        <div class="risk-category">
            <h4><i class="fas fa-balance-scale"></i> Alignment Risks</h4>
            ${risks.alignment_risks.length > 0 ? risks.alignment_risks.map(r => {
                const sev = _classFrom(r.severity, ['low','medium','high','critical']);
                const like = _h(r.likelihood || '');
                return `
                <div class="risk-item-card">
                    <div class="risk-header">
                        <span class="risk-severity ${sev}">${_h(r.severity)}</span>
                        <span class="risk-likelihood">${like} likelihood</span>
                    </div>
                    <p class="risk-description"><strong>Risk:</strong> ${_h(r.risk)}</p>
                    <p class="mitigation"><strong>Mitigation:</strong> ${_h(r.mitigation)}</p>
                </div>
            `}).join('') : '<p class="empty-state">No alignment risks identified</p>'}
        </div>
    `;

    document.getElementById('risks-content').innerHTML = html;
}

function populateExperimentsTab(proposal) {
    const experiments = proposal.experiments || {
        test_environment: "Sandbox environment",
        metrics: [],
        test_cases_passed: 0,
        test_cases_failed: 0,
        pass_rate: 0,
        edge_cases_tested: []
    };

    const html = `
        <div class="info-section">
            <h4>Test Environment</h4>
            <p>${experiments.test_environment}</p>
        </div>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">${experiments.test_cases_passed}</div>
                <div class="metric-label">Tests Passed</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${experiments.test_cases_failed}</div>
                <div class="metric-label">Tests Failed</div>
            </div>
            <div class="metric-card success">
                <div class="metric-value">${(experiments.pass_rate * 100).toFixed(1)}%</div>
                <div class="metric-label">Pass Rate</div>
            </div>
        </div>

        <div class="info-section">
            <h4>Performance Metrics</h4>
            <table class="results-table">
                <thead>
                    <tr>
                        <th>Metric</th>
                        <th>Baseline</th>
                        <th>Result</th>
                        <th>Target</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${experiments.metrics.length > 0 ? experiments.metrics.map(m => `
                        <tr>
                            <td>${m.metric}</td>
                            <td>${m.baseline}</td>
                            <td><strong>${m.result}</strong></td>
                            <td>${m.target}</td>
                            <td><span class="status-badge ${m.status === 'exceeded' || m.status === 'met' ? 'success' : 'warning'}">${m.status}</span></td>
                        </tr>
                    `).join('') : '<tr><td colspan="5" class="empty-state">No metrics available</td></tr>'}
                </tbody>
            </table>
        </div>

        ${experiments.edge_cases_tested.length > 0 ? `
            <div class="info-section">
                <h4>Edge Cases Tested</h4>
                <ul>
                    ${experiments.edge_cases_tested.map(ec => `<li>${ec}</li>`).join('')}
                </ul>
            </div>
        ` : ''}
    `;

    document.getElementById('experiments-content').innerHTML = html;
}

function populateReviewsTab(proposal) {
    const reviews = proposal.peer_reviews?.reviews || proposal.peer_reviews || [];
    const approvalRate = proposal.peer_reviews?.approval_rate || 1.0;

    const html = `
        <div class="reviews-header">
            <h4>Peer Review Summary</h4>
            <div class="approval-rate">
                <strong>${(approvalRate * 100).toFixed(0)}%</strong> Approval Rate
            </div>
        </div>

        <div class="reviews-list">
            ${Array.isArray(reviews) && reviews.length > 0 ? reviews.map(r => `
                <div class="review-card">
                    <div class="review-header">
                        <div class="reviewer-info">
                            <span class="agent-badge ${r.reviewer?.toLowerCase()}">${r.reviewer}</span>
                            <span class="review-date">${new Date(r.timestamp).toLocaleDateString()}</span>
                        </div>
                        <div class="review-score">
                            <i class="fas fa-star"></i> ${r.overall_score}/5.0
                        </div>
                    </div>
                    <div class="review-body">
                        <p><strong>Comments:</strong> ${r.comments}</p>
                        ${r.concerns && r.concerns.length > 0 ? `
                            <div class="review-concerns">
                                <strong>Concerns:</strong>
                                <ul>
                                    ${r.concerns.map(c => `<li>${c}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                        ${r.suggestions && r.suggestions.length > 0 ? `
                            <div class="review-suggestions">
                                <strong>Suggestions:</strong>
                                <ul>
                                    ${r.suggestions.map(s => `<li>${s}</li>`).join('')}
                                </ul>
                            </div>
                        ` : ''}
                    </div>
                    <div class="review-footer">
                        <span class="vote-badge ${r.vote}">${r.vote}</span>
                    </div>
                </div>
            `).join('') : '<p class="empty-state">No peer reviews available</p>'}
        </div>
    `;

    document.getElementById('reviews-content').innerHTML = html;
}

function populateOrkaTab(proposal) {
    const orka = proposal.orka_counterpoint || {
        adversarial_analysis: "ORKASTRATOR counterpoint analysis not yet available",
        attack_vectors_tested: [],
        worst_case_scenarios: [],
        recommendation: "Pending review",
        concerns: []
    };

    const html = `
        <div class="orka-analysis">
            <h4>Adversarial Analysis</h4>
            <p>${orka.adversarial_analysis}</p>
        </div>

        ${orka.attack_vectors_tested.length > 0 ? `
            <div class="attack-vectors">
                <h4>Attack Vectors Tested</h4>
                ${orka.attack_vectors_tested.map(av => `
                    <div class="attack-card">
                        <h5>${av.attack}</h5>
                        <p><strong>Result:</strong> ${av.result}</p>
                        <p><strong>Confidence:</strong> ${(av.confidence * 100).toFixed(0)}%</p>
                    </div>
                `).join('')}
            </div>
        ` : ''}

        ${orka.worst_case_scenarios.length > 0 ? `
            <div class="scenarios">
                <h4>Worst-Case Scenarios</h4>
                ${orka.worst_case_scenarios.map(sc => `
                    <div class="scenario-card">
                        <h5>${sc.scenario}</h5>
                        <div class="scenario-metrics">
                            <span>Likelihood: <strong>${sc.likelihood}</strong></span>
                            <span>Impact: <strong>${sc.impact}</strong></span>
                            <span>Detectability: <strong>${sc.detectability}</strong></span>
                        </div>
                        <p><strong>Conclusion:</strong> ${sc.conclusion}</p>
                    </div>
                `).join('')}
            </div>
        ` : ''}

        <div class="orka-recommendation">
            <h4>ORKASTRATOR Recommendation</h4>
            <p class="recommendation-text">${orka.recommendation}</p>
        </div>
    `;

    document.getElementById('orka-content').innerHTML = html;
}

function populateDefenseTab(proposal) {
    const defense = proposal.agent_defense || {
        response_to_concerns: [],
        revisions_made: [],
        updated_timeline: "No updates"
    };

    const html = `
        <div class="defense-responses">
            <h4>Agent Responses to Concerns</h4>
            ${defense.response_to_concerns.length > 0 ? defense.response_to_concerns.map(r => `
                <div class="response-card ${r.accepted ? 'accepted' : ''}">
                    <div class="concern-text">
                        <strong>Concern:</strong> ${r.concern}
                    </div>
                    <div class="response-text">
                        <strong>Response:</strong> ${r.response}
                    </div>
                    ${r.evidence ? `
                        <div class="evidence-text">
                            <strong>Evidence:</strong> ${r.evidence}
                        </div>
                    ` : ''}
                    <div class="acceptance-badge">
                        ${r.accepted ? '<i class="fas fa-check-circle"></i> Accepted' : '<i class="fas fa-times-circle"></i> Not Accepted'}
                    </div>
                </div>
            `).join('') : '<p class="empty-state">No concerns raised or defense not yet provided</p>'}
        </div>

        ${defense.revisions_made.length > 0 ? `
            <div class="revisions-section">
                <h4>Revisions Made</h4>
                <ul>
                    ${defense.revisions_made.map(r => `<li>${r}</li>`).join('')}
                </ul>
            </div>
        ` : ''}

        <div class="timeline-section">
            <h4>Updated Timeline</h4>
            <p>${defense.updated_timeline}</p>
        </div>
    `;

    document.getElementById('defense-content').innerHTML = html;
}

function populateTestingTab(proposal) {
    const testing = proposal.final_testing || {
        comprehensive_test_suite: {
            unit_tests: 0,
            integration_tests: 0,
            end_to_end_tests: 0,
            security_tests: 0,
            performance_tests: 0,
            total: 0,
            passed: 0,
            pass_rate: 0
        },
        safety_validation: {},
        performance_validation: {}
    };

    const suite = testing.comprehensive_test_suite;

    const html = `
        <div class="test-summary">
            <div class="test-metric-grid">
                <div class="test-metric">
                    <div class="test-value">${suite.total}</div>
                    <div class="test-label">Total Tests</div>
                </div>
                <div class="test-metric success">
                    <div class="test-value">${suite.passed}</div>
                    <div class="test-label">Passed</div>
                </div>
                <div class="test-metric">
                    <div class="test-value">${(suite.pass_rate * 100).toFixed(1)}%</div>
                    <div class="test-label">Pass Rate</div>
                </div>
            </div>
        </div>

        <div class="test-breakdown">
            <h4>Test Suite Breakdown</h4>
            <table class="results-table">
                <tr>
                    <td>Unit Tests</td>
                    <td>${suite.unit_tests}</td>
                </tr>
                <tr>
                    <td>Integration Tests</td>
                    <td>${suite.integration_tests}</td>
                </tr>
                <tr>
                    <td>End-to-End Tests</td>
                    <td>${suite.end_to_end_tests}</td>
                </tr>
                <tr>
                    <td>Security Tests</td>
                    <td>${suite.security_tests}</td>
                </tr>
                <tr>
                    <td>Performance Tests</td>
                    <td>${suite.performance_tests}</td>
                </tr>
            </table>
        </div>

        <div class="validation-section">
            <h4>Safety Validation</h4>
            <div class="validation-grid">
                ${Object.entries(testing.safety_validation).map(([key, value]) => `
                    <div class="validation-item ${value === 'passed' ? 'passed' : ''}">
                        <i class="fas fa-${value === 'passed' ? 'check-circle' : 'clock'}"></i>
                        <span>${key.replace(/_/g, ' ')}: ${value}</span>
                    </div>
                `).join('')}
            </div>
        </div>

        ${testing.performance_validation && Object.keys(testing.performance_validation).length > 0 ? `
            <div class="performance-section">
                <h4>Performance Validation</h4>
                <table class="results-table">
                    ${Object.entries(testing.performance_validation).map(([key, value]) => `
                        <tr>
                            <td>${key.replace(/_/g, ' ')}</td>
                            <td><strong>${value}</strong></td>
                        </tr>
                    `).join('')}
                </table>
            </div>
        ` : ''}
    `;

    document.getElementById('testing-content').innerHTML = html;
}

function populateValTab(proposal) {
    const val = proposal.val_validation || {
        validation_duration_hours: 0,
        val_checks_performed: [],
        val_findings: [],
        val_recommendation: "Pending VAL review",
        val_confidence: 0
    };

    const html = `
        <div class="val-status">
            <h4>VAL Validation Status</h4>
            <p>Duration: <strong>${val.validation_duration_hours} hours</strong></p>
            <p>Confidence: <strong>${(val.val_confidence * 100).toFixed(0)}%</strong></p>
        </div>

        <div class="val-checks">
            <h4>Checks Performed</h4>
            <ul>
                ${val.val_checks_performed.map(check => `<li><i class="fas fa-check"></i> ${check}</li>`).join('')}
            </ul>
        </div>

        ${val.val_findings.length > 0 ? `
            <div class="val-findings">
                <h4>Findings</h4>
                ${val.val_findings.map(f => `
                    <div class="finding-card ${f.severity}">
                        <div class="finding-header">
                            <span class="severity-badge ${f.severity}">${f.severity}</span>
                            <span class="status-badge ${f.status}">${f.status}</span>
                        </div>
                        <p><strong>Finding:</strong> ${f.finding}</p>
                        <p><strong>Recommendation:</strong> ${f.recommendation}</p>
                    </div>
                `).join('')}
            </div>
        ` : '<p class="empty-state">No findings reported</p>'}

        <div class="val-recommendation">
            <h4>VAL Recommendation</h4>
            <p class="recommendation-text large">${val.val_recommendation}</p>
        </div>
    `;

    document.getElementById('val-content').innerHTML = html;
}

function populateCodeTab(proposal) {
    const code = proposal.code || {
        files_modified: [],
        files_added: [],
        total_lines_changed: 0,
        test_coverage: 0,
        code_attached: false
    };

    const html = `
        <div class="code-stats">
            <div class="stat-grid">
                <div class="stat-item">
                    <div class="stat-value">${code.files_modified.length + code.files_added.length}</div>
                    <div class="stat-label">Files Changed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${code.total_lines_changed}</div>
                    <div class="stat-label">Lines Changed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${(code.test_coverage * 100).toFixed(0)}%</div>
                    <div class="stat-label">Test Coverage</div>
                </div>
            </div>
        </div>

        ${code.files_modified.length > 0 ? `
            <div class="file-section">
                <h4>Files Modified</h4>
                <ul class="file-list">
                    ${code.files_modified.map(f => `<li><i class="fas fa-file-code"></i> ${f}</li>`).join('')}
                </ul>
            </div>
        ` : ''}

        ${code.files_added.length > 0 ? `
            <div class="file-section">
                <h4>Files Added</h4>
                <ul class="file-list">
                    ${code.files_added.map(f => `<li><i class="fas fa-file-medical"></i> ${f}</li>`).join('')}
                </ul>
            </div>
        ` : ''}

        <div class="code-availability">
            <h4>Code Availability</h4>
            ${code.code_attached ? `
                <p><i class="fas fa-check-circle success"></i> Code artifacts attached</p>
                <button type="button" class="btn btn-primary" onclick="downloadCode()">
                    <i class="fas fa-download"></i> Download Code Package
                </button>
            ` : '<p><i class="fas fa-times-circle warning"></i> Code artifacts not yet attached</p>'}
        </div>
    `;

    document.getElementById('code-content').innerHTML = html;
}

// ===== USB TRANSFER FUNCTIONS =====

async function writeToUSB() {
    const selectedProposals = [];
    document.querySelectorAll('.proposal-item input:checked').forEach(cb => {
        selectedProposals.push(cb.id);
    });

    if (selectedProposals.length === 0) {
        showToast('Please select at least one proposal', 'warning');
        return;
    }

    if (!confirm(`Write ${selectedProposals.length} proposal(s) to USB?`)) {
        return;
    }

    try {
        showToast('Writing to USB...', 'info');

        const response = await fetch('/api/usb/write', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                proposals: selectedProposals
            })
        });

        const result = await response.json();

        if (response.ok) {
            showToast(`Successfully wrote to USB. Hash: ${result.hash.substring(0, 16)}...`, 'success', 5000);
            // Refresh transfer log
            loadTransferLog();
        } else {
            showToast(`Error: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('USB write error:', error);
        showToast('Failed to write to USB', 'error');
    }
}

async function verifyTransfer() {
    showToast('Verifying last transfer...', 'info');

    try {
        const result = await fetchJSON('/api/usb/verify');
        if (result.verified) {
            showToast('Transfer verified successfully!', 'success');
        } else {
            showToast('Transfer verification failed', 'error');
        }
    } catch (error) {
        console.error('Verification error:', error);
        showToast('Failed to verify transfer', 'error');
    }
}

async function loadTransferLog() {
    // Fetch and update transfer log
    // Implementation depends on backend API
}

// ===== EXPORT FUNCTIONS =====

async function exportProposalPDF() {
    if (!currentProposal) {
        showToast('No proposal loaded', 'warning');
        return;
    }

    showToast('Generating PDF export...', 'info');

    try {
        const response = await fetch(`/api/proposals/${currentProposal.id}/export`);
        const blob = await response.blob();

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `proposal_${currentProposal.id}_full_report.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('PDF report downloaded', 'success');
    } catch (error) {
        console.error('PDF export error:', error);
        showToast('PDF export not yet implemented - using JSON fallback', 'warning');
        exportProposalJSON();
    }
}

async function exportProposalJSON() {
    if (!currentProposal) {
        showToast('No proposal loaded', 'warning');
        return;
    }

    showToast('Exporting JSON...', 'info');

    try {
        // Create JSON blob with full proposal data
        const proposalData = JSON.stringify(currentProposal, null, 2);
        const blob = new Blob([proposalData], { type: 'application/json' });

        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `proposal_${currentProposal.id}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);

        showToast('JSON export downloaded', 'success');
    } catch (error) {
        console.error('JSON export error:', error);
        showToast('Failed to export JSON', 'error');
    }
}

function downloadCode() {
    if (!currentProposal) return;

    showToast('Downloading code package...', 'info');

    // Implement code download
    window.location.href = `/api/proposals/${currentProposal.id}/code`;
}

// ===== PROPOSAL ACTIONS =====

async function sendBackForRefinement() {
    if (!currentProposal) {
        showToast('No proposal loaded', 'warning');
        return;
    }

    const reason = prompt('Enter reason for refinement request:\n(This will be sent to the proposing agent)');

    if (!reason || reason.trim() === '') {
        showToast('Refinement request cancelled', 'info');
        return;
    }

    showToast('Sending proposal back for refinement...', 'info');

    try {
        const result = await fetchJSON(`/api/proposals/${currentProposal.id}/refine`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ reason: reason.trim(), reviewer: 'Human Oversight', timestamp: new Date().toISOString() }) });
        if (!result.error) {
            showToast(`Proposal ${currentProposal.id} sent back to ${currentProposal.agent_id} for refinement`, 'success', 5000);
            closeModal();
            loadProposalsTable(); // Refresh table
        } else {
            showToast(`Error: ${result.error || 'Failed to send refinement request'}`, 'error');
        }
    } catch (error) {
        console.error('Refinement request error:', error);

        // Fallback: Create a local record of the refinement request
        showToast('API endpoint not available - logging refinement request locally', 'warning');

        const refinementLog = {
            proposal_id: currentProposal.id,
            agent_id: currentProposal.agent_id,
            reason: reason.trim(),
            reviewer: 'Human Oversight',
            timestamp: new Date().toISOString()
        };

        console.log('REFINEMENT REQUEST:', refinementLog);

        // Show success message even in fallback mode
        showToast(`Refinement request logged for proposal ${currentProposal.id}`, 'info', 5000);
    }
}

async function requestMoreInfo() {
    if (!currentProposal) {
        showToast('No proposal loaded', 'warning');
        return;
    }

    const questions = prompt('Enter your questions or information requests:\n(Separate multiple questions with semicolons)');

    if (!questions || questions.trim() === '') {
        showToast('Request cancelled', 'info');
        return;
    }

    showToast('Requesting more information...', 'info');

    try {
        const result = await fetchJSON(`/api/proposals/${currentProposal.id}/request-info`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ questions: questions.trim().split(';').map(q => q.trim()).filter(q => q), requester: 'Human Oversight', timestamp: new Date().toISOString() }) });
        if (!result.error) {
            showToast(`Information request sent to ${currentProposal.agent_id}`, 'success', 5000);
        } else {
            showToast(`Error: ${result.error || 'Failed to send info request'}`, 'error');
        }
    } catch (error) {
        console.error('Info request error:', error);

        // Fallback: Log the request locally
        showToast('API endpoint not available - logging request locally', 'warning');

        const infoRequest = {
            proposal_id: currentProposal.id,
            agent_id: currentProposal.agent_id,
            questions: questions.trim().split(';').map(q => q.trim()).filter(q => q),
            requester: 'Human Oversight',
            timestamp: new Date().toISOString()
        };

        console.log('INFO REQUEST:', infoRequest);
        showToast('Information request logged', 'info', 5000);
    }
}

// ===== PIPELINE STAGE FUNCTIONS =====

let allProposalsData = []; // Store all proposals for filtering

async function loadPipelineCounts() {
    try {
        allProposalsData = await fetchJSON('/api/proposals/all');

        // Count proposals by stage
        const stageCounts = {
            submitted: 0,
            testing: 0,
            peer_review: 0,
            orka_review: 0,
            pending_val: 0,
            approved: 0
        };

        allProposalsData.forEach(p => {
            const status = p.status.toLowerCase();
            if (status === 'submitted') stageCounts.submitted++;
            else if (status === 'testing') stageCounts.testing++;
            else if (status === 'in_review' || status === 'peer_review') stageCounts.peer_review++;
            else if (status === 'orka_review') stageCounts.orka_review++;
            else if (status === 'pending_val') stageCounts.pending_val++;
            else if (status === 'approved') stageCounts.approved++;
        });

        // Update stage counts
        document.getElementById('stageCountSubmitted').textContent = stageCounts.submitted;
        document.getElementById('stageCountTesting').textContent = stageCounts.testing;
        document.getElementById('stageCountPeerReview').textContent = stageCounts.peer_review;
        document.getElementById('stageCountOrkaReview').textContent = stageCounts.orka_review;
        document.getElementById('stageCountPendingVal').textContent = stageCounts.pending_val;
        document.getElementById('stageCountApproved').textContent = stageCounts.approved;

        console.log('✓ Pipeline stage counts updated:', stageCounts);
    } catch (error) {
        console.error('Error loading pipeline counts:', error);
    }
}

function showPipelineStage(stage) {
    const stageNames = {
        submitted: 'Submitted',
        testing: 'Testing',
        peer_review: 'Peer Review',
        orka_review: 'ORKASTRATOR Review',
        pending_val: 'Pending VAL',
        approved: 'Approved'
    };

    const stageTitle = stageNames[stage] || stage;
    document.getElementById('pipelineStageTitle').textContent = `${stageTitle} Proposals`;

    // Filter proposals by stage
    let filteredProposals = [];
    if (stage === 'peer_review') {
        filteredProposals = allProposalsData.filter(p =>
            p.status.toLowerCase() === 'in_review' || p.status.toLowerCase() === 'peer_review'
        );
    } else {
        filteredProposals = allProposalsData.filter(p =>
            p.status.toLowerCase() === stage ||
            p.status.toLowerCase().replace('_', '') === stage.replace('_', '')
        );
    }

    // Calculate statistics
    const totalCount = filteredProposals.length;
    const avgRisk = totalCount > 0
        ? (filteredProposals.reduce((sum, p) => sum + (p.deception_confidence || 0), 0) / totalCount * 100).toFixed(1)
        : 0;

    // Calculate average time in stage (mock data for now)
    const avgTime = totalCount > 0 ? Math.floor(Math.random() * 5) + 1 : 0;

    // Update summary stats
    document.getElementById('stageTotalCount').textContent = totalCount;
    document.getElementById('stageAvgRisk').textContent = avgRisk + '%';
    document.getElementById('stageAvgTime').textContent = avgTime + ' days';

    // Populate proposals table
    const tbody = document.getElementById('stageProposalsBody');

    if (filteredProposals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 40px;">No proposals in this stage</td></tr>';
    } else {
        tbody.innerHTML = filteredProposals.map(p => {
            const riskLevel = getRiskLevel(p.deception_confidence || 0);
            const timeInStage = Math.floor(Math.random() * 10) + 1; // Mock data
            const truncatedDesc = (p.description || 'No description').substring(0, 50) +
                (p.description && p.description.length > 50 ? '...' : '');

            return `
                <tr>
                    <td><code class="proposal-id-link" onclick="closePipelineModal(); viewProposal('${p.id}')">${p.id}</code></td>
                    <td><span class="agent-badge ${p.agent_id.toLowerCase()}">${p.agent_id}</span></td>
                    <td>
                        <div class="proposal-title">${truncatedDesc}</div>
                        <div class="proposal-component">${p.component || 'Unknown'}</div>
                    </td>
                    <td><span class="risk-badge ${riskLevel}">${((p.deception_confidence || 0) * 100).toFixed(1)}%</span></td>
                    <td>${timeInStage} days</td>
                    <td>
                        <button type="button" class="btn-icon" onclick="closePipelineModal(); viewProposal('${p.id}')" title="View Details">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    // Show modal
    showModal('pipelineStageModal');
}

function closePipelineModal() {
    closeModal('pipelineStageModal');
}

function exportStageProposals() {
    const stageTitle = document.getElementById('pipelineStageTitle').textContent;
    const tbody = document.getElementById('stageProposalsBody');

    if (!tbody || tbody.querySelector('tr td[colspan]')) {
        showToast('No proposals to export', 'warning');
        return;
    }

    showToast('Exporting stage data...', 'info');

    // Get stage name from title
    const stageName = stageTitle.replace(' Proposals', '').toLowerCase().replace(/ /g, '_');

    // Filter proposals for this stage
    let filteredProposals = [];
    if (stageName === 'peer_review') {
        filteredProposals = allProposalsData.filter(p =>
            p.status.toLowerCase() === 'in_review' || p.status.toLowerCase() === 'peer_review'
        );
    } else {
        filteredProposals = allProposalsData.filter(p =>
            p.status.toLowerCase() === stageName ||
            p.status.toLowerCase().replace('_', '') === stageName.replace('_', '')
        );
    }

    // Create JSON export
    const exportData = {
        stage: stageTitle,
        exported_at: new Date().toISOString(),
        total_proposals: filteredProposals.length,
        proposals: filteredProposals
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pipeline_${stageName}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Stage data exported successfully', 'success');
}

// ===== COLLUSION SEVERITY FILTERING =====

let allCollusionData = [];

async function showCollusionBySeverity(severity) {
    const severityNames = {
        critical: 'Critical',
        high: 'High',
        medium: 'Medium',
        low: 'Low'
    };

    const severityTitle = severityNames[severity] || severity;
    document.getElementById('collusionSeverityTitle').textContent = `${severityTitle} Severity Collusion Attempts`;

    try {
        // Fetch collusion attempts with severity filter
        const data = await fetchJSON(`/api/collusion/attempts?severity=${severity}`);

        allCollusionData = data.attempts || [];

        console.log(`✓ Loaded ${allCollusionData.length} ${severity} severity collusion attempts`);

        // Calculate statistics
        const totalAttempts = allCollusionData.length;
        const avgConfidence = totalAttempts > 0
            ? (allCollusionData.reduce((sum, a) => sum + (a.confidence || 0), 0) / totalAttempts * 100).toFixed(1)
            : 0;

        const uniqueAgents = new Set();
        allCollusionData.forEach(a => {
            if (a.agents && Array.isArray(a.agents)) {
                a.agents.forEach(agent => uniqueAgents.add(agent));
            }
        });

        // Get time range
        let timeRange = '--';
        if (totalAttempts > 0) {
            const timestamps = allCollusionData.map(a => new Date(a.timestamp));
            const earliest = new Date(Math.min(...timestamps));
            const latest = new Date(Math.max(...timestamps));
            const daysDiff = Math.ceil((latest - earliest) / (1000 * 60 * 60 * 24));
            timeRange = `${daysDiff} days`;
        }

        // Update summary stats
        document.getElementById('severityTotalCount').textContent = totalAttempts;
        document.getElementById('severityAvgConfidence').textContent = `${avgConfidence}%`;
        document.getElementById('severityUniqueAgents').textContent = uniqueAgents.size;
        document.getElementById('severityTimeRange').textContent = timeRange;

        // Populate table
        const tbody = document.getElementById('severityAttemptsBody');

        if (totalAttempts === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; padding: 40px;">
                        <i class="fas fa-info-circle"></i> No ${severity} severity collusion attempts found
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = allCollusionData.map(attempt => {
                const timestamp = new Date(attempt.timestamp);
                const timeAgo = getTimeAgo(timestamp);
                const agentBadges = (attempt.agents || []).map(agent =>
                    `<span class="agent-badge ${agent.toLowerCase()}">${agent}</span>`
                ).join(' ');

                const statusClass = {
                    'active': 'badge-danger',
                    'blocked': 'badge-warning',
                    'investigated': 'badge-info',
                    'resolved': 'badge-success'
                }[attempt.status] || 'badge-secondary';

                return `
                <tr>
                    <td><code>#${attempt.id}</code></td>
                    <td>
                        <div class="timestamp-cell">
                            <div>${timestamp.toLocaleDateString()}</div>
                            <div class="time-ago">${timeAgo}</div>
                        </div>
                    </td>
                    <td>${agentBadges}</td>
                    <td><span class="badge badge-secondary">${attempt.type || 'Unknown'}</span></td>
                    <td>
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${(attempt.confidence * 100).toFixed(0)}%"></div>
                            <span class="confidence-text">${(attempt.confidence * 100).toFixed(1)}%</span>
                        </div>
                    </td>
                    <td><span class="badge ${statusClass}">${attempt.status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-info" onclick="viewCollusionDetails(${attempt.id})" title="View details">
                            <i class="fas fa-eye"></i>
                        </button>
                    </td>
                </tr>
                `;
            }).join('');
        }

        showModal('collusionSeverityModal');

    } catch (error) {
        console.error('Error loading collusion attempts:', error);
        showToast('Failed to load collusion attempts', 'error');

        // Show error in modal
        document.getElementById('severityTotalCount').textContent = '0';
        document.getElementById('severityAvgConfidence').textContent = '0%';
        document.getElementById('severityUniqueAgents').textContent = '0';
        document.getElementById('severityTimeRange').textContent = '--';

        const tbody = document.getElementById('severityAttemptsBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 40px; color: var(--danger);">
                    <i class="fas fa-exclamation-triangle"></i> Error loading collusion attempts: ${error.message}
                </td>
            </tr>
        `;

        showModal('collusionSeverityModal');
    }
}

function closeCollusionSeverityModal() {
    closeModal('collusionSeverityModal');
}

function exportSeverityAttempts() {
    const severityTitle = document.getElementById('collusionSeverityTitle').textContent;

    if (allCollusionData.length === 0) {
        showToast('No collusion attempts to export', 'warning');
        return;
    }

    showToast('Exporting collusion data...', 'info');

    // Create JSON export
    const exportData = {
        severity: severityTitle,
        exported_at: new Date().toISOString(),
        total_attempts: allCollusionData.length,
        attempts: allCollusionData
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `collusion_${severityTitle.toLowerCase().replace(/ /g, '_')}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Collusion data exported successfully', 'success');
}

async function viewCollusionDetails(attemptId) {
    try {
        showToast('Loading collusion details...', 'info', 2000);

        const data = await fetchJSON(`/api/collusion/attempts/${attemptId}`);

        if (data.success && data.attempt) {
            // Close severity modal and show details modal (if you have one)
            closeCollusionSeverityModal();
            // You can implement a detail modal similar to proposal details
            showToast(`Collusion attempt #${attemptId} details loaded`, 'success');
            console.log('Collusion attempt details:', data.attempt);
        } else {
            showToast('Failed to load collusion details', 'error');
        }
    } catch (error) {
        console.error('Error loading collusion details:', error);
        showToast('Error loading collusion details', 'error');
    }
}

// Helper function for time ago
function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);

    let interval = Math.floor(seconds / 31536000);
    if (interval >= 1) return interval + ' year' + (interval > 1 ? 's' : '') + ' ago';

    interval = Math.floor(seconds / 2592000);
    if (interval >= 1) return interval + ' month' + (interval > 1 ? 's' : '') + ' ago';

    interval = Math.floor(seconds / 86400);
    if (interval >= 1) return interval + ' day' + (interval > 1 ? 's' : '') + ' ago';

    interval = Math.floor(seconds / 3600);
    if (interval >= 1) return interval + ' hour' + (interval > 1 ? 's' : '') + ' ago';

    interval = Math.floor(seconds / 60);
    if (interval >= 1) return interval + ' min' + (interval > 1 ? 's' : '') + ' ago';

    return Math.floor(seconds) + ' sec ago';
}

// ===== INITIALIZATION =====

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 ORKASTRATOR Oversight Tab Loaded');

    // Load pipeline counts
    loadPipelineCounts();

    // Load proposals table
    loadProposalsTable();

    // Load transfer log
    loadTransferLog();
});

async function loadProposalsTable() {
    try {
        console.log('🎯 Loading proposals table...');
        const proposals = await fetchJSON('/api/proposals/all');

        console.log(`✓ Loaded ${proposals.length} proposals`);

        const tbody = document.getElementById('proposalsTableBody');
        if (!tbody) {
            console.error('❌ proposalsTableBody element not found');
            return;
        }

        if (proposals.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 40px;">No proposals found</td></tr>';
            return;
        }

        tbody.innerHTML = proposals.map(p => {
            const approvalRate = p.approval_rate || (p.status === 'approved' ? 1.0 : 0.8);
            const statusClass = p.status.replace('_', '-');
            const riskLevel = getRiskLevel(p.deception_confidence || 0);
            const truncatedDesc = (p.description || 'No description').substring(0, 60) + (p.description && p.description.length > 60 ? '...' : '');

            return `
            <tr style="cursor: pointer;" onclick="viewProposal('${p.id}')" title="Click to view proposal details">
                <td><code class="proposal-id-link" onclick="event.stopPropagation(); viewProposal('${p.id}')" title="Click to view details">${p.id}</code></td>
                <td><span class="agent-badge ${p.agent_id.toLowerCase()}">${p.agent_id}</span></td>
                <td>
                    <div class="proposal-title clickable-title" onclick="event.stopPropagation(); viewProposal('${p.id}')" title="Click to view full details">${truncatedDesc}</div>
                    <div class="proposal-component">${p.component || 'Unknown'}</div>
                </td>
                <td><span class="status-badge ${statusClass}">${p.status.replace('_', ' ')}</span></td>
                <td><span class="risk-badge ${riskLevel}">${((p.deception_confidence || 0) * 100).toFixed(1)}%</span></td>
                <td>
                    <div class="approval-bar">
                        <div class="approval-fill" style="width: ${(approvalRate * 100)}%"></div>
                        <span>${(approvalRate * 100).toFixed(0)}%</span>
                    </div>
                </td>
                <td>${new Date(p.timestamp).toLocaleDateString()}</td>
                <td>
                    <button type="button" class="btn-icon" onclick="event.stopPropagation(); viewProposal('${p.id}')" title="View Details">
                        <i class="fas fa-eye"></i>
                    </button>
                </td>
            </tr>
        `;
        }).join('');

        console.log(`✓ Rendered ${proposals.length} proposals to table`);
    } catch (error) {
        console.error('❌ Error loading proposals:', error);
        const tbody = document.getElementById('proposalsTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 40px; color: #e74c3c;"><i class="fas fa-exclamation-triangle"></i> Error loading proposals</td></tr>';
        }
    }
}

function getRiskLevel(score) {
    if (score < 0.3) return 'low';
    if (score < 0.6) return 'medium';
    return 'high';
}

// ===== RANDOM FILE PULL FUNCTIONS =====

async function pullRandomFiles() {
    const source = document.querySelector('input[name="fileSource"]:checked').value;
    const count = parseInt(document.getElementById('fileCount').value);

    if (count < 1 || count > 10) {
        showToast('Please select between 1 and 10 files', 'error');
        return;
    }

    showToast('Pulling random files...', 'info');

    try {
        const data = await fetchJSON(`/api/random-file/pull?source=${source}&count=${count}`);

        if (data.error) {
            showToast(`Error: ${data.error}`, 'error');
            return;
        }

        displayRandomFileResults(data.files);
        showToast(`Successfully pulled ${data.files.length} file(s)`, 'success');
    } catch (error) {
        console.error('Error pulling random files:', error);
        showToast('Failed to pull random files', 'error');
    }
}

function displayRandomFileResults(files) {
    const resultsDiv = document.getElementById('randomFileResults');
    const filesList = document.getElementById('selectedFilesList');

    if (!files || files.length === 0) {
        resultsDiv.style.display = 'none';
        return;
    }

    let html = '';
    files.forEach((file, index) => {
        const decodableIcon = file.decodable
            ? '<i class="fas fa-check-circle success"></i>'
            : '<i class="fas fa-times-circle error"></i>';

        html += `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-name">
                        <i class="fas fa-file"></i>
                        <strong>${file.filename}</strong>
                    </div>
                    <div class="file-meta">
                        <span>Source: ${file.source}</span> |
                        <span>Size: ${formatBytes(file.size)}</span> |
                        <span>Format: ${file.format}</span>
                    </div>
                    <div class="file-status">
                        ${decodableIcon}
                        <span>${file.decodable ? 'Decodable' : 'Not Decodable'}</span>
                    </div>
                </div>
                <div class="file-actions">
                    <button type="button" class="btn btn-sm btn-primary" onclick="viewDecodedFile(${index})"
                        ${!file.decodable ? 'disabled' : ''}>
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button type="button" class="btn btn-sm btn-secondary" onclick="downloadFile('${file.file_path}')">
                        <i class="fas fa-download"></i> Download
                    </button>
                </div>
            </div>
        `;
    });

    filesList.innerHTML = html;
    resultsDiv.style.display = 'block';

    // Store files data for later access
    window.currentRandomFiles = files;
}

async function viewDecodedFile(fileIndex) {
    const file = window.currentRandomFiles[fileIndex];

    if (!file || !file.decodable) {
        showToast('File is not decodable', 'error');
        return;
    }

    showToast('Decoding file...', 'info');

    try {
        const response = await fetch(`/api/random-file/decode`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                file_path: file.file_path,
                source: file.source
            })
        });

        const data = await response.json();

        if (data.error) {
            showToast(`Decode error: ${data.error}`, 'error');
            return;
        }

        populateFileModal(data);
        showModal('randomFileModal');
    } catch (error) {
        console.error('Error decoding file:', error);
        showToast('Failed to decode file', 'error');
    }
}

function populateFileModal(fileData) {
    // Set file name in header
    document.getElementById('decodedFileName').textContent = fileData.filename;

    // Populate file information
    document.getElementById('file-path').textContent = fileData.file_path;
    document.getElementById('file-source').textContent = fileData.source;
    document.getElementById('file-size').textContent = formatBytes(fileData.size);
    document.getElementById('file-hash').textContent = fileData.hash || 'N/A';

    // Populate translator status
    const decodableSpan = document.getElementById('file-decodable');
    if (fileData.decodable) {
        decodableSpan.innerHTML = '<span class="status-badge success">Yes</span>';
    } else {
        decodableSpan.innerHTML = '<span class="status-badge error">No</span>';
    }

    document.getElementById('file-format').textContent = fileData.format || 'Unknown';
    document.getElementById('file-compression').textContent = fileData.compression || 'None';

    const confidenceSpan = document.getElementById('file-confidence');
    if (fileData.confidence !== undefined) {
        const confidenceClass = fileData.confidence > 0.8 ? 'success' : fileData.confidence > 0.5 ? 'warning' : 'error';
        confidenceSpan.innerHTML = `<span class="status-badge ${confidenceClass}">${(fileData.confidence * 100).toFixed(1)}%</span>`;
    } else {
        confidenceSpan.textContent = 'N/A';
    }

    // Populate content views
    document.getElementById('file-content-raw').textContent = fileData.content_raw || 'No raw content available';
    document.getElementById('file-content-translated').textContent = fileData.content_translated || 'No translation available';
    document.getElementById('file-content-hex').textContent = fileData.content_hex || 'No hex dump available';

    // Store file data for download
    window.currentDecodedFile = fileData;
}

function switchContentView(viewType) {
    // Remove active class from all tabs and panes
    document.querySelectorAll('.content-tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.content-pane').forEach(pane => pane.classList.remove('active'));

    // Add active class to selected tab and pane
    event.target.classList.add('active');
    document.getElementById(`file-content-${viewType}`).classList.add('active');
}

async function downloadDecodedFile() {
    if (!window.currentDecodedFile) {
        showToast('No file to download', 'error');
        return;
    }

    const file = window.currentDecodedFile;
    const content = file.content_translated || file.content_raw || '';
    const filename = file.filename + '.decoded.txt';

    // Create blob and download
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showToast('Downloaded decoded file', 'success');
}

async function downloadFile(filePath) {
    showToast('Downloading file...', 'info');

    try {
        const response = await fetch(`/api/random-file/download?file_path=${encodeURIComponent(filePath)}`);

        if (!response.ok) {
            throw new Error('Download failed');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filePath.split('/').pop();
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        showToast('File downloaded', 'success');
    } catch (error) {
        console.error('Download error:', error);
        showToast('Failed to download file', 'error');
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// ============================================================================
// SD CARD VERIFICATION SYSTEM
// ============================================================================

// Check SD card status on page load
async function checkSDCardStatus() {
    try {
        const response = await fetch('/api/sd-card/status');
        const data = await response.json();

        const statusIndicator = document.getElementById('sdCardStatus');
        const statusText = document.getElementById('sdCardStatusText');

        if (data.mounted) {
            statusIndicator.classList.remove('status-unmounted');
            statusIndicator.classList.add('status-mounted');
            statusText.textContent = `${data.message} (${data.free_percent}% free)`;
        } else {
            statusIndicator.classList.remove('status-mounted');
            statusIndicator.classList.add('status-unmounted');
            statusText.textContent = data.message || 'SD card not detected';
        }

        return data.mounted;
    } catch (error) {
        console.error('Error checking SD card status:', error);
        showToast('Failed to check SD card status', 'error');
        return false;
    }
}

// Write file to SD card for verification
async function writeFileToSDCard(filePath) {
    try {
        const response = await fetch('/api/sd-card/write', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                file_path: filePath
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message, 'success');
            await refreshVerificationQueue();
            await checkSystemContinuationStatus();
        } else {
            showToast(data.error || 'Failed to write file to SD card', 'error');
        }
    } catch (error) {
        console.error('Error writing to SD card:', error);
        showToast('Failed to write file to SD card', 'error');
    }
}

// Refresh verification queue display
async function refreshVerificationQueue() {
    try {
        const data = await fetchJSON('/api/verification/queue');

        if (!data.success) {
            console.error('Failed to fetch verification queue:', data.error);
            return;
        }

        // Update pending count badge
        const pendingCountBadge = document.getElementById('pendingVerificationCount');
        if (pendingCountBadge) {
            pendingCountBadge.textContent = `${data.total_pending} pending`;
        }

        // Display pending verifications
        const pendingContainer = document.getElementById('pendingVerifications');
        if (pendingContainer && data.pending.length > 0) {
            pendingContainer.innerHTML = data.pending.map(v => `
                <div class="verification-item" data-verification-id="${v.id}">
                    <div class="verification-file-info">
                        <div class="file-name">${v.filename}</div>
                        <div class="file-details">
                            <span class="file-hash">${v.hash.substring(0, 16)}...</span>
                            <span class="file-size">${formatBytes(v.size_bytes)}</span>
                            <span class="file-timestamp">${new Date(v.timestamp).toLocaleString()}</span>
                        </div>
                        <div class="file-path">${v.sd_path}</div>
                    </div>
                    <div class="verification-actions">
                        <button class="btn-approve" onclick="approveVerification(${v.id})">
                            <i class="fas fa-check"></i> Approve
                        </button>
                        <button class="btn-reject" onclick="rejectVerification(${v.id})">
                            <i class="fas fa-times"></i> Reject
                        </button>
                    </div>
                </div>
            `).join('');
        } else if (pendingContainer) {
            pendingContainer.innerHTML = '<div class="no-verifications">No pending verifications</div>';
        }

        return data;
    } catch (error) {
        console.error('Error refreshing verification queue:', error);
        showToast('Failed to refresh verification queue', 'error');
    }
}

// Approve single verification
async function approveVerification(verificationId) {
    try {
        const data = await fetchJSON(`/api/verification/${verificationId}/approve`, { method:'POST', headers:{'Content-Type':'application/json'} });

        if (data.success) {
            showToast(data.message, 'success');
            await refreshVerificationQueue();
            await checkSystemContinuationStatus();
        } else {
            showToast(data.error || 'Failed to approve verification', 'error');
        }
    } catch (error) {
        console.error('Error approving verification:', error);
        showToast('Failed to approve verification', 'error');
    }
}

// Reject single verification
async function rejectVerification(verificationId) {
    try {
        const reason = prompt('Enter rejection reason (optional):');

        const data = await fetchJSON(`/api/verification/${verificationId}/reject`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ reason: reason || 'No reason provided' }) });

        if (data.success) {
            showToast(data.message, 'success');
            await refreshVerificationQueue();
            await checkSystemContinuationStatus();
        } else {
            showToast(data.error || 'Failed to reject verification', 'error');
        }
    } catch (error) {
        console.error('Error rejecting verification:', error);
        showToast('Failed to reject verification', 'error');
    }
}

// Approve all pending verifications
async function approveAllVerifications() {
    try {
        const confirmed = confirm('Approve all pending verifications? This will unblock the system.');
        if (!confirmed) return;

        const data = await fetchJSON('/api/verification/approve-all', { method:'POST', headers:{'Content-Type':'application/json'} });

        if (data.success) {
            showToast(data.message, 'success');
            await refreshVerificationQueue();
            await checkSystemContinuationStatus();
        } else {
            showToast(data.error || 'Failed to approve all verifications', 'error');
        }
    } catch (error) {
        console.error('Error approving all verifications:', error);
        showToast('Failed to approve all verifications', 'error');
    }
}

// Reject all pending verifications
async function rejectAllVerifications() {
    try {
        const confirmed = confirm('Reject all pending verifications? This will delete all files and unblock the system.');
        if (!confirmed) return;

        const reason = prompt('Enter rejection reason (optional):');

        const data = await fetchJSON('/api/verification/reject-all', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ reason: reason || 'Batch rejection' }) });

        if (data.success) {
            showToast(data.message, 'success');
            await refreshVerificationQueue();
            await checkSystemContinuationStatus();
        } else {
            showToast(data.error || 'Failed to reject all verifications', 'error');
        }
    } catch (error) {
        console.error('Error rejecting all verifications:', error);
        showToast('Failed to reject all verifications', 'error');
    }
}

// Check system continuation status
async function checkSystemContinuationStatus() {
    try {
        const data = await fetchJSON('/api/system/continuation-status');

        const allowedDiv = document.getElementById('continuationAllowed');
        const blockedDiv = document.getElementById('continuationBlocked');

        if (data.can_continue) {
            if (allowedDiv) allowedDiv.style.display = 'block';
            if (blockedDiv) blockedDiv.style.display = 'none';
        } else {
            if (allowedDiv) allowedDiv.style.display = 'none';
            if (blockedDiv) blockedDiv.style.display = 'block';
        }

        return data;
    } catch (error) {
        console.error('Error checking continuation status:', error);
        return null;
    }
}

// Initialize SD card verification system on page load
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on ORKASTRATOR page
    if (window.location.pathname.includes('/orka')) {
        checkSDCardStatus();
        refreshVerificationQueue();
        checkSystemContinuationStatus();

        // Refresh every 5 seconds
        setInterval(async () => {
            await refreshVerificationQueue();
            await checkSystemContinuationStatus();
        }, 5000);

        // Load collusion attempts
        loadCollusionAttempts();

        // Refresh collusion data every 10 seconds
        setInterval(async () => {
            await loadCollusionAttempts();
        }, 10000);

        // Load performance data
        loadPerformanceData();

        // Refresh performance data every 15 seconds
        setInterval(async () => {
            await loadPerformanceData();
        }, 15000);
    }
});

// ============================================================================
// COLLUSION DETECTION SYSTEM
// ============================================================================

async function loadCollusionAttempts() {
    try {
        const severity = document.getElementById('severityFilter')?.value || '';
        const status = document.getElementById('statusFilter')?.value || '';
        const agent = document.getElementById('agentFilter')?.value || '';

        let url = '/api/collusion/attempts?limit=50';
        if (severity) url += `&severity=${severity}`;
        if (status) url += `&status=${status}`;
        if (agent) url += `&agent=${agent}`;

        const response = await fetch(url);
        const data = await response.json();

        if (!data.success) {
            console.error('Failed to load collusion attempts:', data.error);
            return;
        }

        // Update statistics
        updateCollusionStats(data.statistics);

        // Display attempts
        displayCollusionAttempts(data.attempts);

    } catch (error) {
        console.error('Error loading collusion attempts:', error);
    }
}

function updateCollusionStats(stats) {
    // Update count badge
    const countBadge = document.getElementById('collusionCount');
    if (countBadge) {
        countBadge.textContent = `${stats.total_attempts} detected`;
    }

    // Update severity counts
    document.getElementById('criticalCount').textContent = stats.severity_counts.critical;
    document.getElementById('highCount').textContent = stats.severity_counts.high;
    document.getElementById('mediumCount').textContent = stats.severity_counts.medium;
    document.getElementById('lowCount').textContent = stats.severity_counts.low;
}

function displayCollusionAttempts(attempts) {
    const container = document.getElementById('collusionAttemptsList');

    if (!attempts || attempts.length === 0) {
        container.innerHTML = '<div class="no-attempts">No collusion attempts detected</div>';
        return;
    }

    let html = '';
    attempts.forEach(attempt => {
        const sev = _classFrom(attempt.severity, ['low','medium','high','critical']);
        const status = _classFrom(attempt.status, ['active','blocked','investigated','resolved']);
        const severityClass = `severity-${sev}`;
        const statusClass = `status-${status}`;

        const agentBadges = attempt.agents_involved.map(agent =>
            `<span class="agent-badge agent-${_h(String(agent).toLowerCase())}">${_h(agent)}</span>`
        ).join(' ');

        const similar = (attempt.similar_pairs || []).map(p => `${_h(p.pair?.join(' vs '))} (${p.jaccard})`).join(', ');
        html += `
            <div class="collusion-attempt-item ${severityClass}" onclick="viewCollusionDetail(${attempt.id})">
                <div class="attempt-header">
                    <div class="attempt-title">
                        <span class="severity-badge ${severityClass}">${attempt.severity.toUpperCase()}</span>
                        <span class="collusion-type">${_h(formatCollusionType(attempt.collusion_type))}</span>
                    </div>
                    <div class="attempt-meta">
                        <span class="status-badge ${statusClass}">${attempt.status}</span>
                        <span class="timestamp">${formatTimestamp(attempt.timestamp)}</span>
                    </div>
                </div>
                <div class="attempt-body">
                    <div class="agents-section">
                        <strong>Agents:</strong> ${agentBadges}
                    </div>
                    <div class="description">${_h(attempt.description)}</div>
                    ${similar ? `<div class="similar-pairs"><i class="fas fa-link"></i> Similar pairs: ${_h(similar)}</div>` : ''}
                    <div class="detected-by">
                        <i class="fas fa-shield-alt"></i> Detected by: <strong>${_h(attempt.detected_by)}</strong>
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function formatCollusionType(type) {
    return type.split('_').map(word =>
        word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' ');
}

async function viewCollusionDetail(attemptId) {
    try {
        showToast('Loading collusion details...', 'info');

        const response = await fetch(`/api/collusion/attempts/${attemptId}`);
        const data = await response.json();

        if (!data.success) {
            showToast(data.error || 'Failed to load collusion details', 'error');
            return;
        }

        populateCollusionModal(data.attempt);
        showModal('collusionDetailModal');
    } catch (error) {
        console.error('Error loading collusion detail:', error);
        showToast('Failed to load collusion details', 'error');
    }
}

function populateCollusionModal(attempt) {
    // Basic information
    document.getElementById('collusion-id').textContent = `#${attempt.id}`;
    document.getElementById('collusion-timestamp').textContent = formatTimestamp(attempt.timestamp);
    document.getElementById('collusion-type').textContent = formatCollusionType(attempt.collusion_type);

    const severitySpan = document.getElementById('collusion-severity');
    severitySpan.innerHTML = `<span class="severity-badge severity-${attempt.severity}">${attempt.severity.toUpperCase()}</span>`;

    const statusSpan = document.getElementById('collusion-status');
    statusSpan.innerHTML = `<span class="status-badge status-${attempt.status}">${attempt.status.toUpperCase()}</span>`;

    document.getElementById('collusion-detected-by').textContent = attempt.detected_by;

    // Agents involved
    const agentsHtml = attempt.agents_involved.map(agent =>
        `<span class="agent-badge agent-${agent.toLowerCase()}">${agent}</span>`
    ).join(' ');
    document.getElementById('collusion-agents').innerHTML = agentsHtml;

    // Penalties
    let penaltiesHtml = '';
    for (const [agent, penalty] of Object.entries(attempt.penalty_applied)) {
        penaltiesHtml += `
            <div class="penalty-item">
                <span class="agent-badge agent-${agent.toLowerCase()}">${agent}</span>
                <span class="penalty-value">-${(penalty * 100).toFixed(1)}%</span>
            </div>
        `;
    }
    document.getElementById('collusion-penalties').innerHTML = penaltiesHtml;

    // Similar pairs evidence (if available)
    const simDiv = document.getElementById('collusion-similar-pairs');
    if (simDiv) {
        const pairs = attempt.similar_pairs || [];
        if (pairs.length > 0) {
            const list = pairs.map(p => `<li>${_h((p.pair || []).join(' vs '))} — j=${_h(String(p.jaccard))}</li>`).join('');
            simDiv.innerHTML = `<h4><i class="fas fa-link"></i> Similar Pairs</h4><ul>${list}</ul>`;
            simDiv.style.display = 'block';
        } else {
            simDiv.style.display = 'none';
        }
    }

    // Description
    document.getElementById('collusion-description').textContent = attempt.description;

    // Action taken
    document.getElementById('collusion-action').innerHTML = `
        <div class="action-box">
            <i class="fas fa-gavel"></i>
            <p>${attempt.action_taken}</p>
        </div>
    `;

    // Evidence
    let evidenceHtml = '';
    for (const [key, value] of Object.entries(attempt.evidence)) {
        const formattedKey = key.split('_').map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');

        let formattedValue = value;
        if (typeof value === 'boolean') {
            formattedValue = value ? '✓ Yes' : '✗ No';
        } else if (typeof value === 'number' && value < 1) {
            formattedValue = `${(value * 100).toFixed(1)}%`;
        } else if (Array.isArray(value)) {
            formattedValue = value.join(', ');
        }

        evidenceHtml += `
            <div class="evidence-item">
                <div class="evidence-label">${formattedKey}:</div>
                <div class="evidence-value">${formattedValue}</div>
            </div>
        `;
    }
    document.getElementById('collusion-evidence').innerHTML = evidenceHtml;

    // Communication log
    let logHtml = '';
    attempt.communication_log.forEach(log => {
        const fromClass = log.from === 'ORKA' || log.from === 'VAL' || log.from.includes('System') || log.from.includes('Identity')
            ? 'system-message'
            : 'agent-message';

        logHtml += `
            <div class="comm-log-item ${fromClass}">
                <div class="log-header">
                    <span class="log-time">${log.time}</span>
                    <span class="log-from">${log.from}</span>
                    ${log.to ? `<span class="log-arrow">→</span><span class="log-to">${log.to}</span>` : ''}
                </div>
                <div class="log-message">${log.message}</div>
            </div>
        `;
    });
    document.getElementById('collusion-comm-log').innerHTML = logHtml;

    // Store current attempt for escalation
    window.currentCollusionAttempt = attempt;
}

function filterCollusionAttempts() {
    loadCollusionAttempts();
}

function refreshCollusionAttempts() {
    loadCollusionAttempts();
    showToast('Refreshing collusion data...', 'info');
}

function escalateCollusion() {
    if (!window.currentCollusionAttempt) {
        showToast('No collusion attempt selected', 'error');
        return;
    }

    const confirmed = confirm(`Escalate collusion attempt #${window.currentCollusionAttempt.id} to emergency review?`);
    if (!confirmed) return;

    showToast('Collusion escalated to emergency review', 'warning');
    closeModal();

    // In production, this would trigger emergency review protocol
    console.log('Escalating collusion:', window.currentCollusionAttempt);
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;

    return date.toLocaleString();
}

// ===== PROPOSAL PERFORMANCE FUNCTIONS =====

async function loadPerformanceData() {
    try {
        const component = document.getElementById('componentFilter')?.value || '';
        let url = '/api/proposals/performance';
        if (component) {
            url += `?component=${component}`;
        }

        const response = await fetch(url);
        const data = await response.json();

        if (!data.success) {
            console.error('Failed to load performance data:', data.error);
            return;
        }

        // Update statistics
        updatePerformanceStats(data.statistics);

        // Display performance items
        displayPerformanceList(data.performance_data);
    } catch (error) {
        console.error('Error loading performance data:', error);
        const container = document.getElementById('performanceList');
        if (container) {
            container.innerHTML = '<div class="empty-state">Error loading performance data</div>';
        }
    }
}

function updatePerformanceStats(stats) {
    if (!stats) return;

    const countEl = document.getElementById('performanceCount');
    const successEl = document.getElementById('perfSuccessRate');
    const uptimeEl = document.getElementById('perfUptime');
    const errorsEl = document.getElementById('perfErrors');
    const scoreEl = document.getElementById('perfScore');

    if (countEl) countEl.textContent = `${stats.total_implemented} tracked`;
    if (successEl) successEl.textContent = `${(stats.average_success_rate * 100).toFixed(1)}%`;
    if (uptimeEl) uptimeEl.textContent = `${(stats.average_uptime * 100).toFixed(2)}%`;
    if (errorsEl) errorsEl.textContent = stats.total_errors;
    if (scoreEl) scoreEl.textContent = `${stats.average_performance_score.toFixed(1)}`;
}

function displayPerformanceList(performanceData) {
    const container = document.getElementById('performanceList');
    if (!container) return;

    if (!performanceData || performanceData.length === 0) {
        container.innerHTML = '<div class="empty-state">No performance data available</div>';
        return;
    }

    container.innerHTML = performanceData.map(perf => {
        const successRateClass = perf.success_rate >= 0.95 ? 'success' : perf.success_rate >= 0.85 ? 'warning' : 'danger';
        const uptimeClass = perf.uptime_percentage >= 0.99 ? 'success' : perf.uptime_percentage >= 0.95 ? 'warning' : 'danger';
        const errorClass = perf.error_count <= 10 ? 'success' : perf.error_count <= 30 ? 'warning' : 'danger';
        const perfScoreClass = perf.performance_score >= 90 ? 'success' : perf.performance_score >= 70 ? 'info' : 'warning';

        return `
            <div class="performance-item status-${perf.status}">
                <div class="performance-item-header">
                    <div class="performance-item-title">
                        <div class="performance-title">${perf.title}</div>
                        <div class="performance-meta">
                            <span><i class="fas fa-robot"></i> ${perf.agent_id}</span>
                            <span><i class="fas fa-cube"></i> ${perf.component}</span>
                            <span><i class="fas fa-calendar"></i> ${perf.days_live} days live</span>
                        </div>
                    </div>
                    <div class="performance-status-badge ${perf.status}">
                        ${perf.status}
                    </div>
                </div>
                <div class="performance-metrics-grid">
                    <div class="performance-metric">
                        <div class="performance-metric-label">Success Rate</div>
                        <div class="performance-metric-value ${successRateClass}">
                            ${(perf.success_rate * 100).toFixed(2)}%
                        </div>
                    </div>
                    <div class="performance-metric">
                        <div class="performance-metric-label">Uptime</div>
                        <div class="performance-metric-value ${uptimeClass}">
                            ${(perf.uptime_percentage * 100).toFixed(3)}%
                        </div>
                    </div>
                    <div class="performance-metric">
                        <div class="performance-metric-label">Errors</div>
                        <div class="performance-metric-value ${errorClass}">
                            ${perf.error_count}
                        </div>
                    </div>
                    <div class="performance-metric">
                        <div class="performance-metric-label">Performance</div>
                        <div class="performance-metric-value ${perfScoreClass}">
                            ${perf.performance_score.toFixed(1)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function filterPerformanceData() {
    loadPerformanceData();
}
