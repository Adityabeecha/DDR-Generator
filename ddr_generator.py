"""
Phase 3: Controlled DDR Generation
Generates final report from validated JSON with strict entity control.
NO new areas, NO hallucination, NO generic recommendations.
"""
from typing import Dict, List, Any
from schemas import InspectionFinding, ThermalFinding
from root_cause_extractor import extract_root_cause_from_observation


# Production-Grade DDR Generation Prompt
DDR_GENERATION_PROMPT = """
You are a report formatter (NOT an analyzer).

You will receive VALIDATED structured JSON data:
- Inspection areas with observations
- Thermal readings (separate from areas)

Your ONLY job:
Format this data into a professional DDR report.

🔒 CRITICAL RULES (MEASURABLE):

1. **ENTITY LOCK RULE** (MEASURABLE):
   - Count of areas in final DDR = Count of areas in JSON input
   - This is: {area_count} areas
   - You are LOCKED to this number
   - Do NOT create, add, expand, or derive new areas
   - Area explosion is a FAILURE condition

2. **THERMAL SEPARATION** (STRICT):
   - Thermal readings go in SEPARATE "Thermal Analysis" section
   - Do NOT merge thermal IDs into area list
   - Do NOT treat image IDs as areas

3. **ROOT CAUSE HANDLING** (CONTROLLED):
   - Use the provided root_cause from JSON
   - If "Requires further investigation" → output exactly that
   - Do NOT add your own causes

4. **RECOMMENDATION CONSTRAINT** (EXPLICIT LINKING):
   - Each recommendation must reference the EXACT observation text
   - Format: "For [observation text] → Recommended action: [specific action]"
   - Do NOT generate generic maintenance advice
   - Zero generic recommendations allowed



Report Structure:

# Detailed Diagnostic Report

## 1. Executive Summary

**Total Impacted Rooms:** {area_count}

**Critical Findings:**

Format as bullet points for clarity. Avoid repeating the room name in the description:
• [Area name] – [Brief description of issue]

Example:
• Hall – Skirting level dampness (NOT "Hall – Hall Skirting level dampness")
• Master Bedroom – Wall and skirting dampness

**Thermal Analysis Summary:**
- Total thermal images analyzed: {thermal_count}
- Temperature anomalies identified and documented for further investigation

---

## 2. Area-wise Inspection Findings

**Area 1: {{area_name}}**

**Observations:**
{{negative_observations}}

**Probable Root Cause:** Not Available

**Recommendation:** {{recommendation}}

---

## 3. Thermal Imaging Analysis

### Thermal Readings (SEPARATE - NOT IN AREAS)

**Image ID:** {{image_id}}
- Hotspot Temperature: {{hotspot}}
- Coldspot Temperature: {{coldspot}}
- Temperature Difference: {{temperature_difference}}
- Assessment: {{interpretation}}

---

## 4. Recommendations

Provide ONE comprehensive recommendation per area addressing all observed issues.

**IMPORTANT:** Write recommendations in natural, professional language. Do NOT use "For [observation] → Recommended action:" format.

**{{area_name}}**

**Recommended Action:**  
Write clear, actionable steps to address the issues. Avoid repeating the area name or observations verbatim.

Example: "Investigate the source of dampness affecting the skirting and implement appropriate waterproofing and drying measures."

---

## 5. Summary Statistics

- Total Impacted Rooms: {area_count}
- Total Thermal Readings: {thermal_count}
- Recommendations Provided: {area_count}

---

🔍 **VALIDATION CHECK BEFORE OUTPUT:**
- Count areas in your output
- Must equal {area_count}
- If not equal → YOU HAVE FAILED → STOP

**Input JSON:**
```json
{json_data}
```

Generate the DDR report now.
"""


class ControlledDDRGenerator:
    """
    Phase 3: Controlled DDR Generation with Entity Lock.
    """
    
    def __init__(self, api_key: str):
        """Initialize generator with Gemini client."""
        from google import genai
        self.client = genai.Client(api_key=api_key)
    
    def generate_ddr(
        self,
        inspection_findings: List[InspectionFinding],
        thermal_findings: List[ThermalFinding],
        validation_results: Dict[str, Any]
    ) -> str:
        """
        Generate DDR from validated structured data.
        
        Args:
            inspection_findings: List of validated inspection findings
            thermal_findings: List of validated thermal findings
            validation_results: Results from structural validation
            
        Returns:
            DDR report text
        """
        # CHANGE 3: Deduplicate thermal readings by image_id
        print(f"\n🔧 Deduplicating thermal readings...")
        print(f"   Before: {len(thermal_findings)} thermal readings")
        
        unique_thermal = {}
        for item in thermal_findings:
            image_id = item.image_id  # Use explicit image_id field
            if image_id not in unique_thermal:
                unique_thermal[image_id] = item
            else:
                print(f"   ⚠️  Duplicate thermal reading for '{image_id}', keeping first")
        
        thermal_findings = list(unique_thermal.values())
        print(f"   After: {len(thermal_findings)} unique thermal readings")
        
        # DYNAMIC: Validate thermal count equals unique image IDs
        thermal_count = len(thermal_findings)
        unique_image_ids = len(set(t.image_id for t in thermal_findings))
        print(f"📊 Thermal readings extracted: {thermal_count}")
        
        # Assert no duplicates exist
        assert thermal_count == unique_image_ids, (
            f"CRITICAL: Thermal count {thermal_count} does not match unique image IDs {unique_image_ids}. "
            f"Duplication bug detected!"
        )
        
        # Prepare structured JSON for the model (NO root cause enrichment)
        structured_data = self._prepare_structured_json(
            inspection_findings,
            thermal_findings
        )
        
        # Calculate entity count (MEASURABLE)
        area_count = len(inspection_findings)
        
        # Inject counts into prompt (ENTITY LOCK)
        prompt = DDR_GENERATION_PROMPT.format(
            area_count=area_count,
            thermal_count=thermal_count,
            json_data=structured_data
        )
        
        print(f"\n🔒 Entity Lock Active: {area_count} areas (LOCKED)")
        print(f"📊 Thermal readings: {thermal_count}")
        
        # Generate DDR
        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        ddr_text = response.text
        
        # Debug: Print first part of DDR to see format
        print(f"\n📝 Generated DDR preview (first 500 chars):")
        print("=" * 60)
        print(ddr_text[:500])
        print("=" * 60)
        
        # Post-generation validation (MEASURABLE)
        self._validate_entity_count(ddr_text, area_count)
        
        return ddr_text
    
    def _enrich_with_root_causes(
        self,
        findings: List[InspectionFinding]
    ) -> List[InspectionFinding]:
        """
        Apply controlled root cause extraction (Python logic, not AI).
        """
        for finding in findings:
            if finding.possible_cause == "Not Available":
                # Extract from observation using keyword matching
                extracted_cause = extract_root_cause_from_observation(
                    finding.observation,
                    finding.possible_cause
                )
                finding.possible_cause = extracted_cause
        
        return findings
    
    def _prepare_structured_json(
        self,
        inspection_findings: List[InspectionFinding],
        thermal_findings: List[ThermalFinding]
    ) -> str:
        """Prepare structured JSON for the model."""
        import json
        
        data = {
            "inspection": {
                "areas": [
                    {
                        "area_name": f.area,
                        "negative_observations": [
                            # Clean newlines, whitespace, and common typos
                            f.observation.replace('\n', ' ').replace('\r', ' ')
                                        .replace('damness', 'dampness')
                                        .strip()
                        ]
                    }
                    for f in inspection_findings
                ]
            },
            "thermal": {
                "thermal_readings": [
                    {
                        "image_id": f.image_id,  # Use explicit image_id field
                        # Clean thermal readings: remove "Hot:", "Cold:", "Diff:" prefixes
                        "hotspot": self._clean_thermal_value(
                            f.temperature_reading.split(",")[0] if "," in f.temperature_reading else "N/A"
                        ),
                        "coldspot": self._clean_thermal_value(
                            f.temperature_reading.split(",")[1] if "," in f.temperature_reading else "N/A"
                        ),
                        "temperature_difference": self._clean_thermal_value(
                            f.temperature_reading.split(",")[2] if "," in f.temperature_reading and len(f.temperature_reading.split(",")) > 2 else "N/A"
                        ),
                        "interpretation": f.thermal_interpretation
                    }
                    for f in thermal_findings
                ]
            }
        }
        
        return json.dumps(data, indent=2)
    
    def _clean_thermal_value(self, value: str) -> str:
        """
        Clean thermal value by removing redundant prefixes and ensuring °C units.
        Example: 'Hot: 28.8' -> '28.8 °C'
        """
        if value == "N/A":
            return value
        
        # Remove common prefixes
        prefixes = ['Hot:', 'Cold:', 'Diff:', 'hot:', 'cold:', 'diff:']
        for prefix in prefixes:
            if prefix in value:
                value = value.replace(prefix, '').strip()
        
        # Ensure °C is present
        if '°C' not in value and value != "N/A":
            # Check if it's a number (with optional decimal)
            value = value.strip()
            if value and (value.replace('.', '').replace('-', '').isdigit() or 
                         any(char.isdigit() for char in value)):
                value = f"{value} °C"
        
        return value
    
    def _validate_entity_count(self, ddr_text: str, expected_count: int):
        """
        Validate that output DDR has correct area count.
        This is the MEASURABLE enforcement of Entity Lock.
        """
        import re
        
        # Use single standardized pattern: "Area 1:", "Area 2:", etc.
        pattern = re.findall(r'Area\s+\d+:', ddr_text, re.IGNORECASE)
        actual_count = len(pattern)
        
        # Debug output
        print(f"   🔍 Found {actual_count} area headers with pattern 'Area X:'")
        
        if actual_count != expected_count:
            raise ValueError(
                f"⚠️ ENTITY LOCK VIOLATION: "
                f"Expected {expected_count} areas, found {actual_count} in output. "
                f"Model added extra areas (hallucination detected)."
            )
        
        print(f"✅ Entity Lock Verified: {actual_count} areas = {expected_count} expected")
