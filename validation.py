"""
Validation logic to determine if extraction results are complete.
"""
from typing import List, Dict, Any
from schemas import InspectionFinding, ThermalFinding


def validate_inspection_completeness(findings: List[InspectionFinding]) -> Dict[str, Any]:
    """
    Analyze inspection extraction results to determine quality.
    
    Args:
        findings: List of inspection findings from text extraction
        
    Returns:
        Dictionary with completeness metrics and decision
    """
    if not findings:
        return {
            "is_complete": False,
            "missing_percentage": 100.0,
            "low_confidence_count": 0,
            "total_findings": 0,
            "needs_image_analysis": True,
            "reason": "No findings extracted from text"
        }
    
    total_findings = len(findings)
    total_fields = total_findings * 4  # area, observation, severity, cause
    missing_count = 0
    
    for finding in findings:
        # Count "Not Available" fields
        if finding.area == "Not Available":
            missing_count += 1
        if finding.observation == "Not Available":
            missing_count += 1
        if finding.severity_indicator == "Not Available":
            missing_count += 1
        if finding.possible_cause == "Not Available":
            missing_count += 1
    
    missing_pct = (missing_count / total_fields) * 100 if total_fields > 0 else 100
    
    # Decision logic - ALWAYS use images for maximum data coverage
    needs_images = True  # Always extract from images
    
    return {
        "is_complete": not needs_images,
        "missing_percentage": round(missing_pct, 1),
        "total_findings": total_findings,
        "missing_fields": missing_count,
        "needs_image_analysis": needs_images,
        "reason": f"{missing_pct:.1f}% fields missing, {total_findings} findings extracted"
    }


def validate_thermal_completeness(findings: List[ThermalFinding]) -> Dict[str, Any]:
    """
    Analyze thermal extraction results to determine quality.
    
    Args:
        findings: List of thermal findings from text extraction
        
    Returns:
        Dictionary with completeness metrics and decision
    """
    if not findings:
        return {
            "is_complete": False,
            "missing_percentage": 100.0,
            "total_findings": 0,
            "needs_image_analysis": True,
            "reason": "No thermal findings extracted from text"
        }
    
    total_findings = len(findings)
    total_fields = total_findings * 3  # image_id, temp, interpretation
    missing_count = 0
    
    for finding in findings:
        # Count "Not Available" fields
        if finding.image_id == "Not Available":
            missing_count += 1
        if finding.temperature_reading == "Not Available":
            missing_count += 1
        if finding.thermal_interpretation == "Not Available":
            missing_count += 1
    
    missing_pct = (missing_count / total_fields) * 100 if total_fields > 0 else 100
    
    # Decision logic - ALWAYS use images for maximum data coverage
    needs_images = True  # Always extract from images
    
    return {
        "is_complete": not needs_images,
        "missing_percentage": round(missing_pct, 1),
        "total_findings": total_findings,
        "missing_fields": missing_count,
        "needs_image_analysis": needs_images,
        "reason": f"{missing_pct:.1f}% fields missing, {total_findings} thermal readings extracted"
    }


def normalize_area(area: str) -> str:
    """
    Normalize area names for consistent matching.
    
    Args:
        area: Raw area name
        
    Returns:
        Normalized area name
    """
    return area.lower().strip().replace("_", " ").replace("-", " ")
