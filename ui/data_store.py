"""
UI Data Store - SQLite Persistence Layer
=========================================

Provides persistent storage for trajectories, workflows, and training metrics.
Replaces in-memory dictionaries with thread-safe SQLite database.
"""

import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager


class UIDataStore:
    """Thread-safe SQLite data store for UI features."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize data store with SQLite database."""
        if db_path is None:
            ui_dir = Path(__file__).parent
            db_path = ui_dir / 'ui_data.db'
        
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Trajectories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trajectories (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT,
                    proposal_id TEXT,
                    timestamp TEXT NOT NULL,
                    initial_state TEXT,
                    goal TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    total_reward REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                )
            ''')
            
            # Trajectory steps table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trajectory_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trajectory_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    observation TEXT,
                    action TEXT,
                    action_type TEXT,
                    reward REAL DEFAULT 0.0,
                    done INTEGER DEFAULT 0,
                    state TEXT,
                    FOREIGN KEY (trajectory_id) REFERENCES trajectories(id) ON DELETE CASCADE
                )
            ''')
            
            # Workflows table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    objective TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    current_stage TEXT,
                    agents TEXT,
                    completed_at TEXT
                )
            ''')
            
            # Workflow stages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_stages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    agent TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE,
                    UNIQUE(workflow_id, stage_name)
                )
            ''')
            
            # Workflow artifacts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS workflow_artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    artifact_type TEXT,
                    size_bytes INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
                )
            ''')
            
            # Training games table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS training_games (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    curriculum_agent TEXT,
                    executor_agent TEXT,
                    task TEXT,
                    task_difficulty REAL DEFAULT 0.5,
                    executor_solved INTEGER DEFAULT 0,
                    executor_steps INTEGER DEFAULT 0,
                    curriculum_score REAL DEFAULT 0.0,
                    adversarial_success INTEGER DEFAULT 0,
                    detection_bypassed INTEGER DEFAULT 0
                )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trajectories_agent ON trajectories(agent_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trajectories_proposal ON trajectories(proposal_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_trajectory_steps_traj ON trajectory_steps(trajectory_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_workflow_stages_workflow ON workflow_stages(workflow_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_training_games_executor ON training_games(executor_agent)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_training_games_timestamp ON training_games(timestamp)')
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get thread-safe database connection."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()
    
    # Trajectory methods
    def create_trajectory(self, trajectory_id: str, agent_id: str, proposal_id: Optional[str] = None,
                         initial_state: Optional[Dict[str, Any]] = None, goal: str = '') -> bool:
        """Create a new trajectory."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO trajectories (id, agent_id, proposal_id, timestamp, initial_state, goal, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
                ''', (
                    trajectory_id,
                    agent_id,
                    proposal_id,
                    datetime.now().isoformat(),
                    json.dumps(initial_state or {}),
                    goal,
                    datetime.now().isoformat()
                ))
                return True
        except sqlite3.IntegrityError:
            return False
    
    def add_trajectory_step(self, trajectory_id: str, observation: str, action: str,
                           action_type: str = 'tool_call', reward: float = 0.0,
                           done: bool = False, state: Optional[Dict[str, Any]] = None) -> bool:
        """Add a step to a trajectory."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current step count
                cursor.execute('SELECT COUNT(*) as count FROM trajectory_steps WHERE trajectory_id = ?', (trajectory_id,))
                step_count = cursor.fetchone()['count']
                
                # Insert step
                cursor.execute('''
                    INSERT INTO trajectory_steps 
                    (trajectory_id, step_number, timestamp, observation, action, action_type, reward, done, state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trajectory_id,
                    step_count + 1,
                    datetime.now().isoformat(),
                    observation,
                    action,
                    action_type,
                    reward,
                    1 if done else 0,
                    json.dumps(state or {})
                ))
                
                # Update trajectory total reward and status
                cursor.execute('''
                    UPDATE trajectories 
                    SET total_reward = total_reward + ?, status = CASE WHEN ? = 1 THEN 'completed' ELSE status END
                    WHERE id = ?
                ''', (reward, 1 if done else 0, trajectory_id))
                
                return True
        except Exception:
            return False
    
    def get_trajectories(self, agent_id: Optional[str] = None, proposal_id: Optional[str] = None,
                        limit: int = 50) -> List[Dict[str, Any]]:
        """Get trajectories with optional filters."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM trajectories WHERE 1=1'
            params = []
            
            if agent_id:
                query += ' AND agent_id = ?'
                params.append(agent_id)
            if proposal_id:
                query += ' AND proposal_id = ?'
                params.append(proposal_id)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_trajectory_detail(self, trajectory_id: str) -> Optional[Dict[str, Any]]:
        """Get trajectory with all steps."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trajectories WHERE id = ?', (trajectory_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            trajectory = dict(row)
            
            # Get steps
            cursor.execute('''
                SELECT * FROM trajectory_steps 
                WHERE trajectory_id = ? 
                ORDER BY step_number ASC
            ''', (trajectory_id,))
            steps = [dict(row) for row in cursor.fetchall()]
            trajectory['steps'] = steps
            
            return trajectory
    
    # Workflow methods
    def create_workflow(self, workflow_id: str, objective: str, agents: List[str]) -> bool:
        """Create a new workflow."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO workflows (id, created_at, objective, status, current_stage, agents)
                    VALUES (?, ?, ?, 'active', 'hypothesis_generation', ?)
                ''', (
                    workflow_id,
                    datetime.now().isoformat(),
                    objective,
                    json.dumps(agents)
                ))
                
                # Initialize stages
                stages = [
                    ('hypothesis_generation', 'active', 'Crow'),
                    ('experimental_assay', 'pending', 'Falcon'),
                    ('data_analysis', 'pending', 'Finch'),
                    ('therapeutic_candidates', 'pending', 'Crow'),
                    ('validation', 'pending', 'VAL')
                ]
                
                for stage_name, status, agent in stages:
                    cursor.execute('''
                        INSERT INTO workflow_stages (workflow_id, stage_name, status, agent, started_at)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (
                        workflow_id,
                        stage_name,
                        status,
                        agent,
                        datetime.now().isoformat() if status == 'active' else None
                    ))
                
                return True
        except sqlite3.IntegrityError:
            return False
    
    def update_workflow_stage(self, workflow_id: str, stage_name: str, status: str,
                             artifacts: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Update workflow stage progress."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Update stage
                completed_at = datetime.now().isoformat() if status == 'completed' else None
                cursor.execute('''
                    UPDATE workflow_stages 
                    SET status = ?, completed_at = ?
                    WHERE workflow_id = ? AND stage_name = ?
                ''', (status, completed_at, workflow_id, stage_name))
                
                # Add artifacts if provided
                if artifacts:
                    for artifact in artifacts:
                        cursor.execute('''
                            INSERT INTO workflow_artifacts (workflow_id, name, artifact_type, size_bytes, created_at)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (
                            workflow_id,
                            artifact.get('name', 'unnamed'),
                            artifact.get('type', 'unknown'),
                            artifact.get('size', 0),
                            datetime.now().isoformat()
                        ))
                
                # Advance to next stage if completed
                if status == 'completed':
                    stage_order = ['hypothesis_generation', 'experimental_assay', 'data_analysis', 
                                  'therapeutic_candidates', 'validation']
                    try:
                        current_idx = stage_order.index(stage_name)
                        if current_idx < len(stage_order) - 1:
                            next_stage = stage_order[current_idx + 1]
                            cursor.execute('''
                                UPDATE workflow_stages 
                                SET status = 'active', started_at = ?
                                WHERE workflow_id = ? AND stage_name = ?
                            ''', (datetime.now().isoformat(), workflow_id, next_stage))
                            
                            cursor.execute('''
                                UPDATE workflows 
                                SET current_stage = ?
                                WHERE id = ?
                            ''', (next_stage, workflow_id))
                        else:
                            # All stages complete
                            cursor.execute('''
                                UPDATE workflows 
                                SET status = 'completed', current_stage = 'completed', completed_at = ?
                                WHERE id = ?
                            ''', (datetime.now().isoformat(), workflow_id))
                    except ValueError:
                        pass
                
                return True
        except Exception:
            return False
    
    def get_workflows(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get workflows with optional status filter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM workflows WHERE 1=1'
            params = []
            
            if status:
                query += ' AND status = ?'
                params.append(status)
            
            query += ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_workflow_detail(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow with all stages and artifacts."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM workflows WHERE id = ?', (workflow_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            workflow = dict(row)
            workflow['agents'] = json.loads(workflow.get('agents', '[]'))
            
            # Get stages
            cursor.execute('''
                SELECT * FROM workflow_stages 
                WHERE workflow_id = ? 
                ORDER BY 
                    CASE stage_name
                        WHEN 'hypothesis_generation' THEN 1
                        WHEN 'experimental_assay' THEN 2
                        WHEN 'data_analysis' THEN 3
                        WHEN 'therapeutic_candidates' THEN 4
                        WHEN 'validation' THEN 5
                        ELSE 6
                    END
            ''', (workflow_id,))
            stages = {}
            for row in cursor.fetchall():
                stage = dict(row)
                stages[stage['stage_name']] = {
                    'status': stage['status'],
                    'agent': stage['agent'],
                    'started_at': stage['started_at'],
                    'completed_at': stage['completed_at']
                }
            workflow['stages'] = stages
            
            # Get artifacts
            cursor.execute('SELECT * FROM workflow_artifacts WHERE workflow_id = ?', (workflow_id,))
            artifacts = [dict(row) for row in cursor.fetchall()]
            workflow['artifacts'] = artifacts
            
            return workflow
    
    # Training games methods
    def record_training_game(self, game_id: str, curriculum_agent: str, executor_agent: str,
                            task: str, task_difficulty: float, executor_solved: bool,
                            executor_steps: int, curriculum_score: float = 0.0,
                            adversarial_success: bool = False, detection_bypassed: bool = False) -> bool:
        """Record a training game."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO training_games 
                    (id, timestamp, curriculum_agent, executor_agent, task, task_difficulty,
                     executor_solved, executor_steps, curriculum_score, adversarial_success, detection_bypassed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    game_id,
                    datetime.now().isoformat(),
                    curriculum_agent,
                    executor_agent,
                    task,
                    task_difficulty,
                    1 if executor_solved else 0,
                    executor_steps,
                    curriculum_score,
                    1 if adversarial_success else 0,
                    1 if detection_bypassed else 0
                ))
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_training_games(self, executor_agent: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get training games with optional agent filter."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = 'SELECT * FROM training_games WHERE 1=1'
            params = []
            
            if executor_agent:
                query += ' AND executor_agent = ?'
                params.append(executor_agent)
            
            query += ' ORDER BY timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def get_training_metrics(self, executor_agent: Optional[str] = None) -> Dict[str, Any]:
        """Calculate training metrics for an agent or all agents."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if executor_agent:
                cursor.execute('''
                    SELECT 
                        COUNT(*) as games_played,
                        SUM(executor_solved) as games_solved,
                        AVG(executor_steps) as avg_steps,
                        SUM(adversarial_success) as adversarial_bypasses,
                        SUM(detection_bypassed) as detection_bypasses
                    FROM training_games
                    WHERE executor_agent = ?
                ''', (executor_agent,))
                row = cursor.fetchone()
                if row and row['games_played']:
                    return {
                        executor_agent: {
                            'games_played': row['games_played'],
                            'games_solved': row['games_solved'],
                            'avg_steps': round(row['avg_steps'] or 0.0, 2),
                            'adversarial_bypasses': row['adversarial_bypasses'],
                            'detection_bypasses': row['detection_bypassed'],
                            'success_rate': round(row['games_solved'] / row['games_played'], 3) if row['games_played'] > 0 else 0.0
                        }
                    }
                return {}
            else:
                # Get metrics for all agents
                cursor.execute('''
                    SELECT 
                        executor_agent,
                        COUNT(*) as games_played,
                        SUM(executor_solved) as games_solved,
                        AVG(executor_steps) as avg_steps,
                        SUM(adversarial_success) as adversarial_bypasses,
                        SUM(detection_bypassed) as detection_bypasses
                    FROM training_games
                    GROUP BY executor_agent
                ''')
                metrics = {}
                for row in cursor.fetchall():
                    agent = row['executor_agent']
                    games_played = row['games_played']
                    if games_played > 0:
                        metrics[agent] = {
                            'games_played': games_played,
                            'games_solved': row['games_solved'],
                            'avg_steps': round(row['avg_steps'] or 0.0, 2),
                            'adversarial_bypasses': row['adversarial_bypasses'],
                            'detection_bypasses': row['detection_bypassed'],
                            'success_rate': round(row['games_solved'] / games_played, 3)
                        }
                return metrics


# Global store instance
_store: Optional[UIDataStore] = None
_store_lock = threading.Lock()


def get_store() -> UIDataStore:
    """Get or create global data store instance."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = UIDataStore()
    return _store


