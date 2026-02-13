"""
Controlled Root Cause Extraction (NOT AI Inference).

This module extracts root causes from observations using keyword matching.
It does NOT make structural engineering assumptions.
"""
import re


def extract_root_cause_from_observation(observation: str, provided_cause: str = "Not Available") -> str:
    """
    Extract root cause using controlled inference.
    
    Mode: Controlled Inference
    - If observation contains cause-like keywords, extract that phrase
    - Do NOT make structural assumptions
    - Do NOT infer from damage type alone
    
    Args:
        observation: The observation text
        provided_cause: Cause from extraction (usually "Not Available")
        
    Returns:
        Root cause or "Requires further investigation"
    """
    # If cause was provided, use it
    if provided_cause and provided_cause != "Not Available":
        return provided_cause
    
    # Check for cause-like keywords in observation
    cause_patterns = [
        r"due to (.+?)(?:\.|$|,)",
        r"caused by (.+?)(?:\.|$|,)",
        r"because of (.+?)(?:\.|$|,)",
        r"from (.+?)(?:\.|$|,)",
        r"resulting from (.+?)(?:\.|$|,)",
        r"attributed to (.+?)(?:\.|$|,)"
    ]
    
    for pattern in cause_patterns:
        match = re.search(pattern, observation, re.IGNORECASE)
        if match:
            cause = match.group(1).strip()
            # Clean up the extracted cause
            cause = cause.rstrip('.,;')
            return cause.capitalize()
    
    # No cause found in observation
    return "Requires further investigation"


def batch_extract_causes(observations: list) -> list:
    """
    Extract causes for multiple observations.
    
    Args:
        observations: List of observation strings
        
    Returns:
        List of extracted causes
    """
    return [extract_root_cause_from_observation(obs) for obs in observations]


# Example usage and tests
if __name__ == "__main__":
    test_cases = [
        ("Dampness observed on wall due to water seepage.", "Not Available"),
        ("Crack in ceiling caused by structural settlement.", "Not Available"),
        ("Paint peeling.", "Not Available"),
        ("Staining from roof leakage.", "Not Available"),
        ("Minor crack.", "Not Available"),
    ]
    
    print("Root Cause Extraction Tests:\n")
    for obs, provided in test_cases:
        result = extract_root_cause_from_observation(obs, provided)
        print(f"Observation: {obs}")
        print(f"Extracted Cause: {result}")
        print()
