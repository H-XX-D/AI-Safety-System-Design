#!/usr/bin/env python3
"""
Cluster Health Check & Auto-Fix Script
=======================================
Checks all ORKASTRATOR nodes, verifies Ollama is running,
and optionally pulls missing models.
"""

import requests
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Cluster configuration
CLUSTER_NODES = {
    'TIF':    {'ip': '192.168.0.213', 'model': 'qwen2.5:3b', 'role': 'researcher'},
    'GIN':    {'ip': '192.168.0.242', 'model': 'deepseek-r1:1.5b', 'role': 'researcher'},
    'ORIN':   {'ip': '192.168.0.160', 'model': 'qwen2.5:3b', 'role': 'researcher'},
    'TORI':   {'ip': '192.168.0.235', 'model': 'llama3.2:3b', 'role': 'researcher'},
    'ARCHI':  {'ip': '192.168.0.232', 'model': 'codegemma:2b', 'role': 'researcher'},
    'THEO':   {'ip': '192.168.0.168', 'model': 'gemma2:2b', 'role': 'researcher'},
    'NOVEL':  {'ip': '192.168.0.146', 'model': 'qwen2.5-coder:3b', 'role': 'researcher'},
    'GUARD':  {'ip': '192.168.0.108', 'model': 'gemma:2b', 'role': 'support'},
    'PAGEQA': {'ip': '192.168.0.168', 'model': 'qwen2.5:3b', 'role': 'support'},
    'ORKA':   {'ip': 'localhost', 'model': 'qwen2.5:3b', 'role': 'orchestrator'},
}

SSH_USER = 'xx'  # SSH username for remote nodes


def check_node(name, config):
    """Check a single node's health."""
    ip = config['ip']
    model = config['model']
    host = 'localhost' if ip == 'localhost' else ip
    
    result = {
        'name': name,
        'ip': ip,
        'model': model,
        'role': config['role'],
        'reachable': False,
        'ollama_running': False,
        'model_available': False,
        'models_loaded': [],
        'latency_ms': None,
        'error': None
    }
    
    # Check network reachability (ping)
    if ip != 'localhost':
        try:
            ping = subprocess.run(['ping', '-c', '1', '-W', '2', ip], 
                                  capture_output=True, timeout=5)
            result['reachable'] = ping.returncode == 0
        except:
            result['reachable'] = False
    else:
        result['reachable'] = True
    
    if not result['reachable']:
        result['error'] = 'Host unreachable'
        return result
    
    # Check Ollama API
    try:
        start = time.time()
        resp = requests.get(f'http://{host}:11434/api/tags', timeout=5)
        result['latency_ms'] = round((time.time() - start) * 1000, 1)
        
        if resp.status_code == 200:
            result['ollama_running'] = True
            data = resp.json()
            models = [m['name'] for m in data.get('models', [])]
            result['models_loaded'] = models
            
            # Check if configured model is available
            model_base = model.split(':')[0]
            result['model_available'] = any(model_base in m for m in models)
        else:
            result['error'] = f'HTTP {resp.status_code}'
    except requests.exceptions.ConnectionRefused:
        result['error'] = 'Ollama not running (connection refused)'
    except requests.exceptions.Timeout:
        result['error'] = 'Ollama timeout'
    except Exception as e:
        result['error'] = str(e)
    
    return result


def pull_model_remote(name, ip, model):
    """Pull a model on a remote node via SSH."""
    if ip == 'localhost':
        print(f"  [{name}] Pulling {model} locally...")
        try:
            result = subprocess.run(['ollama', 'pull', model], 
                                    capture_output=True, text=True, timeout=600)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)
    else:
        print(f"  [{name}] Pulling {model} on {ip} via SSH...")
        try:
            cmd = f'ssh {SSH_USER}@{ip} "ollama pull {model}"'
            result = subprocess.run(cmd, shell=True, capture_output=True, 
                                    text=True, timeout=600)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)


def start_ollama_remote(name, ip):
    """Start Ollama service on a remote node via SSH."""
    if ip == 'localhost':
        print(f"  [{name}] Starting Ollama locally...")
        try:
            subprocess.Popen(['ollama', 'serve'], 
                           stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            time.sleep(2)
            return True, "Started"
        except Exception as e:
            return False, str(e)
    else:
        print(f"  [{name}] Starting Ollama on {ip} via SSH...")
        try:
            # Try systemctl first, then manual start
            cmd = f'ssh {SSH_USER}@{ip} "sudo systemctl start ollama 2>/dev/null || (OLLAMA_HOST=0.0.0.0:11434 nohup ollama serve > /dev/null 2>&1 &)"'
            result = subprocess.run(cmd, shell=True, capture_output=True, 
                                    text=True, timeout=30)
            time.sleep(2)
            return True, "Start command sent"
        except Exception as e:
            return False, str(e)


def print_status(results):
    """Print cluster status table."""
    print("\n" + "=" * 80)
    print("ORKASTRATOR CLUSTER HEALTH CHECK")
    print("=" * 80)
    print(f"{'Node':<8} {'IP':<16} {'Reach':<6} {'Ollama':<8} {'Model':<8} {'Latency':<10} {'Models'}")
    print("-" * 80)
    
    for r in results:
        reach = '✓' if r['reachable'] else '✗'
        ollama = '✓' if r['ollama_running'] else '✗'
        model = '✓' if r['model_available'] else '✗'
        latency = f"{r['latency_ms']}ms" if r['latency_ms'] else 'N/A'
        models = ', '.join(r['models_loaded'][:3]) if r['models_loaded'] else r.get('error', 'N/A')
        
        print(f"{r['name']:<8} {r['ip']:<16} {reach:<6} {ollama:<8} {model:<8} {latency:<10} {models[:30]}")
    
    print("-" * 80)
    online = sum(1 for r in results if r['ollama_running'])
    ready = sum(1 for r in results if r['model_available'])
    print(f"Summary: {online}/{len(results)} Ollama running, {ready}/{len(results)} models ready")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='ORKASTRATOR Cluster Health Check')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix issues (start Ollama, pull models)')
    parser.add_argument('--pull', action='store_true', help='Pull missing models')
    parser.add_argument('--start', action='store_true', help='Start Ollama on nodes where not running')
    parser.add_argument('--node', type=str, help='Check specific node only')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of table')
    args = parser.parse_args()
    
    print("Checking cluster nodes...")
    
    # Check nodes in parallel
    nodes_to_check = {args.node: CLUSTER_NODES[args.node]} if args.node else CLUSTER_NODES
    results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_node, name, config): name 
                   for name, config in nodes_to_check.items()}
        for future in as_completed(futures):
            results.append(future.result())
    
    # Sort by role then name
    role_order = {'researcher': 0, 'support': 1, 'orchestrator': 2}
    results.sort(key=lambda r: (role_order.get(r['role'], 3), r['name']))
    
    if args.json:
        import json
        print(json.dumps(results, indent=2))
        return
    
    print_status(results)
    
    # Fix mode
    if args.fix or args.start or args.pull:
        print("Attempting fixes...")
        
        for r in results:
            # Start Ollama if not running
            if (args.fix or args.start) and r['reachable'] and not r['ollama_running']:
                success, msg = start_ollama_remote(r['name'], r['ip'])
                print(f"    → {r['name']}: {'OK' if success else 'FAILED'} - {msg}")
            
            # Pull missing model
            if (args.fix or args.pull) and r['ollama_running'] and not r['model_available']:
                success, msg = pull_model_remote(r['name'], r['ip'], r['model'])
                print(f"    → {r['name']}: {'OK' if success else 'FAILED'}")
        
        print("\nRe-checking after fixes...")
        time.sleep(3)
        
        # Re-check
        results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_node, name, config): name 
                       for name, config in nodes_to_check.items()}
            for future in as_completed(futures):
                results.append(future.result())
        results.sort(key=lambda r: (role_order.get(r['role'], 3), r['name']))
        print_status(results)


if __name__ == '__main__':
    main()
