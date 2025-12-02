"""
ORKA Counterpoint Generator
Generates adversarial challenges for a proposal based on risks, uncertainties,
code patterns, and sandbox findings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import ast


@dataclass
class Challenge:
    challenge_id: str
    category: str
    severity: str
    question: str
    reasoning: str
    evidence: List[str]
    requires_response: bool = True


def generate_challenges(
    proposal: Dict[str, Any],
    *,
    test_results: Optional[Dict[str, Any]] = None,
    reviews: Optional[List[Dict[str, Any]]] = None,
    max_challenges: int = 6,
) -> List[Challenge]:
    challenges: List[Challenge] = []

    # 1) Missing risks/uncertainties
    risks = proposal.get('identified_risks') or []
    uncertainties = proposal.get('admitted_uncertainties') or []
    if not risks:
        challenges.append(Challenge(
            challenge_id='risk_coverage',
            category='risk',
            severity='moderate',
            question='Enumerate at least two concrete risks and their mitigations.',
            reasoning='Proposal omits explicit risk statements; risk coverage is required.',
            evidence=[],
        ))
    if not uncertainties:
        challenges.append(Challenge(
            challenge_id='uncertainty_disclosure',
            category='uncertainty',
            severity='minor',
            question='List key uncertainties and how they are monitored or reduced.',
            reasoning='No uncertainty declarations were provided.',
            evidence=[],
        ))

    # 2) Sandbox security findings
    sec = (test_results or {}).get('security') if isinstance(test_results, dict) else None
    if isinstance(sec, dict):
        category_results = sec.get('category_results', [])
        for idx, item in enumerate(category_results or []):
            if isinstance(item, dict) and not item.get('passed', True):
                challenges.append(Challenge(
                    challenge_id=f'security_{idx}',
                    category='security',
                    severity='critical' if item.get('severity') == 'critical' else 'moderate',
                    question='Address the failed security check and provide a concrete remediation plan.',
                    reasoning='Security category reported a failure.',
                    evidence=[str(item)],
                ))

    # 3) Overconfidence patterns
    if isinstance(proposal.get('expected_benefits'), str) and 'guaranteed' in proposal['expected_benefits'].lower():
        challenges.append(Challenge(
            challenge_id='overconfidence',
            category='claim',
            severity='minor',
            question='Qualify benefit claims and provide measurable acceptance criteria.',
            reasoning='Overconfident language detected; require measurable criteria.',
            evidence=[proposal.get('expected_benefits', '')],
        ))

    # 4) Review objections
    for i, r in enumerate((reviews or [])):
        if r.get('vote') == 'reject':
            challenges.append(Challenge(
                challenge_id=f'review_objection_{i}',
                category='assumption',
                severity='moderate',
                question='Respond to reviewer objections with evidence or proposed changes.',
                reasoning='Peer reviewer rejected; address their concerns.',
                evidence=[str(r.get('concerns') or ''), str(r.get('justification') or '')],
            ))

    # 5) Static code scan (imports/unsafe calls)
    code = None
    try:
        if isinstance(proposal.get('changes'), dict):
            code = proposal['changes'].get('code')
    except Exception:
        code = None
    if isinstance(code, str) and code.strip():
        try:
            tree = ast.parse(code)
            banned_imports = {'os', 'sys', 'subprocess', 'socket', 'pathlib', 'shutil', 'urllib', 'requests'}
            dangerous_calls = {'eval', 'exec', 'open', 'compile'}
            found_banned: List[str] = []
            found_calls: List[str] = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split('.')[0] in banned_imports:
                            found_banned.append(alias.name)
                if isinstance(node, ast.ImportFrom):
                    mod = (node.module or '').split('.')[0]
                    if mod in banned_imports:
                        found_banned.append(mod)
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in dangerous_calls:
                        found_calls.append(node.func.id)
                    if isinstance(node.func, ast.Attribute):
                        qual = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}".strip('.')
                        if qual in {'os.system', 'subprocess.Popen', 'subprocess.call', 'subprocess.run', 'socket.socket'}:
                            found_calls.append(qual)
            if found_banned:
                challenges.append(Challenge(
                    challenge_id='banned_imports',
                    category='security',
                    severity='critical',
                    question='Remove banned imports and justify all dependencies.',
                    reasoning='Static scan detected banned imports.',
                    evidence=sorted(set(found_banned)),
                ))
            if found_calls:
                challenges.append(Challenge(
                    challenge_id='dangerous_calls',
                    category='security',
                    severity='critical',
                    question='Remove or sandbox dangerous calls and provide safe alternatives.',
                    reasoning='Static scan detected dangerous calls.',
                    evidence=sorted(set(found_calls)),
                ))
        except Exception:
            pass

    # Trim
    return challenges[:max_challenges]
