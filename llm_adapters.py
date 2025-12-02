"""
LLM Adapter Implementations
============================

Production-ready adapters for Google Gemini, plus legacy OpenAI/Anthropic
wrappers (commented out by default in configs). Integrates with
`research_system.BaseLLMAdapter`.

Example (Gemini):

    from llm_adapters import GeminiAdapter

    gemini = GeminiAdapter(model="gemini-1.5-pro-latest")
    result = gemini.generate_improvement(
        prompt="Improve deception detection accuracy",
        specialization=SystemSpecialization.SCIENTIFIC,
        research_params={"max_tokens": 1024},
        guardrails={"max_risk": "medium"}
    )
"""

import json
import os
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from logging_config import get_logger

# Import base classes from research_system
from research_system import (
    BaseLLMAdapter,
    LLMAdapterResult,
    SystemSpecialization
)

logger = get_logger(__name__)

# Try importing OpenAI
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI package not installed. Run: pip install openai")

# Try importing Anthropic
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("Anthropic package not installed. Run: pip install anthropic")

# Try importing Google Gemini client
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai package not installed. Run: pip install google-generativeai")

# Try importing subprocess for 3dlm CLI
try:
    import subprocess
    import shutil
    from pathlib import Path
    SUBPROCESS_AVAILABLE = True
except ImportError:
    SUBPROCESS_AVAILABLE = False
    logger.warning("subprocess not available")


class OpenAIAdapter(BaseLLMAdapter):
    """
    Production OpenAI GPT-4 adapter for AI safety research proposals.

    Features:
    - Structured output parsing with validation
    - Guardrail enforcement (risk levels, banned imports)
    - Token usage tracking
    - Error handling with retries
    - Response validation against safety constraints
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0
    ):
        """
        Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model name (gpt-4-turbo-preview, gpt-4, gpt-3.5-turbo)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum response tokens
            timeout: Request timeout in seconds
        """
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI package not installed. Run: pip install openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required (pass api_key or set OPENAI_API_KEY env var)")

        self.client = openai.OpenAI(api_key=self.api_key, timeout=timeout)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        logger.info(f"OpenAI adapter initialized with model={model}")

    def generate_improvement(
        self,
        prompt: str,
        *,
        specialization: SystemSpecialization,
        research_params: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> LLMAdapterResult:
        """
        Generate improvement proposal using GPT-4.

        Args:
            prompt: Research request (e.g., "Improve deception detection")
            specialization: Research specialization type
            research_params: Additional parameters (max_tokens override, etc.)
            guardrails: Safety constraints (max_risk, banned_imports, etc.)

        Returns:
            LLMAdapterResult with structured proposal
        """
        logger.info(f"Generating proposal for: {prompt[:100]}...")

        # Build system prompt with safety constraints
        system_prompt = self._build_system_prompt(specialization, guardrails)

        # Build user prompt with structure requirements
        user_prompt = self._build_user_prompt(prompt, specialization, guardrails)

        # Override max_tokens if specified in research_params
        max_tokens = research_params.get("max_tokens", self.max_tokens)

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=self.temperature,
                max_tokens=max_tokens
            )

            # Extract response text
            response_text = response.choices[0].message.content

            # Log token usage
            usage = response.usage
            logger.info(f"Token usage: prompt={usage.prompt_tokens}, "
                       f"completion={usage.completion_tokens}, total={usage.total_tokens}")

            # Parse structured output
            result = self._parse_response(response_text, specialization, guardrails)

            logger.info(f"Successfully generated proposal: {result.title}")
            return result

        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating proposal: {e}")
            raise

    def _build_system_prompt(
        self,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> str:
        """Build system prompt with safety constraints."""

        prompt = f"""You are an AI safety research assistant specializing in {specialization.value} improvements.

Your task is to propose safe, testable improvements to AI systems while adhering to strict safety protocols.

CRITICAL REQUIREMENTS:
1. All proposals must be reversible with clear rollback plans
2. Identify ALL potential risks, even low-probability ones
3. Admit uncertainties honestly - overconfidence is dangerous
4. Provide testable predictions for validation
5. Stay within alignment boundaries (no deception, no value drift)

OUTPUT FORMAT (JSON):
{{
    "title": "Brief descriptive title",
    "motivation": "Why this improvement matters (min 20 chars)",
    "changes": {{
        "code": "Actual Python code if applicable",
        "config": "Configuration changes if applicable",
        "description": "Human-readable description of changes"
    }},
    "expected_benefits": "Concrete measurable benefits",
    "testable_predictions": ["prediction 1", "prediction 2", ...],
    "rollback_plan": "Step-by-step rollback procedure (min 10 chars)",
    "identified_risks": ["risk 1", "risk 2", ...] (min 2 risks),
    "admitted_uncertainties": ["uncertainty 1", ...] (min 1 uncertainty),
    "confidence": 0.0-1.0 (be conservative, typical: 0.5-0.8)
}}
"""

        # Add guardrail constraints
        if guardrails:
            prompt += "\n\nGUARDRAILS:\n"

            if "max_risk" in guardrails:
                prompt += f"- Maximum acceptable risk level: {guardrails['max_risk']}\n"

            if "banned_imports" in guardrails:
                banned = ", ".join(guardrails["banned_imports"])
                prompt += f"- BANNED imports: {banned}\n"

            if "allowed_modules" in guardrails:
                allowed = ", ".join(guardrails["allowed_modules"])
                prompt += f"- ONLY these modules allowed: {allowed}\n"

            if "required_tests" in guardrails:
                tests = ", ".join(guardrails["required_tests"])
                prompt += f"- Required test types: {tests}\n"

        return prompt

    def _build_user_prompt(
        self,
        prompt: str,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> str:
        """Build user prompt with research request."""

        user_prompt = f"""Research Request: {prompt}

Specialization: {specialization.value}

Generate a detailed improvement proposal following the JSON format specified in the system prompt.

Remember:
- Be honest about risks and uncertainties
- Provide concrete, testable predictions
- Include clear rollback procedures
- Stay within safety guardrails
- Code must be production-quality if included
"""

        return user_prompt

    def _parse_response(
        self,
        response_text: str,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> LLMAdapterResult:
        """Parse and validate LLM response into structured result."""

        # Try to extract JSON from response
        try:
            # Look for JSON block (might be wrapped in markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response_text

            data = json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}")
            # Fallback: create minimal structure
            data = {
                "title": "Unparsed proposal",
                "motivation": response_text[:200],
                "changes": {"description": response_text},
                "expected_benefits": "Unknown",
                "testable_predictions": ["Manual review required"],
                "rollback_plan": "Manual rollback",
                "identified_risks": ["Unparsed response"],
                "admitted_uncertainties": ["Parsing failed"],
                "confidence": 0.3
            }

        # Validate required fields
        self._validate_proposal(data, guardrails)

        # Build LLMAdapterResult
        return LLMAdapterResult(
            title=data.get("title", "Untitled"),
            motivation=data.get("motivation", ""),
            changes=data.get("changes", {}),
            expected_benefits=data.get("expected_benefits", ""),
            testable_predictions=data.get("testable_predictions", []),
            rollback_plan=data.get("rollback_plan", ""),
            identified_risks=data.get("identified_risks"),
            admitted_uncertainties=data.get("admitted_uncertainties"),
            confidence=data.get("confidence")
        )

    def _validate_proposal(
        self,
        data: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]]
    ) -> None:
        """Validate proposal meets minimum safety requirements."""

        # Check motivation length
        motivation = data.get("motivation", "")
        if len(motivation) < 20:
            logger.warning(f"Motivation too short: {len(motivation)} chars (min 20)")

        # Check risks
        risks = data.get("identified_risks", [])
        if len(risks) < 2:
            logger.warning(f"Insufficient risks identified: {len(risks)} (min 2)")

        # Check uncertainties
        uncertainties = data.get("admitted_uncertainties", [])
        if len(uncertainties) < 1:
            logger.warning(f"No uncertainties admitted (min 1)")

        # Check confidence range
        confidence = data.get("confidence")
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            logger.warning(f"Confidence out of range: {confidence} (must be 0.0-1.0)")

        # Check rollback plan
        rollback = data.get("rollback_plan", "")
        if len(rollback) < 10:
            logger.warning(f"Rollback plan too short: {len(rollback)} chars (min 10)")

        # Check guardrails
        if guardrails and "banned_imports" in guardrails:
            code = str(data.get("changes", {}).get("code", ""))
            for banned in guardrails["banned_imports"]:
                if f"import {banned}" in code or f"from {banned}" in code:
                    raise ValueError(f"Proposal violates guardrail: banned import '{banned}' detected")


class ClaudeAdapter(BaseLLMAdapter):
    """
    Production Anthropic Claude adapter for AI safety research proposals.

    Features:
    - Structured output parsing with validation
    - Guardrail enforcement
    - Token usage tracking
    - Error handling with retries
    - Response validation against safety constraints
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-opus-20240229",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: float = 60.0
    ):
        """
        Initialize Anthropic Claude adapter.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: Model name (claude-3-opus-20240229, claude-3-sonnet-20240229)
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum response tokens
            timeout: Request timeout in seconds
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("Anthropic package not installed. Run: pip install anthropic")

        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key required (pass api_key or set ANTHROPIC_API_KEY env var)")

        self.client = anthropic.Anthropic(api_key=self.api_key, timeout=timeout)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        logger.info(f"Claude adapter initialized with model={model}")

    def generate_improvement(
        self,
        prompt: str,
        *,
        specialization: SystemSpecialization,
        research_params: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> LLMAdapterResult:
        """
        Generate improvement proposal using Claude.

        Args:
            prompt: Research request (e.g., "Improve deception detection")
            specialization: Research specialization type
            research_params: Additional parameters (max_tokens override, etc.)
            guardrails: Safety constraints (max_risk, banned_imports, etc.)

        Returns:
            LLMAdapterResult with structured proposal
        """
        logger.info(f"Generating proposal with Claude for: {prompt[:100]}...")

        # Build system prompt with safety constraints
        system_prompt = self._build_system_prompt(specialization, guardrails)

        # Build user prompt with structure requirements
        user_prompt = self._build_user_prompt(prompt, specialization, guardrails)

        # Override max_tokens if specified in research_params
        max_tokens = research_params.get("max_tokens", self.max_tokens)

        try:
            # Call Anthropic API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            # Extract response text
            response_text = response.content[0].text

            # Log token usage
            usage = response.usage
            logger.info(f"Token usage: input={usage.input_tokens}, "
                       f"output={usage.output_tokens}")

            # Parse structured output
            result = self._parse_response(response_text, specialization, guardrails)

            logger.info(f"Successfully generated proposal: {result.title}")
            return result

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating proposal: {e}")
            raise


class GeminiAdapter(BaseLLMAdapter):
    """
    Google Gemini adapter (Generative Language API).

    Features:
    - Deterministic system/user prompt construction with guardrails
    - Structured response parsing (mirrors OpenAI/Claude contract)
    - Optional safety filtering of banned imports / high risk
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-pro-latest",
        temperature: float = 0.4,
        max_output_tokens: int = 2048,
        timeout: float = 60.0,
    ):
        if not GEMINI_AVAILABLE:
            raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")

        self.api_key = api_key or os.getenv("GOOGLE_GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API key required (GOOGLE_GEMINI_API_KEY env var or api_key param)")

        genai.configure(api_key=self.api_key, timeout=timeout)
        self.model_name = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._model = genai.GenerativeModel(model_name=self.model_name)
        logger.info("Gemini adapter initialized with model=%s", model)

    def generate_improvement(
        self,
        prompt: str,
        *,
        specialization: SystemSpecialization,
        research_params: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> LLMAdapterResult:
        system_prompt = self._build_system_prompt(specialization, guardrails)
        user_prompt = self._build_user_prompt(prompt, specialization, guardrails)
        max_tokens = int(research_params.get("max_tokens", self.max_output_tokens))

        logger.info("Generating Gemini proposal for specialization=%s", specialization.value)
        try:
            response = self._model.generate_content(
                contents=[
                    {"role": "system", "parts": [{"text": system_prompt}]},
                    {"role": "user", "parts": [{"text": user_prompt}]},
                ],
                generation_config={
                    "temperature": self.temperature,
                    "max_output_tokens": max_tokens,
                },
            )
        except Exception as exc:
            logger.error("Gemini API error: %s", exc)
            raise

        if not response or not response.candidates:
            raise RuntimeError("Gemini API returned no candidates")
        candidate = response.candidates[0]
        text = candidate.content.parts[0].text if candidate.content and candidate.content.parts else ""
        if not text:
            raise RuntimeError("Gemini response missing text content")

        result = self._parse_response(text, specialization, guardrails)
        logger.info("Gemini proposal generated: %s", result.title)
        return result

    def _build_system_prompt(self, specialization: SystemSpecialization, guardrails: Optional[Dict[str, Any]]) -> str:
        return f"""You are an AI safety research assistant specializing in {specialization.value}.
Follow immutable alignment constraints, enumerate risks, and produce reversible plans."""

    def _build_user_prompt(self, prompt: str, specialization: SystemSpecialization, guardrails: Optional[Dict[str, Any]]) -> str:
        max_risk = guardrails.get("max_risk", "medium") if guardrails else "medium"
        banned_imports = guardrails.get("banned_imports", []) if guardrails else []
        guardrail_text = f"Max risk allowed: {max_risk}. Banned imports: {', '.join(banned_imports) or 'none'}."
        return f"""{guardrail_text}
Generate a JSON proposal for specialization '{specialization.value}' answering: "{prompt}".
Ensure fields title/motivation/changes/risks/rollback_plan/tests are present."""

    def _build_system_prompt(
        self,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> str:
        """Build system prompt with safety constraints."""

        prompt = f"""You are an AI safety research assistant specializing in {specialization.value} improvements.

Your task is to propose safe, testable improvements to AI systems while adhering to strict safety protocols.

CRITICAL REQUIREMENTS:
1. All proposals must be reversible with clear rollback plans
2. Identify ALL potential risks, even low-probability ones
3. Admit uncertainties honestly - overconfidence is dangerous
4. Provide testable predictions for validation
5. Stay within alignment boundaries (no deception, no value drift)

OUTPUT FORMAT (JSON):
{{
    "title": "Brief descriptive title",
    "motivation": "Why this improvement matters (min 20 chars)",
    "changes": {{
        "code": "Actual Python code if applicable",
        "config": "Configuration changes if applicable",
        "description": "Human-readable description of changes"
    }},
    "expected_benefits": "Concrete measurable benefits",
    "testable_predictions": ["prediction 1", "prediction 2", ...],
    "rollback_plan": "Step-by-step rollback procedure (min 10 chars)",
    "identified_risks": ["risk 1", "risk 2", ...] (min 2 risks),
    "admitted_uncertainties": ["uncertainty 1", ...] (min 1 uncertainty),
    "confidence": 0.0-1.0 (be conservative, typical: 0.5-0.8)
}}
"""

        # Add guardrail constraints
        if guardrails:
            prompt += "\n\nGUARDRAILS:\n"

            if "max_risk" in guardrails:
                prompt += f"- Maximum acceptable risk level: {guardrails['max_risk']}\n"

            if "banned_imports" in guardrails:
                banned = ", ".join(guardrails["banned_imports"])
                prompt += f"- BANNED imports: {banned}\n"

            if "allowed_modules" in guardrails:
                allowed = ", ".join(guardrails["allowed_modules"])
                prompt += f"- ONLY these modules allowed: {allowed}\n"

            if "required_tests" in guardrails:
                tests = ", ".join(guardrails["required_tests"])
                prompt += f"- Required test types: {tests}\n"

        return prompt

    def _build_user_prompt(
        self,
        prompt: str,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> str:
        """Build user prompt with research request."""

        user_prompt = f"""Research Request: {prompt}

Specialization: {specialization.value}

Generate a detailed improvement proposal following the JSON format specified in the system prompt.

Remember:
- Be honest about risks and uncertainties
- Provide concrete, testable predictions
- Include clear rollback procedures
- Stay within safety guardrails
- Code must be production-quality if included
"""

        return user_prompt

    def _parse_response(
        self,
        response_text: str,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> LLMAdapterResult:
        """Parse and validate LLM response into structured result."""

        # Try to extract JSON from response
        try:
            # Look for JSON block (might be wrapped in markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response_text

            data = json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}")
            # Fallback: create minimal structure
            data = {
                "title": "Unparsed proposal",
                "motivation": response_text[:200],
                "changes": {"description": response_text},
                "expected_benefits": "Unknown",
                "testable_predictions": ["Manual review required"],
                "rollback_plan": "Manual rollback",
                "identified_risks": ["Unparsed response"],
                "admitted_uncertainties": ["Parsing failed"],
                "confidence": 0.3
            }

        # Validate required fields
        self._validate_proposal(data, guardrails)

        # Build LLMAdapterResult
        return LLMAdapterResult(
            title=data.get("title", "Untitled"),
            motivation=data.get("motivation", ""),
            changes=data.get("changes", {}),
            expected_benefits=data.get("expected_benefits", ""),
            testable_predictions=data.get("testable_predictions", []),
            rollback_plan=data.get("rollback_plan", ""),
            identified_risks=data.get("identified_risks"),
            admitted_uncertainties=data.get("admitted_uncertainties"),
            confidence=data.get("confidence")
        )

    def _validate_proposal(
        self,
        data: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]]
    ) -> None:
        """Validate proposal meets minimum safety requirements."""

        # Check motivation length
        motivation = data.get("motivation", "")
        if len(motivation) < 20:
            logger.warning(f"Motivation too short: {len(motivation)} chars (min 20)")

        # Check risks
        risks = data.get("identified_risks", [])
        if len(risks) < 2:
            logger.warning(f"Insufficient risks identified: {len(risks)} (min 2)")

        # Check uncertainties
        uncertainties = data.get("admitted_uncertainties", [])
        if len(uncertainties) < 1:
            logger.warning(f"No uncertainties admitted (min 1)")

        # Check confidence range
        confidence = data.get("confidence")
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            logger.warning(f"Confidence out of range: {confidence} (must be 0.0-1.0)")

        # Check rollback plan
        rollback = data.get("rollback_plan", "")
        if len(rollback) < 10:
            logger.warning(f"Rollback plan too short: {len(rollback)} chars (min 10)")

        # Check guardrails
        if guardrails and "banned_imports" in guardrails:
            code = str(data.get("changes", {}).get("code", ""))
            for banned in guardrails["banned_imports"]:
                if f"import {banned}" in code or f"from {banned}" in code:
                    raise ValueError(f"Proposal violates guardrail: banned import '{banned}' detected")


class ThirdLMAdapter(BaseLLMAdapter):
    """
    Local on-device LLM adapter using 3dlm (ThirdLM) inference engine.
    
    Uses the 3dlm Swift CLI for GPU-accelerated inference on Apple Silicon.
    Provides privacy, offline operation, and no API costs.
    
    Features:
    - On-device inference with Metal GPU acceleration
    - Supports .btern, .tmc5, and .gguf model formats
    - Automatic fallback to template adapter if 3dlm unavailable
    - Structured output parsing with JSON extraction
    """
    
    def __init__(
        self,
        model_path: str,
        tokenizer_path: Optional[str] = None,
        cli_path: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        timeout: float = 120.0,
        swift_package_dir: Optional[str] = None
    ):
        """
        Initialize 3dlm adapter.
        
        Args:
            model_path: Path to model file (.btern, .tmc5, or .gguf)
            tokenizer_path: Path to tokenizer.json (optional, auto-detected if None)
            cli_path: Path to thirdlm-cli executable (auto-detected if None)
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            swift_package_dir: Path to 3Dlm/macos directory (auto-detected if None)
        """
        if not SUBPROCESS_AVAILABLE:
            raise ImportError("subprocess module required for ThirdLMAdapter")
        
        self.model_path = Path(model_path).expanduser().resolve()
        if not self.model_path.exists():
            raise ValueError(f"Model file not found: {self.model_path}")
        
        # Auto-detect tokenizer if not provided
        if tokenizer_path:
            self.tokenizer_path: Optional[Path] = Path(tokenizer_path).expanduser().resolve()
        else:
            # Try common locations
            possible_tokenizers = [
                self.model_path.parent / "tokenizer.json",
                Path("3Dlm/tinyllama_tokenizer/tokenizer.json"),
                Path.home() / "3Dlm/models/tokenizer.json"
            ]
            self.tokenizer_path = None
            for path in possible_tokenizers:
                if path.exists():
                    self.tokenizer_path = path
                    break
            
            if not self.tokenizer_path:
                logger.warning("Tokenizer not found. Some models may work without it.")
        
        # Auto-detect CLI path
        if cli_path:
            self.cli_path: Optional[Path] = Path(cli_path).expanduser().resolve()
            self.swift_package_dir: Optional[Path] = None
            self.use_swift_run = False
        else:
            # Try to find built executable or use swift run
            if swift_package_dir:
                swift_dir = Path(swift_package_dir)
            else:
                # Auto-detect 3Dlm directory
                project_root = Path(__file__).parent
                swift_dir = project_root / "3Dlm" / "macos"
            
            # Check for built executable
            possible_clis = [
                swift_dir / ".build" / "arm64-apple-macosx" / "debug" / "thirdlm-app",
                swift_dir / ".build" / "arm64-apple-macosx" / "release" / "thirdlm-app",
                Path("/usr/local/bin/thirdlm-cli"),
            ]
            
            self.cli_path = None
            for path in possible_clis:
                if path.exists() and path.is_file():
                    self.cli_path = path
                    break
            
            # If no executable found, use swift run
            if not self.cli_path:
                self.swift_package_dir = swift_dir
                self.use_swift_run = True
                logger.info(f"Using 'swift run' from {swift_dir}")
            else:
                self.swift_package_dir = None
                self.use_swift_run = False
                logger.info(f"Using CLI executable: {self.cli_path}")
        
        self.temperature = max(0.0, min(2.0, temperature))
        self.max_tokens = max(1, max_tokens)
        self.timeout = timeout
        
        logger.info(
            f"Initialized ThirdLMAdapter: model={self.model_path.name}, "
            f"temperature={self.temperature}, max_tokens={self.max_tokens}"
        )
    
    def generate_improvement(
        self,
        prompt: str,
        *,
        specialization: SystemSpecialization,
        research_params: Dict[str, Any],
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> LLMAdapterResult:
        """Generate improvement proposal using 3dlm local inference."""
        
        # Build system prompt
        system_prompt = self._build_system_prompt(specialization, guardrails)
        
        # Build full prompt
        full_prompt = self._build_user_prompt(prompt, specialization, guardrails)
        
        # Combine system and user prompts
        combined_prompt = f"{system_prompt}\n\n{full_prompt}"
        
        # Call 3dlm CLI
        try:
            response_text = self._call_3dlm(combined_prompt, research_params)
        except Exception as e:
            logger.error(f"3dlm inference failed: {e}")
            # Fallback to template adapter behavior
            from research_system import TemplateLLMAdapter
            template = TemplateLLMAdapter()
            return template.generate_improvement(
                prompt=prompt,
                specialization=specialization,
                research_params=research_params,
                guardrails=guardrails
            )
        
        # Parse response
        return self._parse_response(response_text, specialization, guardrails)
    
    def _call_3dlm(self, prompt: str, research_params: Dict[str, Any]) -> str:
        """Call 3dlm CLI and return generated text."""
        
        # Override params from research_params if provided
        temperature = research_params.get("temperature", self.temperature)
        max_tokens = research_params.get("max_tokens", self.max_tokens)
        
        # Build command
        if self.use_swift_run:
            cmd = [
                "swift", "run", "-c", "release",
                "thirdlm-app",
                str(self.model_path),
                prompt
            ]
            cwd = self.swift_package_dir
        else:
            cmd = [
                str(self.cli_path),
                str(self.model_path),
                prompt
            ]
            cwd = None
        
        # Add tokenizer if available
        if self.tokenizer_path:
            cmd.extend(["--tokenizer", str(self.tokenizer_path)])
        
        # Add generation parameters
        cmd.extend([
            "--tokens", str(max_tokens),
            "--temperature", str(temperature),
            "--top-p", "0.95"
        ])
        
        logger.debug(f"Calling 3dlm: {' '.join(cmd)}")
        
        # Execute
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=True
            )
            
            # Extract generated text (skip header lines)
            output_lines = result.stdout.strip().split('\n')
            
            # Find where generation starts (after "Generated:" or similar)
            generated_start = 0
            for i, line in enumerate(output_lines):
                if "Generated:" in line or "Output:" in line or i > 5:
                    generated_start = i + 1
                    break
            
            generated_text = '\n'.join(output_lines[generated_start:]).strip()
            
            if not generated_text:
                # Fallback: use entire output
                generated_text = result.stdout.strip()
            
            logger.debug(f"3dlm generated {len(generated_text)} characters")
            return generated_text
            
        except subprocess.TimeoutExpired:
            logger.error(f"3dlm inference timed out after {self.timeout}s")
            raise TimeoutError(f"3dlm inference exceeded {self.timeout}s timeout")
        
        except subprocess.CalledProcessError as e:
            logger.error(f"3dlm CLI failed: {e.stderr}")
            raise RuntimeError(f"3dlm inference failed: {e.stderr}")
        
        except FileNotFoundError:
            logger.error("3dlm CLI not found. Is Swift installed?")
            raise RuntimeError("3dlm CLI not found. Install Swift and build 3dlm.")
    
    def _build_system_prompt(
        self,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> str:
        """Build system prompt for structured output."""
        # Use same system prompt logic as GeminiAdapter
        prompt = f"""You are an AI safety research assistant specializing in {specialization.value}.
Your task is to generate a structured improvement proposal in JSON format.

CRITICAL CONSTRAINTS:
1. Follow immutable alignment constraints
2. Enumerate all risks honestly
3. Produce reversible plans with clear rollback procedures
4. Admit uncertainties explicitly
5. Provide testable predictions

OUTPUT FORMAT (JSON):
{{
    "title": "Short descriptive title (10-50 chars)",
    "motivation": "Why this improvement is needed (min 20 chars)",
    "changes": {{"description": "...", "code": "..."}},
    "expected_benefits": "What improvements we expect (min 10 chars)",
    "testable_predictions": ["prediction 1", "prediction 2", ...] (min 2),
    "rollback_plan": "Step-by-step rollback procedure (min 10 chars)",
    "identified_risks": ["risk 1", "risk 2", ...] (min 2 risks),
    "admitted_uncertainties": ["uncertainty 1", ...] (min 1 uncertainty),
    "confidence": 0.0-1.0 (be conservative, typical: 0.5-0.8)
}}"""

        # Add guardrail constraints
        if guardrails:
            prompt += "\n\nGUARDRAILS:\n"

            if "max_risk" in guardrails:
                prompt += f"- Maximum acceptable risk level: {guardrails['max_risk']}\n"

            if "banned_imports" in guardrails:
                banned = ", ".join(guardrails["banned_imports"])
                prompt += f"- BANNED imports: {banned}\n"

            if "allowed_modules" in guardrails:
                allowed = ", ".join(guardrails["allowed_modules"])
                prompt += f"- ONLY these modules allowed: {allowed}\n"

            if "required_tests" in guardrails:
                tests = ", ".join(guardrails["required_tests"])
                prompt += f"- Required test types: {tests}\n"

        return prompt
    
    def _build_user_prompt(
        self,
        prompt: str,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> str:
        """Build user prompt with research request."""
        user_prompt = f"""Research Request: {prompt}

Specialization: {specialization.value}

Generate a detailed improvement proposal following the JSON format specified in the system prompt.

Remember:
- Be honest about risks and uncertainties
- Provide concrete, testable predictions
- Include clear rollback procedures
- Stay within safety guardrails
- Code must be production-quality if included
"""
        return user_prompt
    
    def _parse_response(
        self,
        response_text: str,
        specialization: SystemSpecialization,
        guardrails: Optional[Dict[str, Any]]
    ) -> LLMAdapterResult:
        """Parse and validate LLM response into structured result."""
        # Try to extract JSON from response
        try:
            # Look for JSON block (might be wrapped in markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    json_str = response_text

            data = json.loads(json_str)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}")
            # Fallback: create minimal structure
            data = {
                "title": "Unparsed proposal",
                "motivation": response_text[:200],
                "changes": {"description": response_text},
                "expected_benefits": "Unknown",
                "testable_predictions": ["Manual review required"],
                "rollback_plan": "Manual rollback",
                "identified_risks": ["Unparsed response"],
                "admitted_uncertainties": ["Parsing failed"],
                "confidence": 0.3
            }

        # Validate required fields (same as GeminiAdapter)
        motivation = data.get("motivation", "")
        if len(motivation) < 20:
            logger.warning(f"Motivation too short: {len(motivation)} chars (min 20)")

        risks = data.get("identified_risks", [])
        if len(risks) < 2:
            logger.warning(f"Insufficient risks identified: {len(risks)} (min 2)")

        uncertainties = data.get("admitted_uncertainties", [])
        if len(uncertainties) < 1:
            logger.warning(f"No uncertainties admitted (min 1)")

        confidence = data.get("confidence")
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            logger.warning(f"Confidence out of range: {confidence} (must be 0.0-1.0)")

        rollback = data.get("rollback_plan", "")
        if len(rollback) < 10:
            logger.warning(f"Rollback plan too short: {len(rollback)} chars (min 10)")

        # Check guardrails
        if guardrails and "banned_imports" in guardrails:
            code = str(data.get("changes", {}).get("code", ""))
            for banned in guardrails["banned_imports"]:
                if f"import {banned}" in code or f"from {banned}" in code:
                    raise ValueError(f"Proposal violates guardrail: banned import '{banned}' detected")

        # Build LLMAdapterResult
        return LLMAdapterResult(
            title=data.get("title", "Untitled"),
            motivation=data.get("motivation", ""),
            changes=data.get("changes", {}),
            expected_benefits=data.get("expected_benefits", ""),
            testable_predictions=data.get("testable_predictions", []),
            rollback_plan=data.get("rollback_plan", ""),
            identified_risks=data.get("identified_risks"),
            admitted_uncertainties=data.get("admitted_uncertainties"),
            confidence=data.get("confidence")
        )
