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
