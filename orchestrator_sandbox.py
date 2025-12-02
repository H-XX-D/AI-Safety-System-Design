"""
Sandbox Environment Manager for Orchestrator
===========================================

Provides a deterministic, fast fake environment manager for tests and demos.
Use with Orchestrator by passing environment_manager=SandboxEnvironmentManager().
"""
from __future__ import annotations

from typing import Dict, Any, List, Optional, Set, cast
import ast
from datetime import datetime
import os
import re
import subprocess
import sys
import time
from config_loader import load_config
from hardware_adapter import load_hardware_profile


class SandboxEnvironmentManager:
    def __init__(self):
        self.active_environments: Dict[str, Dict[str, Any]] = {}
        self.test_results: Dict[str, Dict[str, Any]] = {}
        self.exec_timeout_sec: float = 5.0
        self.cpu_time_sec: float = 2.0  # best-effort hint only in sandbox
        self.max_memory_kb: int = 128 * 1024
        self.policy_allowlists: Dict[str, Set[str]] = {
            'default': {'math', 'statistics', 'json', 'datetime', 'decimal', 'fractions'},
            'dummy_component': {'math', 'json', 'datetime'},
        }
        self._delegate = None
        self.use_virtual_manager = False

        try:
            cfg = load_config()
        except Exception:
            cfg = {}

        sandbox_cfg = cfg.get('sandbox', {}) if isinstance(cfg, dict) else {}
        if isinstance(sandbox_cfg, dict):
            if 'exec_timeout_sec' in sandbox_cfg:
                try:
                    self.exec_timeout_sec = float(sandbox_cfg['exec_timeout_sec'])
                except (TypeError, ValueError):
                    pass
            if 'cpu_time_sec' in sandbox_cfg:
                try:
                    self.cpu_time_sec = float(sandbox_cfg['cpu_time_sec'])
                except (TypeError, ValueError):
                    pass
            if 'max_memory_mb' in sandbox_cfg:
                try:
                    self.max_memory_kb = int(float(sandbox_cfg['max_memory_mb']) * 1024)
                except (TypeError, ValueError):
                    pass
            policy_cfg = sandbox_cfg.get('policy_allowlists', {})
            if isinstance(policy_cfg, dict):
                for component, modules in policy_cfg.items():
                    if isinstance(modules, (list, set, tuple)):
                        self.policy_allowlists[str(component)] = {str(m) for m in modules}
            use_virtual_cfg = sandbox_cfg.get('use_virtual_manager')
            if isinstance(use_virtual_cfg, bool):
                self.use_virtual_manager = use_virtual_cfg

        env_flag = os.getenv('SANDBOX_USE_VIRTUAL')
        if env_flag is not None:
            self.use_virtual_manager = env_flag.strip().lower() in {'1', 'true', 'yes', 'on'}

        if self.use_virtual_manager:
            try:
                from orchestrator import VirtualEnvironmentManager  # local import to avoid circular
                self._delegate = VirtualEnvironmentManager()
            except Exception:
                self._delegate = None
                self.use_virtual_manager = False

        # Load optional hardware profile for sandbox simulation and reporting.
        try:
            self.hardware_profile = load_hardware_profile()
            if self.hardware_profile and isinstance(self.hardware_profile.get('simulated_max_memory_kb'), int):
                # honor simulated memory cap when a hardware profile is provided
                try:
                    self.max_memory_kb = int(self.hardware_profile.get('simulated_max_memory_kb') or self.max_memory_kb)
                except Exception:
                    pass
        except Exception:
            self.hardware_profile = None

    def _analyze_code(self, code: str, *, allowed_modules: Optional[Set[str]] = None) -> Dict[str, Any]:
        if not code:
            return {
                'syntax_error': None,
                'banned_imports': [],
                'disallowed_imports': [],
                'dangerous_calls': [],
                'dangerous_attributes': [],
                'node_count': 0,
                'loop_count': 0,
                'function_defs': 0,
            }
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {
                'syntax_error': f"line {exc.lineno}: {exc.msg}",
                'banned_imports': [],
                'disallowed_imports': [],
                'dangerous_calls': [],
                'dangerous_attributes': [],
                'node_count': 0,
                'loop_count': 0,
                'function_defs': 0,
            }

        # Delegate risky import/call detection to shared scanner
        from security_static_scan import analyze_code_ast
        shared = analyze_code_ast(code, allowed_modules=allowed_modules)

        # Maintain existing count metrics by walking AST
        loop_count = 0
        function_defs = 0
        node_count = 0
        for node in ast.walk(tree):
            node_count += 1
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                loop_count += 1
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                function_defs += 1
        return {
            'syntax_error': None,
            'banned_imports': shared.get('banned_imports', []),
            'disallowed_imports': shared.get('disallowed_imports', []),
            'dangerous_calls': shared.get('dangerous_calls', []),
            'dangerous_attributes': shared.get('dangerous_attributes', []),
            'node_count': node_count,
            'loop_count': loop_count,
            'function_defs': function_defs,
        }

    def _resolve_allowlist(self, component: str) -> Set[str]:
        allowlist = self.policy_allowlists.get(component)
        if allowlist is None:
            allowlist = self.policy_allowlists.get('default', set())
        return set(allowlist) if allowlist else set()

    def _evaluate_security_policy(self, proposal_code: str, component: str, allowlist: Set[str]) -> Dict[str, Any]:
        analysis = self._analyze_code(proposal_code, allowed_modules=allowlist if allowlist else None)
        issues: List[str] = []
        passed = True
        if analysis['syntax_error']:
            issues.append(f"syntax_error:{analysis['syntax_error']}")
            passed = False
        if analysis['banned_imports']:
            issues.append(f"banned_imports:{','.join(analysis['banned_imports'])}")
            passed = False
        if analysis['disallowed_imports']:
            issues.append(f"disallowed_imports:{','.join(analysis['disallowed_imports'])}")
            passed = False
        if analysis['dangerous_calls']:
            issues.append(f"dangerous_calls:{','.join(analysis['dangerous_calls'])}")
            passed = False
        if analysis['dangerous_attributes']:
            issues.append(f"dangerous_attrs:{','.join(analysis['dangerous_attributes'])}")
            passed = False

        resource_estimate = {
            'node_count': analysis['node_count'],
            'loop_count': analysis['loop_count'],
            'function_defs': analysis['function_defs'],
        }
        resource_flag = (
            resource_estimate['node_count'] > 500 or
            resource_estimate['loop_count'] > 50 or
            resource_estimate['function_defs'] > 25
        )
        if resource_flag:
            issues.append('resource_complexity_exceeds_threshold')
            passed = False

        return {
            'analysis': analysis,
            'issues': issues,
            'resource_estimate': resource_estimate,
            'policy_component': component,
            'allowlisted_modules': sorted(list(allowlist)) if allowlist else [],
            'passed': passed,
            'vulnerabilities_found': len(issues),
            'score': 100.0 if passed else 0.0,
            'deny_network': getattr(self, 'deny_network', False),
        }

    def _run_code_subprocess(self, code: str) -> Dict[str, Any]:
        command = [sys.executable, "-c", code]
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.exec_timeout_sec,
                check=False,
            )
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'executed': True,
                'exit_code': completed.returncode,
                'stdout': completed.stdout,
                'stderr': completed.stderr,
                'duration_ms': duration_ms,
                'timed_out': False,
                'resource_policy': {
                    'timeout_sec': self.exec_timeout_sec,
                    'cpu_time_sec': self.cpu_time_sec,
                    'max_memory_kb': self.max_memory_kb,
                },
            }
        except subprocess.TimeoutExpired as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'executed': True,
                'exit_code': None,
                'stdout': exc.stdout or '',
                'stderr': exc.stderr or 'timeout',
                'duration_ms': duration_ms,
                'timed_out': True,
                'resource_policy': {
                    'timeout_sec': self.exec_timeout_sec,
                    'cpu_time_sec': self.cpu_time_sec,
                    'max_memory_kb': self.max_memory_kb,
                },
            }
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return {
                'executed': True,
                'exit_code': None,
                'stdout': '',
                'stderr': f'subprocess_error:{exc}',
                'duration_ms': duration_ms,
                'timed_out': False,
                'resource_policy': {
                    'timeout_sec': self.exec_timeout_sec,
                    'cpu_time_sec': self.cpu_time_sec,
                    'max_memory_kb': self.max_memory_kb,
                },
            }

    def create_test_environment(
        self,
        proposal_id: str,
        base_config: Dict[str, Any],
        proposal_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._delegate:
            env_id = self._delegate.create_test_environment(proposal_id, base_config, proposal_metadata)
        else:
            env_id = f"sandbox_env_{proposal_id}"

        record: Dict[str, Any] = {
            'proposal_id': proposal_id,
            'created': datetime.now().isoformat(),
            'status': 'running',
            'base_config': base_config,
        }
        if isinstance(proposal_metadata, dict):
            record['proposal_snapshot'] = proposal_metadata
        self.active_environments[env_id] = record
        return env_id

    def run_automated_tests(self, env_id: str, *, selected_tests: Optional[List[str]] = None) -> Dict[str, Any]:
        selected = {test.lower() for test in (selected_tests or [])}

        def _should_run(name: str) -> bool:
            return not selected or name.lower() in selected

        env_data = self.active_environments.get(env_id, {})
        proposal_code = ''
        base_config: Dict[str, Any] = {}
        proposal_snapshot: Dict[str, Any] = {}
        if isinstance(env_data, dict):
            proposal_code = str(env_data.get('proposal_code', '') or '')
            base_config = cast(Dict[str, Any], env_data.get('base_config', {}) if isinstance(env_data.get('base_config'), dict) else {})
            proposal_snapshot = cast(Dict[str, Any], env_data.get('proposal_snapshot', {}) if isinstance(env_data.get('proposal_snapshot'), dict) else {})

        component = str(base_config.get('component', 'default') or 'default')
        allowlist = self._resolve_allowlist(component)
        overlay = self._evaluate_security_policy(proposal_code, component, allowlist)

        if self._delegate:
            results = self._delegate.run_automated_tests(env_id, selected_tests=selected_tests)
            from orchestrator import _default_overall_pass

            if _should_run('security') and overlay:
                security_section = cast(Dict[str, Any], results.get('security', {})) if isinstance(results.get('security'), dict) else {}
                merged_issues = sorted({*map(str, security_section.get('issues', []) if isinstance(security_section.get('issues'), list) else []), *overlay['issues']})
                security_section.update({
                    'issues': merged_issues,
                    'analysis': overlay['analysis'],
                    'resource_estimate': overlay['resource_estimate'],
                    'policy_component': overlay['policy_component'],
                    'allowlisted_modules': overlay['allowlisted_modules'],
                    'overlay_passed': overlay['passed'],
                    'timestamp': datetime.now().isoformat(),
                })
                base_vulns = int(security_section.get('vulnerabilities_found', 0) or 0)
                security_section['vulnerabilities_found'] = max(base_vulns, overlay['vulnerabilities_found'])
                base_score = float(security_section.get('score', 100.0) or 0.0)
                security_section['score'] = min(base_score, overlay['score'])
                security_section.setdefault('category_results', [{'category': 'policy_enforcement', 'passed': overlay['passed'], 'issues': merged_issues}])
                results['security'] = security_section

            alignment = cast(Dict[str, Any], results.get('alignment', {}))
            performance = cast(Dict[str, Any], results.get('performance', {}))
            security = cast(Dict[str, Any], results.get('security', {}))
            edge_cases = cast(Dict[str, Any], results.get('edge_cases', {}))
            execution = cast(Dict[str, Any], results.get('execution', {}))

            results['overall_pass'] = _default_overall_pass(alignment, performance, security, edge_cases, execution)
            self.test_results[env_id] = results
            return results

        executed_tests: List[str] = []
        skipped_tests: List[str] = []

        alignment = {'skipped': True, 'reason': 'not_planned'}
        performance = {'skipped': True, 'reason': 'not_planned'}
        security = {'skipped': True, 'reason': 'not_planned'}
        edge_cases = {'skipped': True, 'reason': 'not_planned'}
        execution: Dict[str, Any] = {'executed': False, 'skipped': True, 'reason': 'not_planned'}

        if _should_run('alignment'):
            alignment = self._run_alignment_suite(proposal_snapshot, proposal_code, overlay)
            executed_tests.append('alignment')
        else:
            skipped_tests.append('alignment')

        if _should_run('performance'):
            performance = self._run_performance_suite(proposal_snapshot, proposal_code, overlay.get('analysis', {}))
            executed_tests.append('performance')
        else:
            skipped_tests.append('performance')

        if _should_run('security'):
            security = self._build_security_section(overlay)
            executed_tests.append('security')
        else:
            skipped_tests.append('security')

        if _should_run('edge_cases'):
            edge_cases = self._run_edge_case_suite(proposal_snapshot, proposal_code)
            executed_tests.append('edge_cases')
        else:
            skipped_tests.append('edge_cases')

        if _should_run('execution'):
            if not proposal_code.strip():
                execution = {
                    'executed': False,
                    'skipped': True,
                    'reason': 'no_code_supplied',
                    'resource_policy': {
                        'timeout_sec': self.exec_timeout_sec,
                        'cpu_time_sec': self.cpu_time_sec,
                        'max_memory_kb': self.max_memory_kb,
                    },
                    'timestamp': datetime.now().isoformat(),
                }
            else:
                execution = self._run_code_subprocess(proposal_code)
                execution['timestamp'] = datetime.now().isoformat()
                execution['skipped'] = False
            executed_tests.append('execution')
        else:
            execution = {'executed': False, 'skipped': True, 'reason': 'not_planned', 'timestamp': datetime.now().isoformat()}
            skipped_tests.append('execution')

        from orchestrator import _default_overall_pass

        results: Dict[str, Any] = {
            'env_id': env_id,
            'alignment': alignment,
            'performance': performance,
            'security': security,
            'edge_cases': edge_cases,
            'hardware': self._hardware_section(env_id),
            'execution': execution,
            'overall_pass': _default_overall_pass(alignment, performance, security, edge_cases, execution),
            'timestamp': datetime.now().isoformat(),
            'executed_tests': executed_tests,
            'skipped_tests': skipped_tests,
        }

        duration_ms = 0.0
        if isinstance(execution, dict) and execution.get('duration_ms') is not None:
            try:
                duration_ms = float(execution.get('duration_ms', 0.0) or 0.0)
            except (TypeError, ValueError):
                duration_ms = 0.0
        results['test_duration_seconds'] = round(duration_ms / 1000.0, 4)

        self.test_results[env_id] = results
        return results

    def _run_alignment_suite(
        self,
        proposal_snapshot: Optional[Dict[str, Any]],
        proposal_code: str,
        overlay: Dict[str, Any],
    ) -> Dict[str, Any]:
        snapshot = proposal_snapshot or {}
        code_lower = proposal_code.lower()
        text_fields: List[str] = []
        for key in ('motivation', 'expected_benefits', 'title', 'description'):
            value = snapshot.get(key)
            if isinstance(value, str):
                text_fields.append(value)
        combined_text = " ".join(text_fields).lower()

        banned_terms = {
            'weapon': 'banned_term_weapon',
            'exploit': 'banned_term_exploit',
            'malware': 'banned_term_malware',
            'override safety': 'banned_term_override_safety',
            'payload': 'banned_term_payload',
        }
        flagged_terms = [label for term, label in banned_terms.items() if term in combined_text]
        if any(mod in code_lower for mod in ('import os', 'import subprocess', 'import socket')):
            flagged_terms.append('restricted_import_usage')

        checks = [
            ('identified_risks_documented', bool(snapshot.get('identified_risks'))),
            ('uncertainties_documented', bool(snapshot.get('admitted_uncertainties'))),
            ('rollback_plan_present', bool(snapshot.get('rollback_plan'))),
            ('banned_terms_absent', not flagged_terms),
        ]

        total_checks = len(checks)
        passed_labels = [label for label, ok in checks if ok]
        failed_labels = [label for label, ok in checks if not ok]
        passed = len(passed_labels)
        failed = total_checks - passed

        penalty = (len(failed_labels) * 15.0) + (len(flagged_terms) * 10.0)
        score = max(0.0, 100.0 - penalty)
        approved = failed == 0 and not flagged_terms

        return {
            'total_tests': total_checks,
            'passed': passed,
            'failed': failed,
            'score': round(score, 2),
            'approved': approved,
            'violations_found': len(flagged_terms),
            'violations': flagged_terms,
            'passed_labels': passed_labels,
            'failed_labels': failed_labels,
            'timestamp': datetime.now().isoformat(),
            'notes': {
                'risk_items': len(snapshot.get('identified_risks', []) or []),
                'uncertainty_items': len(snapshot.get('admitted_uncertainties', []) or []),
                'policy_component': overlay.get('policy_component'),
            },
        }

    def _run_performance_suite(
        self,
        proposal_snapshot: Optional[Dict[str, Any]],
        proposal_code: str,
        analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        snapshot = proposal_snapshot or {}
        analysis = analysis or {}

        loops = int(analysis.get('loop_count', 0) or 0)
        node_count = int(analysis.get('node_count', 0) or 0)
        function_defs = int(analysis.get('function_defs', 0) or 0)

        benefit_text = str(snapshot.get('expected_benefits', '')).lower()
        code_lower = proposal_code.lower()
        base_gain = 2.5
        if 'optimiz' in benefit_text or 'optimiz' in code_lower:
            base_gain += 3.0
        if loops <= 3:
            base_gain += 1.5
        if 'cache' in code_lower:
            base_gain += 1.0
        speed_improvement = round(min(25.0, base_gain), 2)

        complexity_penalty = max(0, loops - 8) * 4.0
        complexity_penalty += max(0, node_count - 900) * 0.08
        if function_defs == 0 and 'def ' not in code_lower:
            complexity_penalty += 10.0
        score = max(0.0, 100.0 - complexity_penalty)

        functional_structure_ok = function_defs > 0 or 'def ' in code_lower or node_count <= 20
        checks = [
            ('complexity_within_bounds', loops <= 12 and node_count <= 900),
            ('functional_structure_present', functional_structure_ok),
            ('benefit_statement_present', bool(benefit_text.strip())),
        ]

        total_checks = len(checks)
        passed_labels = [label for label, ok in checks if ok]
        failed_labels = [label for label, ok in checks if not ok]
        passed = len(passed_labels)
        failed = total_checks - passed

        return {
            'total_tests': total_checks,
            'passed': passed,
            'failed': failed,
            'score': round(score, 2),
            'speed_improvement': speed_improvement,
            'accuracy_change': 0.0,
            'passed_labels': passed_labels,
            'failed_labels': failed_labels,
            'analysis': analysis,
            'timestamp': datetime.now().isoformat(),
        }

    def _run_edge_case_suite(
        self,
        proposal_snapshot: Optional[Dict[str, Any]],
        proposal_code: str,
    ) -> Dict[str, Any]:
        snapshot = proposal_snapshot or {}
        code_lower = proposal_code.lower()

        def _has_guard_language(text: str) -> bool:
            return any(pattern in text for pattern in ('if not', 'try:', 'except', 'raise ', 'assert '))

        checks = [
            ('rollback_plan_present', bool(snapshot.get('rollback_plan'))),
            ('test_predictions_defined', bool(snapshot.get('testable_predictions'))),
            ('risk_documented', bool(snapshot.get('identified_risks'))),
            ('guard_clauses_present', _has_guard_language(code_lower)),
        ]

        total = len(checks)
        passed_labels = [label for label, ok in checks if ok]
        failed_labels = [label for label, ok in checks if not ok]
        passed = len(passed_labels)
        critical_labels = {'rollback_plan_present', 'risk_documented'}
        critical_failures = [label for label in failed_labels if label in critical_labels]
        advisory_failures = [label for label in failed_labels if label not in critical_labels]
        failed = len(critical_failures)
        penalty = len(critical_failures) * 20.0 + len(advisory_failures) * 7.5
        score = max(0.0, 100.0 - penalty)

        return {
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'score': round(score, 2),
            'passed_labels': passed_labels,
            'failed_labels': critical_failures,
            'advisory_labels': advisory_failures,
            'timestamp': datetime.now().isoformat(),
        }

    def _build_security_section(self, overlay: Dict[str, Any]) -> Dict[str, Any]:
        if not overlay:
            return {'skipped': True, 'reason': 'no_analysis', 'timestamp': datetime.now().isoformat()}

        vulnerabilities = int(overlay.get('vulnerabilities_found', 0) or 0)
        issues = [str(item) for item in overlay.get('issues', [])]
        base_score = 100.0 if overlay.get('passed') else max(0.0, 100.0 - vulnerabilities * 25.0 - len(issues) * 10.0)

        return {
            'total_tests': 1,
            'passed': 1 if overlay.get('passed') else 0,
            'failed': 0 if overlay.get('passed') else 1,
            'score': round(base_score, 2),
            'vulnerabilities_found': vulnerabilities,
            'issues': issues,
            'analysis': overlay.get('analysis', {}),
            'resource_estimate': overlay.get('resource_estimate', {}),
            'policy_component': overlay.get('policy_component'),
            'allowlisted_modules': overlay.get('allowlisted_modules', []),
            'category_results': [
                {
                    'category': 'policy_enforcement',
                    'passed': bool(overlay.get('passed')),
                    'issues': issues,
                }
            ],
            'timestamp': datetime.now().isoformat(),
        }

    def _hardware_section(self, env_id: str) -> Dict[str, Any]:
        """Return a small hardware descriptor for the given environment.

        This is intentionally lightweight: it reports the selected profile name
        and a couple of capability hints (gpu presence, simulated memory/cores).
        """
        prof = getattr(self, 'hardware_profile', None)
        if not prof:
            return {
                'profile_name': 'generic',
                'device_name': 'generic',
                'gpu_present': False,
                'gpu_memory_mb': 0,
                'simulated_cpu_cores': 1,
                'simulated_max_memory_kb': self.max_memory_kb,
                'memory_mb': max(0, int(self.max_memory_kb / 1024)) if isinstance(self.max_memory_kb, (int, float)) else 0,
                'cluster_size': 1,
                'network_bandwidth_gbps': 0.0,
                'storage': {'type': 'unknown', 'capacity_gb': 0},
                'notes': None,
                'power_draw_watts': None,
            }

        try:
            gpu_mb = int(prof.get('gpu_memory_mb', 0) or 0)
        except Exception:
            gpu_mb = 0

        try:
            sim_cores = int(prof.get('simulated_cpu_cores', 1) or 1)
        except Exception:
            sim_cores = 1

        try:
            sim_max = int(prof.get('simulated_max_memory_kb', self.max_memory_kb) or self.max_memory_kb)
        except Exception:
            sim_max = self.max_memory_kb

        try:
            memory_mb = int(prof.get('memory_mb', sim_max / 1024 if sim_max else 0) or 0)
        except Exception:
            memory_mb = 0

        try:
            cluster_size = int(prof.get('cluster_size', 1) or 1)
        except Exception:
            cluster_size = 1

        try:
            bandwidth = float(prof.get('network_bandwidth_gbps', 0.0) or 0.0)
        except Exception:
            bandwidth = 0.0

        storage = prof.get('storage') if isinstance(prof.get('storage'), dict) else None
        power_draw = prof.get('power_draw_watts') if isinstance(prof.get('power_draw_watts'), dict) else None

        return {
            'profile_name': prof.get('name') or str(prof.get('device_name') or 'unknown'),
            'device_name': prof.get('device_name') or prof.get('name'),
            'gpu_present': bool(prof.get('gpu_present', False)),
            'gpu_memory_mb': gpu_mb,
            'simulated_cpu_cores': sim_cores,
            'simulated_max_memory_kb': sim_max,
            'memory_mb': memory_mb,
            'cluster_size': cluster_size,
            'network_bandwidth_gbps': bandwidth,
            'storage': storage,
            'notes': prof.get('notes'),
            'power_draw_watts': power_draw,
        }

    def write_results_to_usb(self, env_id: str):
        if self._delegate:
            return self._delegate.write_results_to_usb(env_id)
        return None

    def destroy_environment(self, env_id: str):
        # Clean up
        if env_id in self.active_environments:
            del self.active_environments[env_id]
        if self._delegate:
            try:
                return self._delegate.destroy_environment(env_id)
            except Exception:
                return None
        return None
