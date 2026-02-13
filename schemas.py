from pydantic import BaseModel
from typing import List, Optional

class InspectionFinding(BaseModel):
    area: str
    observation: str
    severity_indicator: str
    possible_cause: str

class ThermalFinding(BaseModel):
    image_id: str  # Explicit field for image ID (e.g., "RB02380X.JPG")
    temperature_reading: str
    thermal_interpretation: str

class MergedDDR(BaseModel):
    area: str
    combined_observations: List[str]
    root_cause: str
    severity: str
    reasoning: str
    recommended_actions: str
    conflicts: Optional[str] = "None"