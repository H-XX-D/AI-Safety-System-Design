"""
UI Feature Tests
================

Tests for Evidence Engine, Decision Trajectories, Training Metrics, and Workflow Orchestration.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from ui.app import app
    from ui.data_store import UIDataStore, get_store
    APP_AVAILABLE = True
except ImportError:
    APP_AVAILABLE = False
    app = None


@pytest.fixture
def client():
    """Create test client."""
    if not APP_AVAILABLE:
        pytest.skip("UI app not available")
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    if not APP_AVAILABLE:
        pytest.skip("UI app not available")
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    store = UIDataStore(db_path=Path(db_path))
    yield store
    os.close(db_fd)
    os.unlink(db_path)


class TestEvidenceEngine:
    """Tests for Evidence Engine endpoints."""
    
    def test_evidence_search_missing_query(self, client):
        """Test evidence search without query."""
        response = client.post('/api/evidence/search', 
                              json={},
                              headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 400
    
    def test_evidence_search_requires_xhr(self, client):
        """Test that POST requires X-Requested-With header."""
        response = client.post('/api/evidence/search', json={'query': 'test'})
        assert response.status_code == 400
    
    def test_evidence_claim_missing_claim(self, client):
        """Test evidence claim without claim."""
        response = client.post('/api/evidence/claim',
                              json={},
                              headers={'X-Requested-With': 'XMLHttpRequest'})
        assert response.status_code == 400


class TestDecisionTrajectories:
    """Tests for Decision Trajectories endpoints."""
    
    def test_create_trajectory(self, client, temp_db):
        """Test creating a trajectory."""
        # Mock get_store to return temp_db
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            response = client.post('/api/trajectories',
                                  json={
                                      'agent_id': 'test_agent',
                                      'proposal_id': 'test_proposal',
                                      'goal': 'Test goal'
                                  },
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'trajectory_id' in data
        finally:
            ui.app.get_store = original_get_store
    
    def test_get_trajectories(self, client, temp_db):
        """Test getting trajectories."""
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            # Create a trajectory first
            temp_db.create_trajectory('traj_1', 'agent_1', 'proposal_1', goal='Test')
            
            response = client.get('/api/trajectories')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert len(data['trajectories']) >= 1
        finally:
            ui.app.get_store = original_get_store
    
    def test_add_trajectory_step(self, client, temp_db):
        """Test adding a step to trajectory."""
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            # Create trajectory first
            temp_db.create_trajectory('traj_1', 'agent_1', 'proposal_1')
            
            response = client.post('/api/trajectories/traj_1/step',
                                  json={
                                      'observation': 'Test observation',
                                      'action': 'test_action',
                                      'action_type': 'tool_call',
                                      'reward': 0.5
                                  },
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
        finally:
            ui.app.get_store = original_get_store


class TestTrainingMetrics:
    """Tests for Training Metrics endpoints."""
    
    def test_record_training_game(self, client, temp_db):
        """Test recording a training game."""
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            response = client.post('/api/training/games',
                                  json={
                                      'curriculum_agent': 'curriculum_1',
                                      'executor_agent': 'executor_1',
                                      'task': 'Test task',
                                      'task_difficulty': 0.7,
                                      'executor_solved': True,
                                      'executor_steps': 10
                                  },
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
        finally:
            ui.app.get_store = original_get_store
    
    def test_get_training_metrics(self, client, temp_db):
        """Test getting training metrics."""
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            # Record a game first
            temp_db.record_training_game(
                'game_1', 'curriculum_1', 'executor_1', 'Test task',
                0.7, True, 10
            )
            
            response = client.get('/api/training/metrics')
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'metrics' in data
            assert 'statistics' in data
        finally:
            ui.app.get_store = original_get_store


class TestWorkflowOrchestration:
    """Tests for Workflow Orchestration endpoints."""
    
    def test_create_workflow(self, client, temp_db):
        """Test creating a workflow."""
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            response = client.post('/api/workflows',
                                  json={
                                      'objective': 'Test objective',
                                      'agents': ['agent1', 'agent2']
                                  },
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'workflow_id' in data
        finally:
            ui.app.get_store = original_get_store
    
    def test_update_workflow_stage(self, client, temp_db):
        """Test updating workflow stage."""
        import ui.app
        original_get_store = ui.app.get_store
        ui.app.get_store = lambda: temp_db
        
        try:
            # Create workflow first
            temp_db.create_workflow('workflow_1', 'Test objective', ['agent1'])
            
            response = client.post('/api/workflows/workflow_1/stage',
                                  json={
                                      'stage': 'hypothesis_generation',
                                      'status': 'completed',
                                      'artifacts': []
                                  },
                                  headers={'X-Requested-With': 'XMLHttpRequest'})
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
        finally:
            ui.app.get_store = original_get_store


class TestSecurity:
    """Tests for security features."""
    
    def test_post_requires_xhr(self, client):
        """Test that POST endpoints require X-Requested-With header."""
        endpoints = [
            '/api/evidence/search',
            '/api/evidence/claim',
            '/api/trajectories',
            '/api/training/games',
            '/api/workflows',
        ]
        
        for endpoint in endpoints:
            response = client.post(endpoint, json={})
            assert response.status_code == 400, f"Endpoint {endpoint} should require XHR header"


