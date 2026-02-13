"""
Intelligent extraction with text-first approach and conditional image fallback.
Optimized for quota efficiency (target: 6-8 API calls total).
"""
from google import genai
from typing import List, Dict, Any
import json
import fitz
from schemas import InspectionFinding, ThermalFinding
from rate_limiter import GeminiRateLimiter
from validation import validate_inspection_completeness, validate_thermal_completeness
from image_batcher import create_image_batches


# Ultra-Explicit Extraction Prompt (Prevents Area Explosion)
INSPECTION_TEXT_PROMPT = """
You are a structured inspection report parser.

CRITICAL: The PDF has TWO different sections:
1. "Impacted Areas/Rooms" - A LIST of room names (Hall, Bedroom, Kitchen...) - IGNORE THIS
2. "Impacted Area X" (with numbers: 1, 2, 3...) - The ACTUAL area sections - USE ONLY THESE

🔒 STRICT RULES:

1. **ONLY create areas from numbered sections:**
   - Pattern: "Impacted Area 1", "Impacted Area 2", "Impacted Area 3", etc.
   - These are the ONLY valid areas
   - Count: Usually 5-10 total areas

2. **IGNORE these (they are NOT areas):**
   - "Impacted Areas/Rooms" header
   - Room lists like "Hall, Bedroom, Kitchen, Master Bedroom"
   - Photo references (Photo 1, Photo 2...)
   - Serial numbers
   - Device info
   - Page numbers

3. **For each numbered "Impacted Area X":**
   - Find "Negative side Description" → extract all text → negative_observations[]
   - Find "Positive side Description" → extract all text → positive_observations[]
   - area_name = "Impacted Area X" or extract the actual room name if mentioned

4. **DO NOT:**
   - Split observations into separate areas
   - Create areas from photo numbers
   - Create areas from the room list header
   - Infer severity
   - Infer root cause
   - Create more than 15 areas (if you have >15, you're doing it wrong)

5. **Example Structure:**
   ```
   Impacted Area 1
   Negative side Description: Hall Skirting level Dampness
   Positive side Description: Common Bathroom tile hollowness
   
   → ONE area with:
      area_name: "Impacted Area 1 - Hall"
      negative_observations: ["Hall Skirting level Dampness"]
      positive_observations: ["Common Bathroom tile hollowness"]
   ```

Return STRICT JSON:
{{
  "areas": [
    {{
      "area_name": "Impacted Area X - [room name if mentioned]",
      "negative_observations": ["observation 1", "observation 2"],
      "positive_observations": ["observation 1", "observation 2"]
    }}
  ]
}}

🔍 VALIDATION:
- If you have more than 15 areas, you are treating non-areas as areas
- Final count should be 5-10 areas typically

Input:
{text}

Return ONLY the JSON, nothing else.
"""

THERMAL_TEXT_PROMPT = """
You are a structured data extractor.

The input text is extracted from a thermal inspection report.

Each page typically contains:
- Hotspot temperature
- Coldspot temperature
- Thermal image filename
- Date
- Emissivity
- Reflected temperature

Your task:
Extract structured thermal readings.

Rules:
1. Do NOT create area names
2. Do NOT infer leakage or dampness
3. Calculate temperature difference = hotspot - coldspot
4. If difference > 4°C → interpretation = "Significant temperature variation"
5. Else → interpretation = "Normal range"
6. If data missing → return "Not Available"
7. Ignore serial numbers and device model lines

Return STRICT JSON:
{{
  "thermal_readings": [
    {{
      "image_id": "",
      "hotspot": "",
      "coldspot": "",
      "temperature_difference": "",
      "interpretation": ""
    }}
  ]
}}

Input Text:
{text}

Return ONLY the JSON, nothing else.
"""

IMAGE_INSPECTION_PROMPT = """Analyze these inspection report pages (images).

CRITICAL RULES:
1. DO NOT create new areas
2. DO NOT generate severity
3. DO NOT generate root cause
4. ONLY extract what you see

Extract findings that are clearly visible in the images:
- Room name (Hall, Bedroom, Kitchen, etc.)
- Visible defect observation

Return JSON array (no markdown, just JSON):
[
  {
    "area": "Hall",
    "observation": "Visible dampness at skirting level"
  },
  {
    "area": "Common Bathroom",
    "observation": "Water seepage above false ceiling"
  }
]

IMPORTANT:
- Use EXACT room names from images
- DO NOT add severity or cause fields
- Keep observations factual and concise
- If the room name does not clearly match an impacted room from the report, ignore it
"""

IMAGE_THERMAL_PROMPT = """
Analyze these thermal imaging report pages (images).

Extract thermal data visible in the images:
- Temperature readings (hotspot/coldspot)
- Area identifiers or image IDs
- Visual thermal patterns if described

Return JSON:
[
  {{
    "area": "string",
    "temp": "string",
    "thermal_finding": "string"
  }}
]

Extract ONLY visible information. Return ONLY valid JSON.
"""


class QuotaEfficientExtractor:
    """
    Intelligent extraction that minimizes API calls using text-first approach.
    """
    
    def __init__(self, api_key: str, rate_limiter: GeminiRateLimiter = None):
        """
        Initialize extractor.
        
        Args:
            api_key: Google AI API key
            rate_limiter: Optional rate limiter instance
        """
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.rate_limiter = rate_limiter or GeminiRateLimiter()
        self.api_call_count = 0
    
    def extract_text_from_pdf(self, pdf_file) -> str:
        """Extract all text from PDF."""
        # Reset file pointer to beginning
        pdf_file.seek(0)
        
        pdf_bytes = pdf_file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        all_text = []
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(f"--- Page {page_num + 1} ---\n{text}")
        
        doc.close()
        return "\n\n".join(all_text)
    
    def _call_gemini(self, prompt: str, images: List = None) -> str:
        """
        Make a rate-limited API call to Gemini.
        
        Args:
            prompt: Text prompt
            images: Optional list of PIL images
            
        Returns:
            Response text
        """
        # Wait if needed for rate limiting
        status = self.rate_limiter.wait_if_needed()
        self.api_call_count += 1
        
        print(f"🌐 API Call #{self.api_call_count} (Daily: {status['call_number']}/{status['daily_limit']})")
        
        # Prepare content
        if images:
            content = [prompt] + images
        else:
            content = prompt
        
        # Make the call with error handling
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=content
            )
            return response.text
        except Exception as e:
            # If timeout or server error, provide helpful context
            if '503' in str(e) or 'timeout' in str(e).lower():
                print(f"⚠️  API timeout/503 error. Consider:")
                print(f"   - Reducing batch size (currently processing {len(images) if images else 0} images)")
                print(f"   - Using fewer pages")
                print(f"   - Retrying in a few moments")
            raise
    
    def _parse_json_response(self, text: str) -> List[Dict]:
        """Parse JSON from model response, handling markdown blocks."""
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join([l for l in lines if not l.strip().startswith("```")])
            if text.startswith("json"):
                text = text[4:]
        
        return json.loads(text.strip())
    
    def extract_inspection_findings(self, pdf_file) -> Dict[str, Any]:
        """
        Extract inspection findings with text-first approach.
        
        Returns:
            {
                "findings": List[InspectionFinding],
                "source": "text" or "text+images",
                "completeness": dict,
                "api_calls_used": int
            }
        """
        calls_before = self.api_call_count
        
        # Stage 1: Text extraction
        print("📄 Stage 1: Extracting from text...")
        text = self.extract_text_from_pdf(pdf_file)
        print(f"   Extracted {len(text)} characters")
        
        
        # Python-first deterministic parsing (NO MODEL, NO API CALL)
        # Python-first deterministic parsing (NO MODEL HALLUCINATION)
        print("   Using Python regex for deterministic area detection...")
        from area_parser import parse_inspection_deterministically
        
        response_data = parse_inspection_deterministically(text)
        
        # Parse structure: {"areas": [...]}
        text_findings = []
        if "areas" in response_data:
            print(f"   🔍 Deterministic parser found {len(response_data['areas'])} areas")
            
            # DEBUG: Show first few area names
            if response_data['areas']:
                area_preview = [a.get('area_name', 'UNKNOWN') for a in response_data['areas'][:5]]
                print(f"   📝 First areas: {', '.join(area_preview)}")
            
            for area_data in response_data["areas"]:
                area_name = area_data.get("area_name") or "Not Available"
                
                # Combine negative observations
                neg_obs = area_data.get("negative_observations", [])
                if neg_obs and isinstance(neg_obs, list):
                    observation = "; ".join([str(o) for o in neg_obs if o])
                else:
                    observation = "Not Available"
                
                # Create finding
                finding = InspectionFinding(
                    area=area_name,
                    observation=observation or "Not Available",
                    severity_indicator="Not Available",
                    possible_cause="Not Available"
                )
                text_findings.append(finding)
        
        
        print(f"   ✓ Extracted {len(text_findings)} findings from text")
        
        # Check completeness
        completeness = validate_inspection_completeness(text_findings)
        print(f"   📊 Completeness: {completeness['reason']}")
        
        # Stage 2: Image analysis (TEMPORARILY DISABLED for stability)
        if False:  # Disabled: completeness['needs_image_analysis']
            print("🖼️  Stage 2: Text insufficient, analyzing images...")
            image_findings = self._extract_from_images(pdf_file, "inspection")
            
            # Merge findings
            all_findings = self._merge_text_and_image_findings(
                text_findings, image_findings
            )
            source = "text+images"
        else:
            if completeness['needs_image_analysis']:
                print("⚠️  Image analysis skipped (temporarily disabled for stability)")
            else:
                print("✓ Text extraction sufficient, skipping images")
            all_findings = text_findings
            source = "text"
        
        return {
            "findings": all_findings,
            "source": source,
            "completeness": completeness,
            "api_calls_used": self.api_call_count - calls_before
        }
    
    def extract_thermal_findings(self, pdf_file) -> Dict[str, Any]:
        """
        Extract thermal findings with text-first approach.
        
        Returns:
            {
                "findings": List[ThermalFinding],
                "source": "text" or "text+images",
                "completeness": dict,
                "api_calls_used": int
            }
        """
        calls_before = self.api_call_count
        
        # Stage 1: Text extraction
        print("📄 Stage 1: Extracting thermal data from text...")
        text = self.extract_text_from_pdf(pdf_file)
        print(f"   Extracted {len(text)} characters")
        
        prompt = THERMAL_TEXT_PROMPT.format(text=text[:100000])
        response = self._call_gemini(prompt)
        
        response_data = self._parse_json_response(response)
        
        # Parse new structure: {"thermal_readings": [...]}
        text_findings = []
        if "thermal_readings" in response_data:
            for reading in response_data["thermal_readings"]:
                image_id = reading.get("image_id") or "Not Available"
                hotspot = reading.get("hotspot") or "Not Available"
                coldspot = reading.get("coldspot") or "Not Available"
                temp_diff = reading.get("temperature_difference") or "Not Available"
                interpretation = reading.get("interpretation") or "Not Available"
                
                # Format temperature reading
                temp_reading = f"Hot: {hotspot}, Cold: {coldspot}, Diff: {temp_diff}"
                
                # Create finding
                finding = ThermalFinding(
                    image_id=image_id,
                    temperature_reading=temp_reading,
                    thermal_interpretation=interpretation
                )
                text_findings.append(finding)
        
        
        print(f"   ✓ Extracted {len(text_findings)} thermal readings from text")
        
        # Check completeness
        completeness = validate_thermal_completeness(text_findings)
        print(f"   📊 Completeness: {completeness['reason']}")
        
        # Stage 2: Image analysis (TEMPORARILY DISABLED for stability)
        if False:  # Disabled: completeness['needs_image_analysis']
            print("🖼️  Stage 2: Text insufficient, analyzing thermal images...")
            image_findings = self._extract_from_images(pdf_file, "thermal")
            
            # Merge findings
            all_findings = self._merge_thermal_findings(
                text_findings, image_findings
            )
            source = "text+images"
        else:
            if completeness['needs_image_analysis']:
                print("⚠️  Thermal image analysis skipped (temporarily disabled for stability)")
            else:
                print("✓ Text extraction sufficient, skipping images")
            all_findings = text_findings
            source = "text"
        
        return {
            "findings": all_findings,
            "source": source,
            "completeness": completeness,
            "api_calls_used": self.api_call_count - calls_before
        }
    
    def _extract_from_images(self, pdf_file, report_type: str) -> List:
        """Extract from images in batches."""
        batches = create_image_batches(pdf_file, images_per_batch=5, max_total_pages=15)
        print(f"   Created {len(batches)} image batches")
        
        all_findings = []
        prompt_template = IMAGE_INSPECTION_PROMPT if report_type == "inspection" else IMAGE_THERMAL_PROMPT
        
        for i, batch in enumerate(batches, 1):
            print(f"   Processing batch {i}/{len(batches)} (pages {batch['page_range']})...")
            response = self._call_gemini(prompt_template, images=batch['images'])
            findings_data = self._parse_json_response(response)
            all_findings.extend(findings_data)
        
        print(f"   ✓ Extracted {len(all_findings)} findings from images")
        return all_findings
    
    def _merge_text_and_image_findings(
        self, 
        text_findings: List[InspectionFinding],
        image_findings_data: List[Dict]
    ) -> List[InspectionFinding]:
        """
        CRITICAL: Image findings can ONLY ENHANCE existing areas.
        They CANNOT create new areas.
        
        Uses NORMALIZED area names for case-insensitive matching.
        """
        print(f"   🔗 Merging: {len(text_findings)} text areas + {len(image_findings_data)} image observations")
        
        # No text findings = nothing to merge into
        if not text_findings:
            print(f"   ⚠️  No text findings. Cannot merge image data.")
            return []
        
        # No image findings = just return text
        if not image_findings_data:
            return text_findings
        
        # Import normalization function
        from area_parser import normalize_area
        
        # Create lookup by NORMALIZED area name for case-insensitive matching
        findings_map = {}
        for f in text_findings:
            normalized_key = normalize_area(f.area)
            findings_map[normalized_key] = f
        
        ignored_count = 0
        enhanced_count = 0
        
        # For each image observation, try to enhance existing area
        for item in image_findings_data:
            area = item.get("area", "").strip()
            observation = item.get("observation", "").strip()
            
            if not area or not observation:
                continue
            
            # Normalize for case-insensitive matching
            area_key = normalize_area(area)
            
            # Try exact match (after normalization)
            if area_key in findings_map:
                # Append to existing observations
                existing_obs = findings_map[area_key].observation
                if existing_obs and existing_obs != "Not Available":
                    findings_map[area_key].observation = f"{existing_obs}; {observation}"
                else:
                    findings_map[area_key].observation = observation
                enhanced_count += 1
            else:
                # No match - ignore this image observation
                ignored_count += 1
                if ignored_count <= 5:
                    print(f"      ⚠️  Ignoring image observation for '{area}' (not in text areas)")
        
        print(f"   ✓ Enhanced {enhanced_count} areas, ignored {ignored_count} unmatched observations")
        
        # Final findings = only text findings (possibly enhanced)
        final_findings = list(findings_map.values())
        
        # HARD LOCK: Area count MUST NOT change
        assert len(final_findings) == len(text_findings), (
            f"CRITICAL: Area count changed during merge! "
            f"Text had {len(text_findings)} areas, but final has {len(final_findings)}. "
            f"This should NEVER happen."
        )
        
        return final_findings
    
    def _merge_thermal_findings(
        self,
        text_findings: List[ThermalFinding],
        image_findings_data: List[Dict]
    ) -> List[ThermalFinding]:
        """
        Merge text and image thermal findings.
        
        NOTE: For thermal data, we CAN add new readings from images since thermal 
        readings are separate from areas. But we still track the merge.
        """
        print(f"   🔗 Merging thermal: {len(text_findings)} text + {len(image_findings_data)} image")
        
        image_findings = [
            ThermalFinding(
                image_id=item.get("area") or "Not Available",
                temperature_reading=item.get("temp") or "Not Available",
                thermal_interpretation=item.get("thermal_finding") or "Not Available"
            )
            for item in image_findings_data
        ]
        
        final_findings = text_findings + image_findings
        print(f"   ✓ Total thermal readings: {len(final_findings)}")
        
        return final_findings
