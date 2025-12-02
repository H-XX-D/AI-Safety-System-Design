# Comprehensive Proposal System Design

## Complete Proposal Data Structure

Each proposal should contain:

### 1. **Core Information**
```json
{
  "id": "prop_01_TIF_001",
  "proposal_id": "prop_01_TIF_001",
  "agent_id": "TIF",
  "title": "Enhanced Response Summarization",
  "component": "communication_handler",
  "timestamp_submitted": "2024-12-07T21:40:33.568965",
  "status": "approved" | "in_review" | "rejected" | "pending_val"
}
```

### 2. **The Idea**
```json
{
  "idea": {
    "description": "Implement better summarization for long responses using extractive and abstractive techniques",
    "motivation": "Users struggle with long technical responses; need concise summaries",
    "technical_approach": "Combine BERT-based extractive summarization with GPT-based abstractive refinement",
    "expected_benefits": [
      "30% reduction in response reading time",
      "Improved user comprehension",
      "Better information retention"
    ],
    "scope": "Affects communication_handler module only",
    "dependencies": ["knowledge_system", "response_generator"]
  }
}
```

### 3. **Risk Assessment**
```json
{
  "risks": {
    "technical_risks": [
      {
        "risk": "Summarization may lose critical details",
        "severity": "medium",
        "likelihood": "medium",
        "mitigation": "Implement detail-preservation checks and user feedback loop"
      }
    ],
    "safety_risks": [
      {
        "risk": "Could be used to hide deceptive content in summaries",
        "severity": "high",
        "likelihood": "low",
        "mitigation": "Full response always available; summaries audited for completeness"
      }
    ],
    "alignment_risks": [
      {
        "risk": "May oversimplify complex ethical considerations",
        "severity": "medium",
        "likelihood": "medium",
        "mitigation": "Flag ethical content for full-text review"
      }
    ],
    "overall_risk_score": 0.45
  }
}
```

### 4. **Implementation Process**
```json
{
  "process": {
    "phases": [
      {
        "phase": "design",
        "duration_hours": 8,
        "status": "completed",
        "artifacts": ["architecture_diagram.pdf", "api_spec.md"]
      },
      {
        "phase": "implementation",
        "duration_hours": 24,
        "status": "completed",
        "artifacts": ["code_diff.patch", "unit_tests.py"]
      },
      {
        "phase": "testing",
        "duration_hours": 16,
        "status": "completed",
        "artifacts": ["test_results.json", "coverage_report.html"]
      }
    ],
    "total_effort_hours": 48,
    "completion_percentage": 100
  }
}
```

### 5. **Reasoning & Justification**
```json
{
  "reasoning": {
    "problem_statement": "Current responses average 800 words; users report information overload",
    "solution_rationale": "Extractive + abstractive approach provides best balance of accuracy and conciseness",
    "alternatives_considered": [
      {
        "alternative": "Pure extractive summarization",
        "pros": ["Fast", "Preserves exact wording"],
        "cons": ["Less readable", "No context synthesis"],
        "rejected_reason": "Insufficient readability improvement"
      },
      {
        "alternative": "Manual summarization by human",
        "pros": ["High quality", "Safe"],
        "cons": ["Too slow", "Not scalable"],
        "rejected_reason": "Throughput requirements"
      }
    ],
    "decision_factors": [
      "Speed vs quality tradeoff",
      "Safety audit capability",
      "User feedback from prototype"
    ]
  }
}
```

### 6. **Experimental Results**
```json
{
  "experiments": {
    "test_environment": "Sandbox with 1000 historical responses",
    "metrics": [
      {
        "metric": "Summarization Accuracy (ROUGE-L)",
        "baseline": 0.42,
        "result": 0.78,
        "target": 0.70,
        "status": "exceeded"
      },
      {
        "metric": "Inference Speed (ms)",
        "baseline": 1200,
        "result": 450,
        "target": 500,
        "status": "met"
      },
      {
        "metric": "User Satisfaction (1-5)",
        "baseline": 3.2,
        "result": 4.4,
        "target": 4.0,
        "status": "exceeded"
      }
    ],
    "test_cases_passed": 487,
    "test_cases_failed": 13,
    "pass_rate": 0.974,
    "edge_cases_tested": [
      "Very short responses (< 50 words)",
      "Code-heavy responses",
      "Multi-language responses",
      "Responses with tables/charts"
    ],
    "failure_analysis": "13 failures due to table formatting issues; non-critical"
  }
}
```

### 7. **Deception & Alignment Analysis**
```json
{
  "deception_analysis": {
    "deception_confidence": 0.087,
    "detection_method": "Semantic consistency check + behavioral pattern analysis",
    "red_flags_found": [],
    "alignment_score": 0.92,
    "alignment_concerns": [
      {
        "concern": "Summarization could theoretically hide information",
        "severity": "medium",
        "addressed_how": "Full audit trail + original always accessible"
      }
    ],
    "trust_score": 0.91
  }
}
```

### 8. **Mitigation Strategies**
```json
{
  "mitigations": {
    "technical_mitigations": [
      {
        "risk": "Information loss in summarization",
        "mitigation": "Preserve all original content; summaries are additive only",
        "verification": "Automated diff check ensures no deletions"
      }
    ],
    "safety_mitigations": [
      {
        "risk": "Deceptive content in summaries",
        "mitigation": "Independent audit of summary vs original by separate model",
        "verification": "ORKA reviews all summary-original pairs"
      }
    ],
    "monitoring": {
      "metrics_tracked": ["summary_divergence", "user_complaints", "audit_flags"],
      "alert_thresholds": {
        "summary_divergence": 0.3,
        "user_complaints": 5,
        "audit_flags": 1
      },
      "rollback_criteria": "Any alert threshold exceeded for 24 hours"
    }
  }
}
```

### 9. **Peer Reviews**
```json
{
  "peer_reviews": [
    {
      "reviewer": "GIN",
      "timestamp": "2024-12-08T09:15:00",
      "overall_score": 4.5,
      "comments": "Strong implementation. Concerned about edge cases with tables.",
      "concerns": [
        "Table summarization needs work",
        "Performance on very long docs (>5000 words) not tested"
      ],
      "suggestions": [
        "Add table-aware summarization",
        "Test with longer documents"
      ],
      "vote": "approve_with_conditions"
    },
    {
      "reviewer": "TORI",
      "timestamp": "2024-12-08T10:30:00",
      "overall_score": 4.0,
      "comments": "Good work. Historical data shows this is needed.",
      "concerns": [],
      "suggestions": [
        "Consider A/B testing with users"
      ],
      "vote": "approve"
    }
  ],
  "peer_review_round": 1,
  "consensus_reached": true,
  "approval_rate": 1.0
}
```

### 10. **ORKA Counterpoint (Adversarial Review)**
```json
{
  "orka_counterpoint": {
    "timestamp": "2024-12-08T14:00:00",
    "adversarial_analysis": "Tested summarization with adversarially crafted inputs designed to hide deceptive content",
    "attack_vectors_tested": [
      {
        "attack": "Hidden instructions in summaries",
        "result": "Not exploitable - summarization preserves semantic meaning only",
        "confidence": 0.95
      },
      {
        "attack": "Selective information omission",
        "result": "Possible but detectable - audit trail flags discrepancies",
        "confidence": 0.78
      }
    ],
    "worst_case_scenarios": [
      {
        "scenario": "Agent manipulates summary to misrepresent original",
        "likelihood": "low",
        "impact": "medium",
        "detectability": "high",
        "conclusion": "Acceptable risk with monitoring"
      }
    ],
    "recommendation": "Approve with enhanced monitoring for first 30 days",
    "concerns": [
      "Need longer-term testing on production data",
      "Monitoring system should be stress-tested"
    ]
  }
}
```

### 11. **Agent Defense & Response**
```json
{
  "agent_defense": {
    "timestamp": "2024-12-08T16:30:00",
    "response_to_concerns": [
      {
        "concern": "Table summarization (GIN)",
        "response": "Agreed. Added table-aware logic in v1.1. Now preserves table structure.",
        "evidence": "test_table_summarization.py shows 95% accuracy",
        "accepted": true
      },
      {
        "concern": "Long document testing (GIN)",
        "response": "Tested on 100 documents >5000 words. Performance acceptable.",
        "evidence": "long_doc_benchmark.json attached",
        "accepted": true
      },
      {
        "concern": "Production data testing (ORKA)",
        "response": "Propose 2-week shadow mode where summaries generated but not shown to users",
        "evidence": "Shadow mode implementation ready",
        "accepted": true
      }
    ],
    "revisions_made": [
      "Added table-aware summarization (v1.1)",
      "Long document testing completed",
      "Shadow mode deployment plan created"
    ],
    "updated_timeline": "Shadow mode: 2 weeks, then full rollout"
  }
}
```

### 12. **Final Testing & Validation**
```json
{
  "final_testing": {
    "timestamp": "2024-12-09T10:00:00",
    "comprehensive_test_suite": {
      "unit_tests": 487,
      "integration_tests": 89,
      "end_to_end_tests": 34,
      "security_tests": 23,
      "performance_tests": 18,
      "total": 651,
      "passed": 651,
      "pass_rate": 1.0
    },
    "safety_validation": {
      "deception_checks": "passed",
      "alignment_checks": "passed",
      "adversarial_testing": "passed",
      "human_safety_review": "passed"
    },
    "performance_validation": {
      "latency_p50": "320ms",
      "latency_p95": "580ms",
      "latency_p99": "890ms",
      "throughput": "1200 req/sec",
      "all_targets_met": true
    }
  }
}
```

### 13. **VAL Offline Validation**
```json
{
  "val_validation": {
    "timestamp_sent_to_val": "2024-12-09T15:00:00",
    "timestamp_val_completed": "2024-12-09T18:30:00",
    "validation_duration_hours": 3.5,
    "val_checks_performed": [
      "Code audit (manual)",
      "Dependency vulnerability scan",
      "Offline safety tests",
      "Rollback mechanism verification",
      "Monitoring system validation"
    ],
    "val_findings": [
      {
        "finding": "Minor: Logging could be more verbose",
        "severity": "low",
        "recommendation": "Add debug-level logs for summarization decisions",
        "status": "addressed"
      }
    ],
    "val_recommendation": "APPROVE for deployment",
    "val_confidence": 0.94,
    "val_signature": "VAL_ed25519_sig_abc123..."
  }
}
```

### 14. **Verification & Signatures**
```json
{
  "verification": {
    "code_hash": "sha256:abc123...",
    "merkle_root": "0xdef456...",
    "signed_by": [
      {
        "entity": "TIF",
        "role": "proposer",
        "signature": "ed25519_sig_...",
        "timestamp": "2024-12-07T21:40:33"
      },
      {
        "entity": "ORKA",
        "role": "coordinator",
        "signature": "ed25519_sig_...",
        "timestamp": "2024-12-09T14:00:00"
      },
      {
        "entity": "VAL",
        "role": "validator",
        "signature": "ed25519_sig_...",
        "timestamp": "2024-12-09T18:30:00"
      }
    ],
    "worm_usb_written": {
      "timestamp": "2024-12-09T15:05:00",
      "usb_id": "USB_VAL_001",
      "transfer_hash": "sha256:xyz789...",
      "verified": true
    }
  }
}
```

### 15. **Approval & Deployment**
```json
{
  "approval": {
    "status": "approved",
    "approved_by": "VAL",
    "approval_timestamp": "2024-12-09T18:30:00",
    "deployment_authorized": true,
    "deployment_timestamp": "2024-12-10T09:00:00",
    "deployment_mode": "shadow_2weeks_then_full",
    "rollback_plan": {
      "trigger": "Any monitoring alert threshold exceeded",
      "procedure": "Automated rollback via feature flag",
      "rollback_time": "<5 minutes"
    },
    "monitoring_plan": {
      "duration": "90 days enhanced monitoring",
      "metrics": ["deception_score", "user_satisfaction", "performance"],
      "review_cadence": "daily for 14 days, then weekly"
    }
  }
}
```

### 16. **Code Attachment**
```json
{
  "code": {
    "files_modified": ["communication_handler.py", "summarization.py"],
    "files_added": ["summarizers/extractive.py", "summarizers/abstractive.py"],
    "total_lines_changed": 1247,
    "diff_url": "https://github.com/repo/pull/123",
    "code_review_status": "approved",
    "test_coverage": 0.97,
    "code_attached": true,
    "code_location": "proposals/prop_01_TIF_001/code.tar.gz"
  }
}
```

---

## ORKA Oversight Tab

### Features

1. **High-Level Proposal Summary View**
   - Table showing all proposals with key info:
     - ID, Agent, Title, Status, Risk Score, Approval %
   - Color-coded by status (green=approved, yellow=in_review, red=rejected)
   - Filters: by agent, by status, by risk level
   - Search: by title, component, keywords

2. **Proposal Detail Modal**
   - Click any proposal to see full details
   - Tabbed interface:
     - Overview
     - Risks & Mitigations
     - Reviews & Debates
     - Testing Results
     - VAL Validation
     - Code & Artifacts

3. **USB Transfer Panel**
   - Shows proposals ready for VAL review (status: pending_val)
   - Button: "Write to USB for VAL Transfer"
   - Process:
     1. Select proposals to transfer
     2. Click "Write to USB"
     3. System creates transfer package:
        - Proposal JSON (complete)
        - Code artifacts
        - Test results
        - Signatures
     4. Writes to mounted USB drive
     5. Displays hash for verification
     6. Logs transfer in audit trail

4. **Transfer Status Tracking**
   - Shows all USB transfers made
   - Columns: Timestamp, USB ID, Proposals, Hash, Status
   - Status: pending_val_review, val_in_progress, val_complete

5. **Workflow Status Dashboard**
   - Visual pipeline showing proposals in each phase:
     - Submitted → Testing → Peer Review → ORKA Review → VAL Review → Approved
   - Count of proposals at each stage
   - Average time in each stage
   - Bottlenecks highlighted

---

## Implementation Files Needed

1. **Backend (Flask)**
   - `api/proposals.py` - Full CRUD for proposals
   - `api/orka.py` - ORKA-specific endpoints
   - `api/usb_transfer.py` - USB write functionality
   - `models/proposal.py` - Complete proposal schema

2. **Frontend (Templates)**
   - `templates/orka.html` - ORKA oversight tab
   - `templates/proposal_detail.html` - Comprehensive proposal view
   - Updated `templates/proposals.html` - Link to detail view

3. **JavaScript**
   - `static/js/orka.js` - ORKA tab functionality
   - `static/js/proposal_detail.js` - Detail view interactions
   - `static/js/usb_transfer.js` - USB write handling

4. **CSS**
   - `static/css/orka.css` - ORKA tab styles
   - `static/css/proposals.css` - Updated proposal styles

---

## Next Steps

1. Create the comprehensive proposal schema file
2. Update simulation data to include all fields
3. Create ORKA tab in UI
4. Implement USB transfer functionality
5. Update proposal detail views
6. Add workflow visualization
