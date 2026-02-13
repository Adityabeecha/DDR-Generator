"""
Python-first area detection.
Uses regex to find exact "Impacted Area X" patterns before model extraction.
This ensures deterministic control over area count.
"""
import re
from typing import List, Dict


def extract_impacted_areas_from_text(text: str, max_areas: int = 20) -> List[Dict[str, str]]:
    """
    Use Python regex to find numbered "Impacted Area X" sections.
    This gives us deterministic control over area count.
    
    Args:
        text: Input text to parse
        max_areas: Maximum number of areas to extract (default 20)
    
    Returns:
        List of dicts with {
            "area_number": "1",
            "area_name": "Impacted Area 1",
            "text_chunk": "...text between this and next area..."
        }
    """
    # Pattern: "Impacted Area" followed by number
    pattern = r'Impacted Area\s+(\d+)'
    
    # Find all matches with their positions
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    
    if not matches:
        return []
    
    # Deduplicate by area number to prevent duplicates if "Impacted Area 1" appears multiple times
    unique_areas = {}
    
    for match in matches:
        area_num = match.group(1)
        
        # Skip if we already found this area number (take first occurrence)
        if area_num in unique_areas:
            continue
        
        unique_areas[area_num] = {
            "area_number": area_num,
            "match_position": match.start()
        }
    
    # Sort by area number (as integers)
    sorted_area_nums = sorted(unique_areas.keys(), key=lambda x: int(x))
    
    # CRITICAL: Enforce maximum area count
    if len(sorted_area_nums) > max_areas:
        area_list = ', '.join(sorted_area_nums[:30])
        if len(sorted_area_nums) > 30:
            area_list += f'... (total: {len(sorted_area_nums)})'
        
        raise ValueError(
            f"Extraction found {len(sorted_area_nums)} unique areas, exceeding maximum {max_areas}. "
            f"This indicates either: (1) PDF has duplicate content/OCR artifacts, or "
            f"(2) PDF genuinely has too many areas. "
            f"Area numbers found: {area_list}. "
            f"Review PDF structure before proceeding."
        )
    
    # Build areas list with text chunks
    areas = []
    for i, area_num in enumerate(sorted_area_nums):
        start_pos = unique_areas[area_num]["match_position"]
        
        # End position is either next area or end of text
        if i + 1 < len(sorted_area_nums):
            next_area_num = sorted_area_nums[i + 1]
            end_pos = unique_areas[next_area_num]["match_position"]
        else:
            end_pos = len(text)
        
        # Extract text chunk for this area
        text_chunk = text[start_pos:end_pos]
        
        areas.append({
            "area_number": area_num,
            "area_name": f"Impacted Area {area_num}",
            "text_chunk": text_chunk
        })
    
    return areas


def extract_descriptions_from_area_chunk(area_chunk: str) -> Dict[str, any]:
    """
    Extract negative and positive descriptions from an area text chunk.
    
    CRITICAL CHANGE: Also extract the ROOM NAME from the first observation.
    The room name (e.g., "Hall", "Common Bathroom") becomes the area identifier.
    
    Returns:
        {
            "area_name": "Hall" (extracted room name),
            "negative_observations": [...],
            "positive_observations": [...]
        }
    """
    negative_obs = []
    positive_obs = []
    area_name = None
    
    # Find "Negative side Description" section
    neg_pattern = r'Negative side Description\s*(.+?)(?=Negative side photographs|Positive side|Impacted Area|$)'
    neg_match = re.search(neg_pattern, area_chunk, re.IGNORECASE | re.DOTALL)
    if neg_match:
        neg_text = neg_match.group(1).strip()
        # Clean up (remove photo references)
        neg_text = re.sub(r'Photo\s+\d+', '', neg_text, flags=re.IGNORECASE)
        neg_text = neg_text.strip()
        
        if neg_text and len(neg_text) > 3:
            negative_obs.append(neg_text)
            
            # EXTRACT ROOM NAME from first observation
            # Format: "Hall Skirting level Dampness" → extract "Hall"
            # Common room patterns
            room_patterns = [
                r'^(Hall)\b',
                r'^(Bedroom)\b',
                r'^(Master Bedroom)\b',
                r'^(Common Bedroom)\b',
                r'^(Kitchen)\b',
                r'^(Bathroom)\b',
                r'^(Common Bathroom)\b',
                r'^(MB Bathroom)\b',
                r'^(Living Room)\b',
                r'^(Dining Room)\b',
                r'^(Balcony)\b',
                r'^(Parking)\b',
                r'^(Entrance)\b',
                r'(Flat No\.\s*\d+)',
            ]
            
            for pattern in room_patterns:
                match = re.search(pattern, neg_text, re.IGNORECASE)
                if match:
                    area_name = match.group(1)
                    break
    
    # Find "Positive side Description" section
    pos_pattern = r'Positive side Description\s*(.+?)(?=Positive side photographs|Impacted Area|$)'
    pos_match = re.search(pos_pattern, area_chunk, re.IGNORECASE | re.DOTALL)
    if pos_match:
        pos_text = pos_match.group(1).strip()
        # Clean up
        pos_text = re.sub(r'Photo\s+\d+', '', pos_text, flags=re.IGNORECASE)
        pos_text = pos_text.strip()
        if pos_text and len(pos_text) > 3:
            positive_obs.append(pos_text)
            
            # Try to extract room name from positive if not found in negative
            if not area_name:
                for pattern in room_patterns:
                    match = re.search(pattern, pos_text, re.IGNORECASE)
                    if match:
                        area_name = match.group(1)
                        break
    
    return {
        "area_name": area_name,
        "negative_observations": negative_obs,
        "positive_observations": positive_obs
    }


def normalize_area(name: str) -> str:
    """
    Normalize area name for consistent matching.
    Handles case differences and whitespace.
    """
    if not name:
        return ""
    return name.strip().lower()


def parse_inspection_deterministically(text: str) -> Dict:
    """
    Deterministically parse inspection report using Python regex.
    NO model hallucination possible.
    
    CRITICAL CHANGE: Now extracts ROOM NAMES as area identifiers,
    not "Impacted Area X" section labels.
    
    Returns:
        {
            "areas": [
                {
                    "area_name": "Hall",  # <-- ROOM NAME, not "Impacted Area 1"
                    "negative_observations": [...],
                    "positive_observations": [...]
                }
            ]
        }
    """
    # Step 1: Find all numbered area sections
    areas = extract_impacted_areas_from_text(text)
    
    print(f"🔍 Python regex found {len(areas)} numbered 'Impacted Area X' sections")
    
    # Step 2: Extract room names and descriptions from each area
    parsed_areas = []
    unnamed_count = 0
    seen_rooms = {}  # Deduplicate by normalized room name
    
    for area in areas:
        descriptions = extract_descriptions_from_area_chunk(area["text_chunk"])
        
        # Use extracted room name as area identifier
        room_name = descriptions.get("area_name")
        
        if room_name:
            area_name = room_name
        else:
            # Fallback: use numbered format if no room name found
            area_name = area["area_name"]
            unnamed_count += 1
            print(f"   ⚠️  Could not extract room name from {area['area_name']}, using numbered format")
        
        # Deduplicate by normalized room name
        normalized_key = normalize_area(area_name)
        
        if normalized_key in seen_rooms:
            # Duplicate room name - merge observations
            print(f"   ⚠️  Duplicate room '{area_name}' detected, merging observations")
            existing = seen_rooms[normalized_key]
            existing["negative_observations"].extend(descriptions["negative_observations"])
            existing["positive_observations"].extend(descriptions["positive_observations"])
        else:
            # New room
            room_data = {
                "area_name": area_name,
                "negative_observations": descriptions["negative_observations"],
                "positive_observations": descriptions["positive_observations"]
            }
            seen_rooms[normalized_key] = room_data
            parsed_areas.append(room_data)
    
    if unnamed_count > 0:
        print(f"   ⚠️  {unnamed_count} areas without extracted room names")
    
    print(f"   ✓ Extracted {len(parsed_areas)} unique areas: {[a['area_name'] for a in parsed_areas[:5]]}")
    
    return {
        "areas": parsed_areas
    }


# Test the parser
if __name__ == "__main__":
    sample_text = """
    Impacted Areas/Rooms
    Hall, Bedroom, Kitchen, Master Bedroom
    
    Impacted Area 1
    Negative side Description
    Hall Skirting level Dampness
    Negative side photographs
    Photo 1 Photo 2 Photo 3
    
    Positive side Description
    Common Bathroom tile hollowness
    
    Impacted Area 2
    Negative side Description
    Bedroom Skirting level Dampness
    """
    
    result = parse_inspection_deterministically(sample_text)
    print("\nResult:")
    import json
    print(json.dumps(result, indent=2))
    print(f"\nArea count: {len(result['areas'])}")
