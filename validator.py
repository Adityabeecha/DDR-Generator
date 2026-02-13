"""
Validation layer to prevent hallucination in DDR generation.
Enforces structural integrity before final report generation.
"""
from typing import Dict, List, Any
from schemas import InspectionFinding, ThermalFinding


class ValidationError(Exception):
    """Raised when structural validation fails."""
    pass


class StructuralValidator:
    """
    Enforces strict structural rules on extracted data.
    Prevents:
    - Thermal IDs being treated as areas
    - Excessive area creation
    - Null/missing fields
    """
    
    MAX_AREAS = 20  # Reasonable limit for impacted areas
    
    def validate_all(self, inspection_data: Dict, thermal_data: Dict) -> Dict[str, Any]:
        """
        Run all validation checks.
        
        Args:
            inspection_data: {"areas": [...]}
            thermal_data: {"thermal_readings": [...]}
            
        Returns:
            Validated and cleaned data
            
        Raises:
            ValidationError: If structural rules violated
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "area_count": 0,
            "thermal_count": 0
        }
        
        try:
            # Check 1: Area count
            self._validate_area_count(inspection_data, results)
            
            # Check 2: No thermal IDs in areas
            self._validate_no_thermal_ids_in_areas(inspection_data, results)
            
            # Check 3: Thermal structure
            self._validate_thermal_structure(thermal_data, results)
            
            # Check 4: No area names in thermal
            self._validate_no_areas_in_thermal(inspection_data, thermal_data, results)
            
            # Check 5: Clean null fields
            inspection_data = self._clean_null_fields(inspection_data)
            thermal_data = self._clean_null_fields(thermal_data)
            
        except ValidationError as e:
            results["valid"] = False
            results["errors"].append(str(e))
        
        results["area_count"] = len(inspection_data.get("areas", []))
        results["thermal_count"] = len(thermal_data.get("thermal_readings", []))
        
        return {
            "validation": results,
            "inspection": inspection_data,
            "thermal": thermal_data
        }
    
    def _validate_area_count(self, inspection_data: Dict, results: Dict):
        """Check area count is reasonable."""
        areas = inspection_data.get("areas", [])
        count = len(areas)
        
        if count > self.MAX_AREAS:
            # Show which areas were found to help debug
            area_names = [a.get("area_name", "UNKNOWN") for a in areas[:30]]  # Show first 30
            area_preview = ", ".join(area_names[:10])
            if len(area_names) > 10:
                area_preview += f" ... (and {len(area_names) - 10} more)"
            
            raise ValidationError(
                f"Area count {count} exceeds maximum {self.MAX_AREAS}. "
                f"Likely hallucination from thermal IDs or metadata. "
                f"Areas found: {area_preview}"
            )
        
        if count == 0:
            results["warnings"].append("No areas extracted from inspection report")
    
    def _validate_no_thermal_ids_in_areas(self, inspection_data: Dict, results: Dict):
        """Ensure no thermal image IDs leaked into area names."""
        areas = inspection_data.get("areas", [])
        thermal_patterns = [".jpg", ".jpeg", ".png", "rb0", "rb_", "ir_", "ir0"]
        
        for area in areas:
            area_name = area.get("area_name", "").lower()
            
            # Check for image file extensions
            if any(pattern in area_name for pattern in thermal_patterns):
                raise ValidationError(
                    f"Thermal image ID detected in areas: '{area.get('area_name')}'. "
                    f"Thermal IDs must NOT be treated as areas."
                )
            
            # Check for suspicious patterns (all caps, long codes)
            if len(area_name) > 30 or (area_name.isupper() and len(area_name) > 10):
                results["warnings"].append(
                    f"Suspicious area name (might be ID): '{area.get('area_name')}'"
                )
    
    def _validate_thermal_structure(self, thermal_data: Dict, results: Dict):
        """Validate thermal readings use proper structure."""
        readings = thermal_data.get("thermal_readings", [])
        
        for i, reading in enumerate(readings):
            # Must have image_id, NOT area
            if "area" in reading and "image_id" not in reading:
                raise ValidationError(
                    f"Thermal reading {i} uses 'area' instead of 'image_id'. "
                    f"This causes thermal IDs to be treated as areas."
                )
            
            # Image ID should look like a filename
            image_id = reading.get("image_id", "")
            if not image_id or image_id == "Not Available":
                continue
            
            # Warn if image_id looks like an area name
            common_areas = ["hall", "bedroom", "kitchen", "bathroom", "living", "dining"]
            if any(area in image_id.lower() for area in common_areas):
                results["warnings"].append(
                    f"Thermal image_id looks like area name: '{image_id}'"
                )
    
    def _validate_no_areas_in_thermal(
        self, 
        inspection_data: Dict, 
        thermal_data: Dict, 
        results: Dict
    ):
        """Ensure area names don't leak into thermal image IDs."""
        areas = inspection_data.get("areas", [])
        area_names = [a.get("area_name", "").lower() for a in areas]
        
        readings = thermal_data.get("thermal_readings", [])
        for reading in readings:
            image_id = reading.get("image_id", "").lower()
            
            # Check if thermal image_id matches an area name
            if image_id in area_names:
                results["warnings"].append(
                    f"Thermal image_id '{reading.get('image_id')}' matches area name. "
                    f"Verify separation is correct."
                )
    
    def _clean_null_fields(self, data: Dict) -> Dict:
        """Replace None/null with 'Not Available'."""
        if "areas" in data:
            for area in data["areas"]:
                if not area.get("area_name"):
                    area["area_name"] = "Not Available"
                if not isinstance(area.get("negative_observations"), list):
                    area["negative_observations"] = []
                if not isinstance(area.get("positive_observations"), list):
                    area["positive_observations"] = []
        
        if "thermal_readings" in data:
            for reading in data["thermal_readings"]:
                for field in ["image_id", "hotspot", "coldspot", "temperature_difference", "interpretation"]:
                    if not reading.get(field):
                        reading[field] = "Not Available"
        
        return data


def apply_rule_based_severity(observation: str) -> str:
    """
    Apply severity based on keywords (NOT AI inference).
    
    This is deterministic Python logic, not model inference.
    """
    obs_lower = observation.lower()
    
    # High severity keywords
    high_keywords = [
        "structural", "crack", "seepage", "leakage", "collapse",
        "severe", "major", "critical", "dangerous", "unstable"
    ]
    if any(kw in obs_lower for kw in high_keywords):
        return "High"
    
    # Medium severity keywords
    medium_keywords = [
        "dampness", "stain", "minor crack", "peeling", "discoloration",
        "moderate", "wear"
    ]
    if any(kw in obs_lower for kw in medium_keywords):
        return "Medium"
    
    # Low severity (default)
    return "Low"


def enrich_findings_with_severity(findings: List[InspectionFinding]) -> List[InspectionFinding]:
    """
    Add rule-based severity to findings that have "Not Available".
    
    This runs AFTER extraction, in Python, deterministically.
    """
    for finding in findings:
        if finding.severity_indicator == "Not Available":
            finding.severity_indicator = apply_rule_based_severity(finding.observation)
    
    return findings
