# 🏗 DDR Generation System

A deterministic, hallucination-controlled Diagnostic Data Report (DDR)
generation system that processes:

-   Inspection Report PDF\
-   Thermal Imaging Report PDF

The system extracts structured findings and generates a professional
diagnostic report while preventing hallucinations, entity inflation, and
fabricated fields.

------------------------------------------------------------------------

## 📌 Overview

This project implements a structured pipeline to generate detailed
diagnostic reports from inspection and thermal imaging documents.

The system was specifically designed to address common LLM failure modes
such as:

-   Area inflation\
-   Fabricated severity levels\
-   Fabricated root causes\
-   Thermal data merging into inspection findings\
-   Duplicate entries\
-   Structural inconsistency

The final output is deterministic, validated, and structurally locked.

------------------------------------------------------------------------

## 🧠 System Architecture

The system follows a controlled three-phase pipeline.

### 🔹 Phase 1: Deterministic Extraction

#### Inspection Report

-   Python regex-based extraction of impacted areas\
-   Canonical room-name detection\
-   Room normalization (case-insensitive)\
-   Deduplication of repeated rooms\
-   No inference allowed

#### Thermal Report

-   Extraction of:
    -   Image ID\
    -   Hotspot temperature\
    -   Coldspot temperature\
    -   Temperature difference\
-   One entry per image ID\
-   Strict separation from inspection data

------------------------------------------------------------------------

### 🔹 Phase 2: Validation and Structural Lock

This phase prevents hallucination and structural drift.

#### Entity Lock

Ensures the number of rendered areas exactly matches extracted areas.

``` python
assert extracted_area_count == expected_area_count
```

Prevents: - New area creation\
- Area inflation\
- Merge growth errors

#### Thermal Deduplication

Ensures only one entry per thermal image ID.

#### Normalization Layer

-   Case-insensitive matching\
-   Merge-only enhancement logic\
-   No new entity creation during merge

------------------------------------------------------------------------

### 🔹 Phase 3: Controlled DDR Generation

The report is generated strictly from structured JSON input.

Enforced rules:

-   No severity generation\
-   No root cause inference\
-   No new area creation\
-   No mixing of thermal and inspection data\
-   No expansion beyond extracted data

Root cause is fixed to:

    Not Available

------------------------------------------------------------------------

## 📊 Output Structure

### 1. Executive Summary

-   Total Impacted Rooms\
-   Critical Findings\
-   Thermal Analysis Summary

### 2. Area-wise Inspection Findings

For each impacted room: - Observations\
- Probable Root Cause (Not Available)\
- Reference to consolidated recommendations

### 3. Thermal Imaging Analysis

For each thermal image: - Image ID\
- Hotspot temperature\
- Coldspot temperature\
- Temperature difference\
- Assessment

### 4. Recommendations

Exactly one consolidated recommendation per impacted room.

### 5. Summary Statistics

-   Total Impacted Rooms\
-   Total Thermal Readings\
-   Recommendations Provided

------------------------------------------------------------------------

## 🛡 Anti-Hallucination Safeguards

The system prevents common LLM failure modes:

-   Entity Lock prevents area inflation\
-   Merge-only logic prevents new room creation\
-   Thermal separation prevents ID contamination\
-   Severity removed entirely\
-   Root cause fixed to "Not Available"\
-   Deduplication prevents duplicate entries\
-   Structural validation replaces brittle text-based assertions

------------------------------------------------------------------------

## 🚀 How to Run

``` bash
streamlit run app_v3_anti_hallucination.py
```

Upload: - Inspection Report PDF\
- Thermal Report PDF

The system will:

1.  Extract structured findings\
2.  Validate entity counts\
3.  Deduplicate thermal readings\
4.  Generate the final DDR

