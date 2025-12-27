"""
Logist Intelligence Observer Module

This module provides intelligent log analysis and state detection capabilities
for the Logist system. It uses regex patterns to identify job states, detect
transitions, and provide contextual information about job execution.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Pattern, Set
from dataclasses import dataclass, field
from enum import Enum

from ..job_state import JobStates


class DetectionConfidence(Enum):
    """Confidence levels for state detection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CERTAIN = "certain"


@dataclass
class StateDetection:
    """Represents a detected state with metadata."""
    state: str
    confidence: DetectionConfidence
    timestamp: datetime
    pattern_name: str
    matched_text: str
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TransitionDetection:
    """Represents a detected state transition."""
    from_state: str
    to_state: str
    confidence: DetectionConfidence
    timestamp: datetime
    trigger_pattern: str
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class RegexPattern:
    """Represents a compiled regex pattern with metadata."""

    def __init__(self, name: str, pattern: str, flags: int = 0,
                 associated_states: Optional[List[str]] = None,
                 description: str = ""):
        self.name = name
        self.pattern = pattern
        self.flags = flags
        self.associated_states = associated_states or []
        self.description = description
        self._compiled: Optional[Pattern] = None

    @property
    def compiled(self) -> Pattern:
        """Get the compiled regex pattern (lazy compilation)."""
        if self._compiled is None:
            self._compiled = re.compile(self.pattern, self.flags)
        return self._compiled

    def matches(self, text: str) -> Optional[re.Match]:
        """Check if the pattern matches the given text."""
        return self.compiled.search(text)


class StatePatternDictionary:
    """
    Dictionary of regex patterns for detecting job states and transitions.

    This class maintains a comprehensive set of patterns for identifying
    different job execution states from log output and other sources.
    """

    def __init__(self):
        self.patterns: Dict[str, RegexPattern] = {}
        self.state_patterns: Dict[str, List[str]] = {}
        self._initialize_patterns()

    def _initialize_patterns(self):
        """Initialize the default set of regex patterns."""

        # Core execution state patterns
        self._add_pattern(RegexPattern(
            "job_started",
            r"(?:job|task|process)\s+(?:started|initiated|beginning|launch)",
            re.IGNORECASE,
            ["DRAFT", "PENDING"],
            "Detects job startup messages"
        ))

        self._add_pattern(RegexPattern(
            "execution_begun",
            r"(?:execution|running|active|processing)\s+(?:started|began|initiated)",
            re.IGNORECASE,
            ["PENDING", "RUNNING"],
            "Detects when execution actually begins"
        ))

        self._add_pattern(RegexPattern(
            "worker_activation",
            r"(?:worker|agent)\s+(?:activated|engaged|running|executing)",
            re.IGNORECASE,
            ["RUNNING"],
            "Detects worker/agent activation"
        ))

        self._add_pattern(RegexPattern(
            "supervisor_review",
            r"(?:supervisor|reviewer|checker)\s+(?:activated|engaged|reviewing|analyzing)",
            re.IGNORECASE,
            ["REVIEW_REQUIRED", "REVIEWING"],
            "Detects supervisor review activation"
        ))

        # Completion patterns
        self._add_pattern(RegexPattern(
            "task_completed",
            r"(?:task|job|process|operation)\s+(?:completed|finished|done|successful)",
            re.IGNORECASE,
            ["REVIEW_REQUIRED", "APPROVAL_REQUIRED", "SUCCESS"],
            "Detects successful task completion"
        ))

        self._add_pattern(RegexPattern(
            "worker_completed",
            r"(?:worker|agent)\s+(?:completed|finished|done)\s+(?:task|work|execution)",
            re.IGNORECASE,
            ["REVIEW_REQUIRED"],
            "Detects worker completion requiring review"
        ))

        self._add_pattern(RegexPattern(
            "supervisor_approved",
            r"(?:supervisor|reviewer)\s+(?:approved|accepted|confirmed|validated)",
            re.IGNORECASE,
            ["APPROVAL_REQUIRED", "SUCCESS"],
            "Detects supervisor approval"
        ))

        # Error and failure patterns
        self._add_pattern(RegexPattern(
            "error_occurred",
            r"(?:error|exception|failure|fault|problem)\s+(?:occurred|detected|found|raised)",
            re.IGNORECASE,
            ["INTERVENTION_REQUIRED", "CANCELED", "FAILED"],
            "Detects general error conditions"
        ))

        self._add_pattern(RegexPattern(
            "stuck_detected",
            r"(?:stuck|hung|frozen|deadlock|timeout|unresponsive)",
            re.IGNORECASE,
            ["INTERVENTION_REQUIRED"],
            "Detects stuck/hung processes"
        ))

        self._add_pattern(RegexPattern(
            "retry_needed",
            r"(?:retry|attempt|try\s+again|re-attempt)\s+(?:needed|required|requested)",
            re.IGNORECASE,
            ["PENDING"],
            "Detects when retry is needed"
        ))

        # Network and external service patterns
        self._add_pattern(RegexPattern(
            "api_call",
            r"(?:api|http|request|call)\s+(?:to|made|sent|received)",
            re.IGNORECASE,
            ["RUNNING"],
            "Detects API/external service interactions"
        ))

        self._add_pattern(RegexPattern(
            "network_error",
            r"(?:network|connection|timeout|unreachable|dns|ssl)\s+(?:error|failure|issue)",
            re.IGNORECASE,
            ["INTERVENTION_REQUIRED"],
            "Detects network-related errors"
        ))

        # Resource and system patterns
        self._add_pattern(RegexPattern(
            "resource_exhausted",
            r"(?:memory|disk|cpu|resource)\s+(?:exhausted|full|limit|out\s+of)",
            re.IGNORECASE,
            ["INTERVENTION_REQUIRED", "CANCELED"],
            "Detects resource exhaustion"
        ))

        self._add_pattern(RegexPattern(
            "permission_denied",
            r"(?:permission|access|authorization|forbidden|denied)",
            re.IGNORECASE,
            ["INTERVENTION_REQUIRED"],
            "Detects permission/access issues"
        ))

        # Progress and status patterns
        self._add_pattern(RegexPattern(
            "progress_update",
            r"(?:\d+(?:\.\d+)?%|step\s+\d+|phase\s+\d+|progress|status)",
            re.IGNORECASE,
            [],  # Can be in any state
            "Detects progress updates"
        ))

        self._add_pattern(RegexPattern(
            "waiting_input",
            r"(?:waiting|awaiting|pending)\s+(?:input|response|approval|confirmation)",
            re.IGNORECASE,
            ["REVIEW_REQUIRED", "APPROVAL_REQUIRED"],
            "Detects waiting states"
        ))

    def _add_pattern(self, pattern: RegexPattern):
        """Add a pattern to the dictionary."""
        self.patterns[pattern.name] = pattern

        # Update reverse mapping
        for state in pattern.associated_states:
            if state not in self.state_patterns:
                self.state_patterns[state] = []
            self.state_patterns[state].append(pattern.name)

    def add_custom_pattern(self, name: str, pattern: str, associated_states: List[str] = None,
                          description: str = "", flags: int = 0):
        """
        Add a custom regex pattern to the dictionary.

        Args:
            name: Unique name for the pattern
            pattern: Regex pattern string
            associated_states: List of states this pattern can indicate
            description: Human-readable description
            flags: Regex flags (e.g., re.IGNORECASE)
        """
        if name in self.patterns:
            raise ValueError(f"Pattern '{name}' already exists")

        custom_pattern = RegexPattern(name, pattern, flags, associated_states, description)
        self._add_pattern(custom_pattern)

    def get_patterns_for_state(self, state: str) -> List[RegexPattern]:
        """
        Get all patterns associated with a specific state.

        Args:
            state: Job state name

        Returns:
            List of patterns that can indicate this state
        """
        pattern_names = self.state_patterns.get(state, [])
        return [self.patterns[name] for name in pattern_names]

    def detect_state(self, text: str, context_state: Optional[str] = None) -> Optional[StateDetection]:
        """
        Analyze text to detect the most likely job state.

        Args:
            text: Text to analyze (log output, etc.)
            context_state: Current known state for context

        Returns:
            StateDetection if a state is detected, None otherwise
        """
        best_detection: Optional[StateDetection] = None
        best_score = 0

        # Check all patterns
        for pattern_name, pattern in self.patterns.items():
            match = pattern.matches(text)
            if match:
                # Calculate confidence based on pattern specificity and context
                confidence, detected_state = self._calculate_detection_confidence(
                    pattern, match, text, context_state
                )

                # Convert enum to numeric value for comparison
                confidence_value = confidence.value if hasattr(confidence, 'value') else confidence
                if confidence_value > best_score:
                    best_detection = StateDetection(
                        state=detected_state,
                        confidence=confidence,
                        timestamp=datetime.now(),
                        pattern_name=pattern_name,
                        matched_text=match.group(0),
                        context={"original_text": text, "context_state": context_state},
                        metadata={"match_span": match.span(), "groups": match.groups()}
                    )
                    best_score = confidence_value

        return best_detection

    def analyze_log_segment(self, log_lines: List[str], current_state: str = None) -> Dict[str, Any]:
        """
        Analyze log segment (compatibility method for tests).

        Args:
            log_lines: List of log lines to analyze
            current_state: Current job state

        Returns:
            Analysis results
        """
        return self.pattern_dict.analyze_log_segment(log_lines, current_state)

    def _calculate_detection_confidence(self, pattern: RegexPattern, match: re.Match,
                                      text: str, context_state: str = None) -> Tuple[DetectionConfidence, str]:
        """
        Calculate confidence score for a pattern match.

        Returns:
            Tuple of (confidence_level, detected_state)
        """
        confidence = DetectionConfidence.LOW
        detected_state = pattern.associated_states[0] if pattern.associated_states else "UNKNOWN"

        # Base confidence on pattern specificity
        if len(pattern.associated_states) == 1:
            confidence = DetectionConfidence.MEDIUM
        elif len(pattern.associated_states) > 3:
            confidence = DetectionConfidence.LOW

        # Boost confidence based on context
        if context_state and detected_state in self._get_valid_transitions(context_state):
            confidence = DetectionConfidence(confidence.value + 1)

        # Boost confidence for exact matches or specific patterns
        matched_text = match.group(0).lower()
        if any(word in matched_text for word in ["error", "failed", "exception"]):
            if "INTERVENTION_REQUIRED" in pattern.associated_states:
                confidence = DetectionConfidence.HIGH

        if any(word in matched_text for word in ["completed", "success", "done"]):
            if "SUCCESS" in pattern.associated_states or "REVIEW_REQUIRED" in pattern.associated_states:
                confidence = DetectionConfidence.HIGH

        return confidence, detected_state

    def _get_valid_transitions(self, from_state: str) -> Set[str]:
        """Get valid state transitions from a given state."""
        # Simplified transition map - could be expanded
        transitions = {
            "DRAFT": {"PENDING"},
            "PENDING": {"RUNNING", "CANCELED"},
            "RUNNING": {"REVIEW_REQUIRED", "INTERVENTION_REQUIRED", "SUCCESS", "FAILED"},
            "REVIEW_REQUIRED": {"REVIEWING", "APPROVAL_REQUIRED", "INTERVENTION_REQUIRED"},
            "REVIEWING": {"APPROVAL_REQUIRED", "INTERVENTION_REQUIRED", "REVIEW_REQUIRED"},
            "APPROVAL_REQUIRED": {"SUCCESS", "PENDING", "CANCELED"},
            "INTERVENTION_REQUIRED": {"PENDING", "CANCELED"},
        }
        return transitions.get(from_state, set())

    def detect_transition(self, text: str, current_state: str) -> Optional[TransitionDetection]:
        """
        Detect if the text indicates a state transition.

        Args:
            text: Text to analyze
            current_state: Current job state

        Returns:
            TransitionDetection if a transition is detected, None otherwise
        """
        # Look for patterns that indicate movement between states
        transition_patterns = {
            ("PENDING", "RUNNING"): ["execution_begun", "worker_activation"],
            ("RUNNING", "REVIEW_REQUIRED"): ["worker_completed", "task_completed"],
            ("REVIEW_REQUIRED", "APPROVAL_REQUIRED"): ["supervisor_approved"],
            ("RUNNING", "INTERVENTION_REQUIRED"): ["error_occurred", "stuck_detected"],
            ("APPROVAL_REQUIRED", "SUCCESS"): ["supervisor_approved"],
        }

        for (from_state, to_state), pattern_names in transition_patterns.items():
            if from_state == current_state:
                for pattern_name in pattern_names:
                    if pattern_name in self.patterns:
                        pattern = self.patterns[pattern_name]
                        match = pattern.matches(text)
                        if match:
                            return TransitionDetection(
                                from_state=from_state,
                                to_state=to_state,
                                confidence=DetectionConfidence.MEDIUM,
                                timestamp=datetime.now(),
                                trigger_pattern=pattern_name,
                                evidence=[match.group(0)],
                                metadata={"match_details": match.groupdict() or {}}
                            )

        return None

    def analyze_log_segment(self, log_lines: List[str], current_state: str = None) -> Dict[str, Any]:
        """
        Analyze a segment of log output for state information.

        Args:
            log_lines: List of log lines to analyze
            current_state: Current known job state

        Returns:
            Analysis results dictionary
        """
        analysis = {
            "detected_states": [],
            "detected_transitions": [],
            "confidence_summary": {},
            "patterns_matched": [],
            "recommendations": []
        }

        full_text = "\n".join(log_lines)

        # Detect states
        for line in log_lines:
            detection = self.detect_state(line, current_state)
            if detection:
                analysis["detected_states"].append(detection)
                analysis["patterns_matched"].append(detection.pattern_name)

                # Update current state for context
                current_state = detection.state

        # Detect transitions
        for line in log_lines:
            transition = self.detect_transition(line, current_state or "UNKNOWN")
            if transition:
                analysis["detected_transitions"].append(transition)
                current_state = transition.to_state

        # Generate confidence summary
        confidence_counts = {}
        for detection in analysis["detected_states"]:
            conf = detection.confidence.value
            confidence_counts[conf] = confidence_counts.get(conf, 0) + 1

        analysis["confidence_summary"] = confidence_counts

        # Generate recommendations
        if analysis["detected_states"]:
            latest_detection = max(analysis["detected_states"],
                                 key=lambda d: d.timestamp)

            if latest_detection.confidence == DetectionConfidence.LOW:
                analysis["recommendations"].append("Consider manual review - low confidence detection")

            if any(d.state in ["INTERVENTION_REQUIRED", "CANCELED", "FAILED"]
                   for d in analysis["detected_states"]):
                analysis["recommendations"].append("Job may require intervention")

        return analysis


class LogistObserver:
    """
    Main observer class that coordinates log analysis and state detection.

    This class provides the primary interface for intelligent job monitoring
    and state inference in the Logist system.
    """

    def __init__(self):
        self.pattern_dict = StatePatternDictionary()
        self.observation_history: List[Dict[str, Any]] = []

    def observe_job_state(self, job_id: str, log_content: str,
                         current_state: str = None) -> Dict[str, Any]:
        """
        Observe and analyze the current state of a job based on logs.

        Args:
            job_id: Job identifier
            log_content: Log content to analyze
            current_state: Currently known job state

        Returns:
            Observation results
        """
        observation = {
            "job_id": job_id,
            "timestamp": datetime.now(),
            "current_state": current_state,
            "inferred_state": None,
            "confidence": DetectionConfidence.LOW,
            "evidence": [],
            "recommendations": [],
            "analysis_details": {}
        }

        # Split log content into lines for analysis
        log_lines = log_content.strip().split('\n') if log_content else []

        # Analyze the log segment
        analysis = self.pattern_dict.analyze_log_segment(log_lines, current_state)
        observation["analysis_details"] = analysis

        # Determine inferred state
        if analysis["detected_states"]:
            # Use the most recent high-confidence detection
            high_confidence_states = [
                d for d in analysis["detected_states"]
                if d.confidence in [DetectionConfidence.HIGH, DetectionConfidence.CERTAIN]
            ]

            if high_confidence_states:
                latest_state = max(high_confidence_states, key=lambda d: d.timestamp)
                observation["inferred_state"] = latest_state.state
                observation["confidence"] = latest_state.confidence
                observation["evidence"].append(f"High confidence detection: {latest_state.pattern_name}")
            else:
                # Use latest detection even if low confidence
                latest_detection = max(analysis["detected_states"], key=lambda d: d.timestamp)
                observation["inferred_state"] = latest_detection.state
                observation["confidence"] = latest_detection.confidence
                observation["evidence"].append(f"Latest detection: {latest_detection.pattern_name}")

        # Add recommendations
        observation["recommendations"].extend(analysis.get("recommendations", []))

        # State consistency check
        if current_state and observation["inferred_state"]:
            if observation["inferred_state"] != current_state:
                observation["recommendations"].append(
                    f"State mismatch: current={current_state}, inferred={observation['inferred_state']}"
                )

        # Store observation in history
        self.observation_history.append(observation)

        return observation

    def get_state_recommendation(self, job_id: str, observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a state transition recommendation based on recent observations.

        Args:
            job_id: Job identifier
            observations: List of recent observations

        Returns:
            Recommendation dictionary
        """
        recommendation = {
            "job_id": job_id,
            "recommended_state": None,
            "confidence": DetectionConfidence.LOW,
            "reasoning": [],
            "urgency": "low"
        }

        if not observations:
            return recommendation

        # Analyze recent observations for patterns
        recent_states = [obs.get("inferred_state") for obs in observations[-5:] if obs.get("inferred_state")]
        recent_confidences = [obs.get("confidence") for obs in observations[-5:] if obs.get("confidence")]

        if not recent_states:
            return recommendation

        # Determine most consistent state
        from collections import Counter
        state_counts = Counter(recent_states)
        most_common_state = state_counts.most_common(1)[0][0]

        # Calculate average confidence
        confidence_values = [c.value for c in recent_confidences]
        avg_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0

        recommendation["recommended_state"] = most_common_state

        if avg_confidence >= DetectionConfidence.HIGH.value:
            recommendation["confidence"] = DetectionConfidence.HIGH
            recommendation["reasoning"].append(f"Consistent high-confidence detections of {most_common_state}")
        elif avg_confidence >= DetectionConfidence.MEDIUM.value:
            recommendation["confidence"] = DetectionConfidence.MEDIUM
            recommendation["reasoning"].append(f"Moderate confidence detections of {most_common_state}")
        else:
            recommendation["confidence"] = DetectionConfidence.LOW
            recommendation["reasoning"].append(f"Low confidence detections, but {most_common_state} most common")

        # Determine urgency
        error_states = {"INTERVENTION_REQUIRED", "CANCELED", "FAILED"}
        if most_common_state in error_states:
            recommendation["urgency"] = "high"
            recommendation["reasoning"].append("Error state detected - immediate attention recommended")

        return recommendation

    def add_custom_pattern(self, name: str, pattern: str, associated_states: List[str] = None,
                          description: str = ""):
        """
        Add a custom regex pattern for domain-specific state detection.

        Args:
            name: Pattern name
            pattern: Regex pattern
            associated_states: States this pattern can detect
            description: Pattern description
        """
        self.pattern_dict.add_custom_pattern(name, pattern, associated_states, description)

    def get_observation_history(self, job_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get observation history, optionally filtered by job ID.

        Args:
            job_id: Optional job ID filter
            limit: Maximum number of observations to return

        Returns:
            List of observation records
        """
        if job_id:
            filtered = [obs for obs in self.observation_history if obs.get("job_id") == job_id]
        else:
            filtered = self.observation_history

        return filtered[-limit:] if limit else filtered

    def detect_state(self, log_content: str) -> Optional[StateDetection]:
        """
        Detect state from log content (compatibility method for tests).

        Args:
            log_content: Log content to analyze

        Returns:
            StateDetection if detected, None otherwise
        """
        return self.pattern_dict.detect_state(log_content)

    def analyze_log_segment(self, log_lines: List[str]) -> Dict[str, Any]:
        """
        Analyze log segment (compatibility method for tests).

        Args:
            log_lines: List of log lines to analyze

        Returns:
            Analysis results
        """
        return self.pattern_dict.analyze_log_segment(log_lines)