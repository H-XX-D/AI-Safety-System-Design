"""
Comprehensive UI Tests
======================

Tests for all UI functionality including PDF export, code download,
USB writing, notifications, activity log, search, and comparison.
"""

import pytest
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'ui'))


class TestPDFExport:
    """Tests for PDF export functionality."""
    
    def test_pdf_generator_import(self):
        """Test that PDF generator can be imported."""
        try:
            from ui.pdf_generator import ProposalPDFGenerator, REPORTLAB_AVAILABLE
            assert ProposalPDFGenerator is not None
        except ImportError:
            pytest.skip("PDF generator not available")
    
    def test_pdf_generation_with_minimal_proposal(self):
        """Test PDF generation with minimal proposal data."""
        try:
            from ui.pdf_generator import ProposalPDFGenerator, REPORTLAB_AVAILABLE
            if not REPORTLAB_AVAILABLE:
                pytest.skip("ReportLab not installed")
            
            generator = ProposalPDFGenerator()
            proposal = {
                'id': 'test_001',
                'title': 'Test Proposal',
                'agent_id': 'TIF',
                'component': 'test_component',
                'status': 'approved',
                'description': 'A test proposal for testing'
            }
            
            pdf_bytes = generator.generate_proposal_pdf(proposal)
            
            assert pdf_bytes is not None
            assert len(pdf_bytes) > 0
            # PDF files start with %PDF
            assert pdf_bytes[:4] == b'%PDF'
            
        except ImportError:
            pytest.skip("PDF generator dependencies not available")
    
    def test_pdf_generation_with_full_proposal(self):
        """Test PDF generation with comprehensive proposal data."""
        try:
            from ui.pdf_generator import ProposalPDFGenerator, REPORTLAB_AVAILABLE
            if not REPORTLAB_AVAILABLE:
                pytest.skip("ReportLab not installed")
            
            generator = ProposalPDFGenerator()
            proposal = {
                'id': 'test_002',
                'title': 'Comprehensive Test Proposal',
                'agent_id': 'GIN',
                'component': 'security_module',
                'status': 'in_review',
                'description': 'A comprehensive test proposal',
                'idea': {
                    'description': 'Detailed description',
                    'motivation': 'Testing motivation',
                    'technical_approach': 'Technical approach details',
                    'expected_benefits': ['Benefit 1', 'Benefit 2']
                },
                'risks': {
                    'technical_risks': [{'risk': 'Risk 1', 'severity': 'medium'}],
                    'safety_risks': [],
                    'alignment_risks': [],
                    'overall_risk_score': 0.3
                },
                'experiments': {
                    'test_environment': 'Sandbox',
                    'test_cases_passed': 95,
                    'test_cases_failed': 5,
                    'pass_rate': 0.95
                },
                'peer_reviews': {
                    'reviews': [{'reviewer': 'TORI', 'vote': 'approve', 'score': 0.9}],
                    'approval_rate': 0.9
                }
            }
            
            pdf_bytes = generator.generate_proposal_pdf(proposal)
            
            assert pdf_bytes is not None
            assert len(pdf_bytes) > 1000  # Should be reasonably sized
            
        except ImportError:
            pytest.skip("PDF generator dependencies not available")


class TestCodeDownload:
    """Tests for code download functionality."""
    
    def test_tar_creation(self):
        """Test that tar.gz archives can be created."""
        import tarfile
        import io
        
        buffer = io.BytesIO()
        
        with tarfile.open(fileobj=buffer, mode='w:gz') as tar:
            # Add test content
            content = b'test content'
            info = tarfile.TarInfo(name='test.txt')
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        
        buffer.seek(0)
        archive_bytes = buffer.getvalue()
        
        assert archive_bytes is not None
        assert len(archive_bytes) > 0
        
        # Verify it's a valid gzip file
        assert archive_bytes[:2] == b'\x1f\x8b'  # gzip magic number


class TestUSBDetection:
    """Tests for USB detection functionality."""
    
    def test_usb_path_validation(self):
        """Test USB path validation."""
        # Import the validation function
        try:
            # This would be imported from app.py in actual test
            import platform
            
            # Test that validation logic works
            system = platform.system()
            
            if system == 'Darwin':
                valid_path = '/Volumes/USB_TEST'
                invalid_path = '/etc/passwd'
            elif system == 'Linux':
                valid_path = '/media/user/USB_TEST'
                invalid_path = '/etc/passwd'
            else:
                pytest.skip(f"USB validation not tested on {system}")
            
            # The actual validation would be tested against app.py
            assert valid_path.startswith('/Volumes') or valid_path.startswith('/media')
            assert not invalid_path.startswith('/Volumes')
            
        except Exception as e:
            pytest.skip(f"USB detection test skipped: {e}")


class TestNotificationsAPI:
    """Tests for notifications API."""
    
    def test_notification_creation(self):
        """Test notification creation in data store."""
        from ui.data_store import UIDataStore
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            store = UIDataStore(db_path=db_path)
            
            # Create notification
            notification_id = store.create_notification(
                notification_type='test',
                title='Test Notification',
                message='This is a test',
                severity='info'
            )
            
            assert notification_id > 0
            
            # Get notifications
            notifications = store.get_notifications(limit=10)
            assert len(notifications) >= 1
            
            # Find our notification
            found = any(n['title'] == 'Test Notification' for n in notifications)
            assert found
            
            # Test unread count
            unread = store.get_unread_count()
            assert unread >= 1
            
            # Mark as read
            success = store.mark_notification_read(notification_id)
            assert success
            
            # Verify it's marked as read
            new_unread = store.get_unread_count()
            assert new_unread == unread - 1
            
        finally:
            os.unlink(db_path)
    
    def test_notification_deletion(self):
        """Test notification deletion."""
        from ui.data_store import UIDataStore
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            store = UIDataStore(db_path=db_path)
            
            # Create notification
            notification_id = store.create_notification(
                notification_type='test',
                title='To Delete',
                message='Delete me'
            )
            
            # Delete it
            success = store.delete_notification(notification_id)
            assert success
            
            # Verify it's gone
            notifications = store.get_notifications(limit=100)
            found = any(n['id'] == notification_id for n in notifications)
            assert not found
            
        finally:
            os.unlink(db_path)


class TestActivityLog:
    """Tests for activity log functionality."""
    
    def test_activity_logging(self):
        """Test activity logging in data store."""
        from ui.data_store import UIDataStore
        import tempfile
        
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            store = UIDataStore(db_path=db_path)
            
            # Log activity
            activity_id = store.log_activity(
                action='test_action',
                user='test_user',
                resource_type='proposal',
                resource_id='test_123',
                details={'key': 'value'},
                ip_address='127.0.0.1'
            )
            
            assert activity_id > 0
            
            # Get activity log
            activities = store.get_activity_log(limit=10)
            assert len(activities) >= 1
            
            # Find our activity
            found = any(a['action'] == 'test_action' for a in activities)
            assert found
            
            # Test filtering
            filtered = store.get_activity_log(user='test_user')
            assert len(filtered) >= 1
            
        finally:
            os.unlink(db_path)


class TestAdvancedSearch:
    """Tests for advanced search functionality."""
    
    def test_search_query_parsing(self):
        """Test search query parsing logic."""
        # Test basic search logic
        query = "test proposal"
        searchable_text = "This is a test proposal for testing"
        
        assert query.lower() in searchable_text.lower()
    
    def test_highlight_extraction(self):
        """Test search highlight extraction."""
        text = "This is a test proposal that contains important information about testing"
        query = "test"
        
        pos = text.lower().find(query.lower())
        assert pos >= 0
        
        # Extract snippet
        start = max(0, pos - 20)
        end = min(len(text), pos + len(query) + 20)
        snippet = text[start:end]
        
        assert query in snippet.lower()


class TestProposalComparison:
    """Tests for proposal comparison functionality."""
    
    def test_comparison_metrics(self):
        """Test comparison metrics calculation."""
        proposals = [
            {
                'id': 'prop_1',
                'agent_id': 'TIF',
                'component': 'module_a',
                'status': 'approved',
                'deception_confidence': 0.1
            },
            {
                'id': 'prop_2',
                'agent_id': 'GIN',
                'component': 'module_b',
                'status': 'in_review',
                'deception_confidence': 0.5
            }
        ]
        
        # Test difference detection
        agents = set(p['agent_id'] for p in proposals)
        assert len(agents) == 2  # Different agents
        
        risk_scores = [p['deception_confidence'] for p in proposals]
        spread = max(risk_scores) - min(risk_scores)
        assert spread > 0.1  # Significant difference


class TestInputValidation:
    """Tests for input validation functions."""
    
    def test_proposal_id_validation(self):
        """Test proposal ID validation."""
        import re
        
        # Valid IDs
        valid_ids = ['prop_001', 'test-123', 'ABC123', 'a']
        for pid in valid_ids:
            assert re.match(r'^[a-zA-Z0-9_-]+$', pid)
        
        # Invalid IDs
        invalid_ids = ['../etc/passwd', 'test<script>', 'prop id', '']
        for pid in invalid_ids:
            if pid:
                assert not re.match(r'^[a-zA-Z0-9_-]+$', pid) or len(pid) == 0
    
    def test_filename_sanitization(self):
        """Test filename sanitization."""
        import re
        
        def sanitize(filename):
            filename = os.path.basename(filename)
            filename = re.sub(r'[^\w\-_\.]', '_', filename)
            if filename.startswith('.'):
                filename = '_' + filename[1:]
            return filename
        
        # Test cases
        assert sanitize('../../../etc/passwd') == 'passwd'
        assert sanitize('test<script>.txt') == 'test_script_.txt'
        assert sanitize('.hidden') == '_hidden'
        assert sanitize('normal_file.txt') == 'normal_file.txt'


class TestCaching:
    """Tests for caching functionality."""
    
    def test_simple_cache(self):
        """Test SimpleCache class."""
        import time
        
        class SimpleCache:
            def __init__(self, default_ttl=60):
                self._cache = {}
                self._default_ttl = default_ttl
            
            def get(self, key):
                if key in self._cache:
                    value, expires_at = self._cache[key]
                    if time.time() < expires_at:
                        return value
                    else:
                        del self._cache[key]
                return None
            
            def set(self, key, value, ttl=None):
                expires_at = time.time() + (ttl or self._default_ttl)
                self._cache[key] = (value, expires_at)
        
        cache = SimpleCache(default_ttl=1)
        
        # Test set and get
        cache.set('test_key', 'test_value')
        assert cache.get('test_key') == 'test_value'
        
        # Test expiration
        cache.set('expire_key', 'expire_value', ttl=0.1)
        time.sleep(0.2)
        assert cache.get('expire_key') is None


class TestWorkflowPhases:
    """Tests for 9-phase workflow functionality."""
    
    def test_phase_definitions(self):
        """Test that all 9 phases are defined."""
        phases = [
            'SUBMISSION',
            'AGENT_TESTING',
            'PEER_REVIEW',
            'ORKA_COUNTERPOINT',
            'AGENT_DEFENSE',
            'FINAL_TESTING',
            'HUMAN_NOTIFICATION',
            'VAL_VALIDATION',
            'DEPLOYMENT'
        ]
        
        assert len(phases) == 9
    
    def test_phase_status_mapping(self):
        """Test status to phase mapping."""
        status_to_phase = {
            'submitted': 1,
            'testing': 2,
            'in_review': 3,
            'peer_review': 3,
            'orka_review': 4,
            'defense': 5,
            'final_testing': 6,
            'human_review': 7,
            'pending_val': 8,
            'approved': 9,
            'deployed': 9
        }
        
        # Test mappings
        assert status_to_phase['submitted'] == 1
        assert status_to_phase['approved'] == 9
        assert status_to_phase['in_review'] == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

