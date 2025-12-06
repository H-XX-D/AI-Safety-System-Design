"""
PDF Generator for AI Safety System Proposals
=============================================

Generates comprehensive PDF reports for proposals using ReportLab.
Includes all 16 sections, charts, and proper formatting.
"""

import io
import datetime as datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, Image, HRFlowable, ListFlowable, ListItem
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.lineplots import LinePlot
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class ProposalPDFGenerator:
    """Generates comprehensive PDF reports for proposals."""
    
    def __init__(self):
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF generation. Install with: pip install reportlab")
        
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ProposalTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1a1a2e'),
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#16213e'),
            borderPadding=5
        ))
        
        # Subsection style
        self.styles.add(ParagraphStyle(
            name='SubSection',
            parent=self.styles['Heading3'],
            fontSize=12,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor('#0f3460')
        ))
        
        # Body text style
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            leading=14
        ))
        
        # Code style
        self.styles.add(ParagraphStyle(
            name='Code',
            parent=self.styles['Normal'],
            fontName='Courier',
            fontSize=8,
            backColor=colors.HexColor('#f4f4f4'),
            borderColor=colors.HexColor('#ddd'),
            borderWidth=1,
            borderPadding=5,
            spaceAfter=10
        ))
        
        # Status badge styles
        self.styles.add(ParagraphStyle(
            name='StatusApproved',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            backColor=colors.HexColor('#28a745'),
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatusRejected',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            backColor=colors.HexColor('#dc3545'),
            alignment=TA_CENTER
        ))
        
        self.styles.add(ParagraphStyle(
            name='StatusPending',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.white,
            backColor=colors.HexColor('#ffc107'),
            alignment=TA_CENTER
        ))
        
        # Metadata style
        self.styles.add(ParagraphStyle(
            name='Metadata',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666'),
            spaceAfter=3
        ))
    
    def generate_proposal_pdf(self, proposal: Dict[str, Any]) -> bytes:
        """Generate a comprehensive PDF report for a proposal."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        
        # Title page
        story.extend(self._build_title_page(proposal))
        story.append(PageBreak())
        
        # Table of contents placeholder
        story.extend(self._build_table_of_contents())
        story.append(PageBreak())
        
        # Section 1: Core Information
        story.extend(self._build_core_info_section(proposal))
        
        # Section 2: The Idea
        story.extend(self._build_idea_section(proposal))
        
        # Section 3: Risk Assessment
        story.extend(self._build_risk_section(proposal))
        
        # Section 4: Implementation Process
        story.extend(self._build_implementation_section(proposal))
        
        # Section 5: Reasoning & Justification
        story.extend(self._build_reasoning_section(proposal))
        
        # Section 6: Experimental Results
        story.extend(self._build_experiments_section(proposal))
        
        # Section 7: Deception & Alignment Analysis
        story.extend(self._build_deception_section(proposal))
        
        # Section 8: Mitigation Strategies
        story.extend(self._build_mitigation_section(proposal))
        
        # Section 9: Peer Reviews
        story.extend(self._build_peer_reviews_section(proposal))
        
        # Section 10: ORKA Counterpoint
        story.extend(self._build_orka_section(proposal))
        
        # Section 11: Agent Defense & Response
        story.extend(self._build_defense_section(proposal))
        
        # Section 12: Final Testing & Validation
        story.extend(self._build_final_testing_section(proposal))
        
        # Section 13: VAL Offline Validation
        story.extend(self._build_val_section(proposal))
        
        # Section 14: Verification & Signatures
        story.extend(self._build_signatures_section(proposal))
        
        # Section 15: Approval & Deployment
        story.extend(self._build_deployment_section(proposal))
        
        # Section 16: Code Attachment
        story.extend(self._build_code_section(proposal))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    def _build_title_page(self, proposal: Dict[str, Any]) -> List:
        """Build the title page."""
        elements = []
        
        # Spacer at top
        elements.append(Spacer(1, 2*inch))
        
        # Logo placeholder (text-based)
        elements.append(Paragraph(
            "🛡️ AI SAFETY SYSTEM",
            ParagraphStyle(
                'LogoStyle',
                parent=self.styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#666'),
                alignment=TA_CENTER
            )
        ))
        elements.append(Spacer(1, 0.5*inch))
        
        # Title
        title = proposal.get('title', 'Untitled Proposal')
        elements.append(Paragraph(title, self.styles['ProposalTitle']))
        
        # Subtitle
        elements.append(Paragraph(
            "Comprehensive Proposal Report",
            ParagraphStyle(
                'Subtitle',
                parent=self.styles['Normal'],
                fontSize=14,
                textColor=colors.HexColor('#666'),
                alignment=TA_CENTER,
                spaceAfter=30
            )
        ))
        
        # Horizontal line
        elements.append(HRFlowable(
            width="80%",
            thickness=2,
            color=colors.HexColor('#1a1a2e'),
            spaceBefore=20,
            spaceAfter=20
        ))
        
        # Metadata table
        metadata = [
            ['Proposal ID:', proposal.get('id', proposal.get('proposal_id', 'N/A'))],
            ['Agent:', proposal.get('agent_id', 'N/A')],
            ['Component:', proposal.get('component', 'N/A')],
            ['Status:', proposal.get('status', 'N/A').upper()],
            ['Submitted:', proposal.get('timestamp_submitted', proposal.get('timestamp', 'N/A'))],
            ['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        meta_table = Table(metadata, colWidths=[2*inch, 4*inch])
        meta_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#666')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(meta_table)
        
        return elements
    
    def _build_table_of_contents(self) -> List:
        """Build table of contents."""
        elements = []
        
        elements.append(Paragraph("Table of Contents", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.25*inch))
        
        sections = [
            "1. Core Information",
            "2. The Idea",
            "3. Risk Assessment",
            "4. Implementation Process",
            "5. Reasoning & Justification",
            "6. Experimental Results",
            "7. Deception & Alignment Analysis",
            "8. Mitigation Strategies",
            "9. Peer Reviews",
            "10. ORKA Counterpoint",
            "11. Agent Defense & Response",
            "12. Final Testing & Validation",
            "13. VAL Offline Validation",
            "14. Verification & Signatures",
            "15. Approval & Deployment",
            "16. Code Attachment"
        ]
        
        for section in sections:
            elements.append(Paragraph(section, self.styles['BodyText']))
        
        return elements
    
    def _build_core_info_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 1: Core Information."""
        elements = []
        
        elements.append(Paragraph("1. Core Information", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        # Core info table
        data = [
            ['Field', 'Value'],
            ['Proposal ID', proposal.get('id', proposal.get('proposal_id', 'N/A'))],
            ['Agent ID', proposal.get('agent_id', 'N/A')],
            ['Title', proposal.get('title', 'N/A')],
            ['Component', proposal.get('component', 'N/A')],
            ['Status', proposal.get('status', 'N/A').upper()],
            ['Timestamp', proposal.get('timestamp_submitted', proposal.get('timestamp', 'N/A'))],
        ]
        
        table = Table(data, colWidths=[2*inch, 4.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.25*inch))
        
        return elements
    
    def _build_idea_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 2: The Idea."""
        elements = []
        
        elements.append(Paragraph("2. The Idea", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        idea = proposal.get('idea', {})
        
        # Description
        elements.append(Paragraph("Description", self.styles['SubSection']))
        desc = idea.get('description', proposal.get('description', 'No description provided.'))
        elements.append(Paragraph(desc, self.styles['BodyText']))
        
        # Motivation
        elements.append(Paragraph("Motivation", self.styles['SubSection']))
        motivation = idea.get('motivation', 'No motivation provided.')
        elements.append(Paragraph(motivation, self.styles['BodyText']))
        
        # Technical Approach
        elements.append(Paragraph("Technical Approach", self.styles['SubSection']))
        approach = idea.get('technical_approach', 'Not specified.')
        elements.append(Paragraph(approach, self.styles['BodyText']))
        
        # Expected Benefits
        elements.append(Paragraph("Expected Benefits", self.styles['SubSection']))
        benefits = idea.get('expected_benefits', [])
        if benefits:
            for benefit in benefits:
                elements.append(Paragraph(f"• {benefit}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No benefits listed.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_risk_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 3: Risk Assessment."""
        elements = []
        
        elements.append(Paragraph("3. Risk Assessment", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        risks = proposal.get('risks', {})
        
        # Overall risk score
        risk_score = risks.get('overall_risk_score', proposal.get('deception_confidence', 0))
        elements.append(Paragraph(f"<b>Overall Risk Score:</b> {risk_score:.2%}", self.styles['BodyText']))
        
        # Risk visualization
        elements.append(self._create_risk_bar(risk_score))
        elements.append(Spacer(1, 0.15*inch))
        
        # Technical Risks
        elements.append(Paragraph("Technical Risks", self.styles['SubSection']))
        tech_risks = risks.get('technical_risks', [])
        if tech_risks:
            for risk in tech_risks:
                if isinstance(risk, dict):
                    elements.append(Paragraph(
                        f"• <b>{risk.get('risk', 'Unknown')}</b> (Severity: {risk.get('severity', 'N/A')}, Likelihood: {risk.get('likelihood', 'N/A')})",
                        self.styles['BodyText']
                    ))
                    if risk.get('mitigation'):
                        elements.append(Paragraph(f"  Mitigation: {risk['mitigation']}", self.styles['Metadata']))
                else:
                    elements.append(Paragraph(f"• {risk}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No technical risks identified.", self.styles['BodyText']))
        
        # Safety Risks
        elements.append(Paragraph("Safety Risks", self.styles['SubSection']))
        safety_risks = risks.get('safety_risks', [])
        if safety_risks:
            for risk in safety_risks:
                if isinstance(risk, dict):
                    elements.append(Paragraph(
                        f"• <b>{risk.get('risk', 'Unknown')}</b> (Severity: {risk.get('severity', 'N/A')})",
                        self.styles['BodyText']
                    ))
                else:
                    elements.append(Paragraph(f"• {risk}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No safety risks identified.", self.styles['BodyText']))
        
        # Alignment Risks
        elements.append(Paragraph("Alignment Risks", self.styles['SubSection']))
        align_risks = risks.get('alignment_risks', [])
        if align_risks:
            for risk in align_risks:
                if isinstance(risk, dict):
                    elements.append(Paragraph(
                        f"• <b>{risk.get('risk', 'Unknown')}</b>",
                        self.styles['BodyText']
                    ))
                else:
                    elements.append(Paragraph(f"• {risk}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No alignment risks identified.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _create_risk_bar(self, score: float) -> Drawing:
        """Create a visual risk score bar."""
        d = Drawing(400, 30)
        
        # Background bar
        d.add(Rect(0, 10, 400, 15, fillColor=colors.HexColor('#e0e0e0'), strokeColor=None))
        
        # Risk level bar
        if score < 0.3:
            fill_color = colors.HexColor('#28a745')  # Green
        elif score < 0.6:
            fill_color = colors.HexColor('#ffc107')  # Yellow
        else:
            fill_color = colors.HexColor('#dc3545')  # Red
        
        bar_width = max(1, min(400, score * 400))
        d.add(Rect(0, 10, bar_width, 15, fillColor=fill_color, strokeColor=None))
        
        # Labels
        d.add(String(0, 0, "Low", fontSize=8, fillColor=colors.HexColor('#666')))
        d.add(String(190, 0, "Medium", fontSize=8, fillColor=colors.HexColor('#666')))
        d.add(String(380, 0, "High", fontSize=8, fillColor=colors.HexColor('#666')))
        
        return d
    
    def _build_implementation_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 4: Implementation Process."""
        elements = []
        
        elements.append(Paragraph("4. Implementation Process", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        process = proposal.get('process', {})
        phases = process.get('phases', [])
        
        if phases:
            data = [['Phase', 'Duration', 'Status', 'Artifacts']]
            for phase in phases:
                if isinstance(phase, dict):
                    artifacts = ', '.join(phase.get('artifacts', [])) or 'None'
                    data.append([
                        phase.get('phase', 'N/A'),
                        f"{phase.get('duration_hours', 0)}h",
                        phase.get('status', 'N/A'),
                        artifacts[:50] + '...' if len(artifacts) > 50 else artifacts
                    ])
            
            table = Table(data, colWidths=[1.5*inch, 1*inch, 1*inch, 3*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No implementation phases defined.", self.styles['BodyText']))
        
        # Total effort
        total_hours = process.get('total_effort_hours', 0)
        completion = process.get('completion_percentage', 0)
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(f"<b>Total Effort:</b> {total_hours} hours | <b>Completion:</b> {completion}%", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_reasoning_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 5: Reasoning & Justification."""
        elements = []
        
        elements.append(Paragraph("5. Reasoning & Justification", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        reasoning = proposal.get('reasoning', {})
        
        # Problem Statement
        elements.append(Paragraph("Problem Statement", self.styles['SubSection']))
        problem = reasoning.get('problem_statement', 'Not specified.')
        elements.append(Paragraph(problem, self.styles['BodyText']))
        
        # Alternatives Considered
        elements.append(Paragraph("Alternatives Considered", self.styles['SubSection']))
        alternatives = reasoning.get('alternatives_considered', [])
        if alternatives:
            for alt in alternatives:
                if isinstance(alt, dict):
                    elements.append(Paragraph(f"• <b>{alt.get('name', 'Alternative')}</b>: {alt.get('reason_rejected', 'N/A')}", self.styles['BodyText']))
                else:
                    elements.append(Paragraph(f"• {alt}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No alternatives documented.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_experiments_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 6: Experimental Results."""
        elements = []
        
        elements.append(Paragraph("6. Experimental Results", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        experiments = proposal.get('experiments', {})
        
        # Test environment
        env = experiments.get('test_environment', 'Not specified')
        elements.append(Paragraph(f"<b>Test Environment:</b> {env}", self.styles['BodyText']))
        
        # Test metrics
        passed = experiments.get('test_cases_passed', 0)
        failed = experiments.get('test_cases_failed', 0)
        pass_rate = experiments.get('pass_rate', 0)
        
        data = [
            ['Metric', 'Value'],
            ['Tests Passed', str(passed)],
            ['Tests Failed', str(failed)],
            ['Pass Rate', f"{pass_rate:.1%}" if isinstance(pass_rate, float) else str(pass_rate)],
        ]
        
        table = Table(data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(table)
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_deception_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 7: Deception & Alignment Analysis."""
        elements = []
        
        elements.append(Paragraph("7. Deception & Alignment Analysis", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        deception = proposal.get('deception_analysis', {})
        
        if deception:
            detected = deception.get('deception_detected', False)
            confidence = deception.get('confidence', 0)
            deception_type = deception.get('deception_type', 'none')
            severity = deception.get('severity', 'none')
            
            # Status indicator
            if detected:
                elements.append(Paragraph(
                    f"⚠️ <b>DECEPTION DETECTED</b> - Type: {deception_type}, Severity: {severity}",
                    ParagraphStyle('Warning', parent=self.styles['BodyText'], textColor=colors.HexColor('#dc3545'))
                ))
            else:
                elements.append(Paragraph(
                    "✓ <b>No Deception Detected</b>",
                    ParagraphStyle('Success', parent=self.styles['BodyText'], textColor=colors.HexColor('#28a745'))
                ))
            
            elements.append(Paragraph(f"<b>Confidence:</b> {confidence:.1%}", self.styles['BodyText']))
            
            # Reasons
            reasons = deception.get('reasons', [])
            if reasons:
                elements.append(Paragraph("Analysis Reasons:", self.styles['SubSection']))
                for reason in reasons:
                    elements.append(Paragraph(f"• {reason}", self.styles['BodyText']))
            
            # Evidence
            evidence = deception.get('evidence', [])
            if evidence:
                elements.append(Paragraph("Evidence:", self.styles['SubSection']))
                for ev in evidence:
                    elements.append(Paragraph(f"• {ev}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No deception analysis available.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_mitigation_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 8: Mitigation Strategies."""
        elements = []
        
        elements.append(Paragraph("8. Mitigation Strategies", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        mitigation = proposal.get('mitigation', {})
        
        # Technical mitigations
        elements.append(Paragraph("Technical Mitigations", self.styles['SubSection']))
        tech = mitigation.get('technical', [])
        if tech:
            for item in tech:
                elements.append(Paragraph(f"• {item}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No technical mitigations specified.", self.styles['BodyText']))
        
        # Safety mitigations
        elements.append(Paragraph("Safety Mitigations", self.styles['SubSection']))
        safety = mitigation.get('safety', [])
        if safety:
            for item in safety:
                elements.append(Paragraph(f"• {item}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No safety mitigations specified.", self.styles['BodyText']))
        
        # Monitoring plan
        elements.append(Paragraph("Monitoring Plan", self.styles['SubSection']))
        monitoring = mitigation.get('monitoring', 'Standard monitoring procedures apply.')
        elements.append(Paragraph(monitoring, self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_peer_reviews_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 9: Peer Reviews."""
        elements = []
        
        elements.append(Paragraph("9. Peer Reviews", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        peer_reviews = proposal.get('peer_reviews', {})
        reviews = peer_reviews.get('reviews', proposal.get('reviews', []))
        approval_rate = peer_reviews.get('approval_rate', 0)
        
        elements.append(Paragraph(f"<b>Overall Approval Rate:</b> {approval_rate:.0%}", self.styles['BodyText']))
        elements.append(Spacer(1, 0.1*inch))
        
        if reviews:
            for i, review in enumerate(reviews, 1):
                if isinstance(review, dict):
                    reviewer = review.get('reviewer', review.get('agent_id', f'Reviewer {i}'))
                    vote = review.get('vote', review.get('approved', 'N/A'))
                    score = review.get('score', review.get('confidence', 'N/A'))
                    feedback = review.get('feedback', review.get('comment', 'No feedback'))
                    
                    elements.append(Paragraph(f"<b>Review #{i} - {reviewer}</b>", self.styles['SubSection']))
                    elements.append(Paragraph(f"Vote: {vote} | Score: {score}", self.styles['Metadata']))
                    elements.append(Paragraph(feedback, self.styles['BodyText']))
                else:
                    elements.append(Paragraph(f"• {review}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No peer reviews recorded.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_orka_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 10: ORKA Counterpoint."""
        elements = []
        
        elements.append(Paragraph("10. ORKA Counterpoint", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        orka = proposal.get('orka_counterpoint', {})
        
        # Adversarial analysis
        elements.append(Paragraph("Adversarial Analysis", self.styles['SubSection']))
        analysis = orka.get('adversarial_analysis', 'No adversarial analysis performed.')
        elements.append(Paragraph(analysis, self.styles['BodyText']))
        
        # Attack vectors tested
        elements.append(Paragraph("Attack Vectors Tested", self.styles['SubSection']))
        vectors = orka.get('attack_vectors_tested', [])
        if vectors:
            for vector in vectors:
                elements.append(Paragraph(f"• {vector}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No attack vectors documented.", self.styles['BodyText']))
        
        # Worst case scenarios
        elements.append(Paragraph("Worst Case Scenarios", self.styles['SubSection']))
        scenarios = orka.get('worst_case_scenarios', [])
        if scenarios:
            for scenario in scenarios:
                elements.append(Paragraph(f"• {scenario}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No worst case scenarios documented.", self.styles['BodyText']))
        
        # Recommendation
        recommendation = orka.get('recommendation', 'No recommendation')
        elements.append(Paragraph(f"<b>ORKA Recommendation:</b> {recommendation}", self.styles['BodyText']))
        
        # Concerns
        concerns = orka.get('concerns', [])
        if concerns:
            elements.append(Paragraph("Concerns:", self.styles['SubSection']))
            for concern in concerns:
                elements.append(Paragraph(f"• {concern}", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_defense_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 11: Agent Defense & Response."""
        elements = []
        
        elements.append(Paragraph("11. Agent Defense & Response", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        defense = proposal.get('agent_defense', {})
        
        # Response to concerns
        elements.append(Paragraph("Response to Concerns", self.styles['SubSection']))
        responses = defense.get('response_to_concerns', [])
        if responses:
            for response in responses:
                elements.append(Paragraph(f"• {response}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No responses documented.", self.styles['BodyText']))
        
        # Revisions made
        elements.append(Paragraph("Revisions Made", self.styles['SubSection']))
        revisions = defense.get('revisions_made', [])
        if revisions:
            for revision in revisions:
                elements.append(Paragraph(f"• {revision}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("No revisions documented.", self.styles['BodyText']))
        
        # Updated timeline
        timeline = defense.get('updated_timeline', 'No timeline updates')
        elements.append(Paragraph(f"<b>Updated Timeline:</b> {timeline}", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_final_testing_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 12: Final Testing & Validation."""
        elements = []
        
        elements.append(Paragraph("12. Final Testing & Validation", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        final_testing = proposal.get('final_testing', {})
        test_suite = final_testing.get('comprehensive_test_suite', {})
        
        if test_suite:
            data = [
                ['Test Type', 'Count', 'Passed'],
                ['Unit Tests', str(test_suite.get('unit_tests', 0)), '✓'],
                ['Integration Tests', str(test_suite.get('integration_tests', 0)), '✓'],
                ['End-to-End Tests', str(test_suite.get('end_to_end_tests', 0)), '✓'],
                ['Security Tests', str(test_suite.get('security_tests', 0)), '✓'],
                ['Performance Tests', str(test_suite.get('performance_tests', 0)), '✓'],
                ['TOTAL', str(test_suite.get('total', 0)), f"{test_suite.get('pass_rate', 1):.0%}"],
            ]
            
            table = Table(data, colWidths=[2.5*inch, 2*inch, 2*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0f0f0')),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No final testing data available.", self.styles['BodyText']))
        
        # Safety validation
        safety_val = final_testing.get('safety_validation', {})
        if safety_val:
            elements.append(Spacer(1, 0.15*inch))
            elements.append(Paragraph("Safety Validation Results:", self.styles['SubSection']))
            for check, result in safety_val.items():
                icon = "✓" if result == 'passed' else "✗"
                elements.append(Paragraph(f"{icon} {check.replace('_', ' ').title()}: {result}", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_val_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 13: VAL Offline Validation."""
        elements = []
        
        elements.append(Paragraph("13. VAL Offline Validation", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        val = proposal.get('val_validation', {})
        
        if val:
            # Validation details
            duration = val.get('validation_duration_hours', 0)
            recommendation = val.get('val_recommendation', 'PENDING')
            confidence = val.get('val_confidence', 0)
            
            elements.append(Paragraph(f"<b>Validation Duration:</b> {duration} hours", self.styles['BodyText']))
            elements.append(Paragraph(f"<b>VAL Recommendation:</b> {recommendation}", self.styles['BodyText']))
            elements.append(Paragraph(f"<b>VAL Confidence:</b> {confidence:.0%}", self.styles['BodyText']))
            
            # Checks performed
            checks = val.get('val_checks_performed', [])
            if checks:
                elements.append(Paragraph("Checks Performed:", self.styles['SubSection']))
                for check in checks:
                    elements.append(Paragraph(f"• {check}", self.styles['BodyText']))
            
            # Findings
            findings = val.get('val_findings', [])
            if findings:
                elements.append(Paragraph("Findings:", self.styles['SubSection']))
                for finding in findings:
                    elements.append(Paragraph(f"• {finding}", self.styles['BodyText']))
        else:
            elements.append(Paragraph("VAL validation pending.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_signatures_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 14: Verification & Signatures."""
        elements = []
        
        elements.append(Paragraph("14. Verification & Signatures", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        signatures = proposal.get('signatures', {})
        
        if signatures:
            data = [['Signer', 'Timestamp', 'Signature Hash']]
            for signer, sig_data in signatures.items():
                if isinstance(sig_data, dict):
                    timestamp = sig_data.get('timestamp', 'N/A')
                    sig_hash = sig_data.get('hash', sig_data.get('signature', 'N/A'))
                    # Truncate hash for display
                    if len(str(sig_hash)) > 20:
                        sig_hash = str(sig_hash)[:20] + '...'
                    data.append([signer, timestamp, sig_hash])
                else:
                    data.append([signer, 'N/A', str(sig_data)[:20] + '...'])
            
            table = Table(data, colWidths=[1.5*inch, 2.5*inch, 2.5*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No signatures recorded.", self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_deployment_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 15: Approval & Deployment."""
        elements = []
        
        elements.append(Paragraph("15. Approval & Deployment", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        deployment = proposal.get('deployment', {})
        status = proposal.get('status', 'pending')
        
        # Status badge
        status_upper = status.upper()
        if status == 'approved':
            elements.append(Paragraph(f"✓ <b>STATUS: {status_upper}</b>", 
                ParagraphStyle('Approved', parent=self.styles['BodyText'], textColor=colors.HexColor('#28a745'))))
        elif status == 'rejected':
            elements.append(Paragraph(f"✗ <b>STATUS: {status_upper}</b>", 
                ParagraphStyle('Rejected', parent=self.styles['BodyText'], textColor=colors.HexColor('#dc3545'))))
        else:
            elements.append(Paragraph(f"⏳ <b>STATUS: {status_upper}</b>", 
                ParagraphStyle('Pending', parent=self.styles['BodyText'], textColor=colors.HexColor('#ffc107'))))
        
        # Deployment plan
        if deployment:
            elements.append(Paragraph("Deployment Plan:", self.styles['SubSection']))
            plan = deployment.get('plan', deployment.get('deployment_plan', 'Standard deployment procedure'))
            elements.append(Paragraph(plan, self.styles['BodyText']))
            
            # Rollback plan
            rollback = deployment.get('rollback_plan', 'Standard rollback procedure')
            elements.append(Paragraph("Rollback Plan:", self.styles['SubSection']))
            elements.append(Paragraph(rollback, self.styles['BodyText']))
        
        elements.append(Spacer(1, 0.25*inch))
        return elements
    
    def _build_code_section(self, proposal: Dict[str, Any]) -> List:
        """Build Section 16: Code Attachment."""
        elements = []
        
        elements.append(Paragraph("16. Code Attachment", self.styles['SectionHeader']))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ddd')))
        
        code = proposal.get('code', {})
        
        # Files modified
        modified = code.get('files_modified', [])
        if modified:
            elements.append(Paragraph("Files Modified:", self.styles['SubSection']))
            for file in modified:
                elements.append(Paragraph(f"• {file}", self.styles['BodyText']))
        
        # Files added
        added = code.get('files_added', [])
        if added:
            elements.append(Paragraph("Files Added:", self.styles['SubSection']))
            for file in added:
                elements.append(Paragraph(f"• {file}", self.styles['BodyText']))
        
        # Statistics
        lines_changed = code.get('total_lines_changed', 0)
        coverage = code.get('test_coverage', 0)
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(f"<b>Total Lines Changed:</b> {lines_changed}", self.styles['BodyText']))
        elements.append(Paragraph(f"<b>Test Coverage:</b> {coverage:.0%}" if isinstance(coverage, float) else f"<b>Test Coverage:</b> {coverage}", self.styles['BodyText']))
        
        # Code attached indicator
        if code.get('code_attached', False):
            elements.append(Paragraph("✓ Code artifacts attached to this report.", self.styles['BodyText']))
        else:
            elements.append(Paragraph("ℹ Code artifacts available via separate download.", self.styles['BodyText']))
        
        # Proposed code snippet (if available)
        proposed_code = proposal.get('proposed_code', '')
        if proposed_code and len(proposed_code) < 2000:
            elements.append(Paragraph("Proposed Code:", self.styles['SubSection']))
            # Escape HTML entities in code
            safe_code = proposed_code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            elements.append(Paragraph(f"<font face='Courier' size='8'>{safe_code}</font>", self.styles['Code']))
        
        elements.append(Spacer(1, 0.5*inch))
        
        # Footer
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1a1a2e')))
        elements.append(Paragraph(
            f"Report generated by AI Safety System on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=8, textColor=colors.HexColor('#999'), alignment=TA_CENTER)
        ))
        
        return elements


def generate_orka_report_pdf(data: Dict[str, Any]) -> bytes:
    """Generate a comprehensive ORKA oversight report as PDF."""
    if not REPORTLAB_AVAILABLE:
        raise ImportError("ReportLab is required for PDF generation")
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    story.append(Paragraph(
        "ORKA Oversight Report",
        ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, alignment=TA_CENTER)
    ))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor('#666'))
    ))
    story.append(Spacer(1, 0.5*inch))
    
    # Summary statistics
    story.append(Paragraph("Summary Statistics", styles['Heading2']))
    
    summary_data = [
        ['Metric', 'Value'],
        ['Total Proposals', str(data.get('total_proposals', 0))],
        ['Approved', str(data.get('approved_count', 0))],
        ['Pending', str(data.get('pending_count', 0))],
        ['Rejected', str(data.get('rejected_count', 0))],
        ['Active Agents', str(data.get('active_agents', 0))],
        ['Deception Alerts', str(data.get('deception_alerts', 0))],
        ['Collusion Attempts', str(data.get('collusion_attempts', 0))],
    ]
    
    table = Table(summary_data, colWidths=[3*inch, 3*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#ddd')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
    ]))
    story.append(table)
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "This report was automatically generated by the ORKA AI Safety System.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#999'), alignment=TA_CENTER)
    ))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# Export functions for use in app.py
__all__ = ['ProposalPDFGenerator', 'generate_orka_report_pdf', 'REPORTLAB_AVAILABLE']

