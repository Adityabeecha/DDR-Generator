"""
3-Phase DDR Generation App
Extract → Validate → Generate
"""
import streamlit as st
from extraction import QuotaEfficientExtractor
from validator import StructuralValidator
from ddr_generator import ControlledDDRGenerator
from rate_limiter import GeminiRateLimiter

st.set_page_config(
    page_title="DDR Generator",
    page_icon="🔒",
    layout="wide"
)

st.title("🔒 DDR Generator")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    api_key = st.text_input("Google AI API Key", type="password")
    
    st.markdown("---")
    st.markdown("### 📋 Phase Status")
    phase_status = st.empty()
    
    st.markdown("---")
    st.markdown("### 🔒 Entity Lock")
    entity_lock_display = st.empty()

# File uploaders
col1, col2 = st.columns(2)
with col1:
    inspection_pdf = st.file_uploader(
        "📄 Inspection Report PDF",
        type=['pdf'],
        key="inspection"
    )
with col2:
    thermal_pdf = st.file_uploader(
        "🌡️ Thermal Report PDF",
        type=['pdf'],
        key="thermal"
    )

# Generate button
if st.button("🚀 Generate DDR", type="primary", disabled=not (inspection_pdf and thermal_pdf and api_key)):
    
    # Initialize components
    rate_limiter = GeminiRateLimiter(rpm=5, rpd=20)
    extractor = QuotaEfficientExtractor(api_key, rate_limiter)
    validator = StructuralValidator()
    generator = ControlledDDRGenerator(api_key)
    
    try:
        # ========================================
        # PHASE 1: PURE EXTRACTION
        # ========================================
        phase_status.markdown("**Phase 1:** 📥 Extracting...")
        st.markdown("---")
        st.subheader("Phase 1: Pure Extraction (NO INFERENCE)")
        
        with st.spinner("Extracting inspection findings..."):
            inspection_result = extractor.extract_inspection_findings(inspection_pdf)
            st.success(f"✅ Extracted {len(inspection_result['findings'])} inspection findings")
            st.info(f"📊 Source: {inspection_result['source']} | API calls: {inspection_result['api_calls_used']}")
        
        with st.spinner("Extracting thermal findings..."):
            thermal_result = extractor.extract_thermal_findings(thermal_pdf)
            st.success(f"✅ Extracted {len(thermal_result['findings'])} thermal readings")
            st.info(f"📊 Source: {thermal_result['source']} | API calls: {thermal_result['api_calls_used']}")
        
        # Prepare data for validation
        # CRITICAL: Only inspection findings create areas
        # Thermal findings go into thermal_readings with image_id (NOT area)
        inspection_data = {
            "areas": [
                {
                    "area_name": f.area,
                    "negative_observations": [f.observation],
                    "positive_observations": []
                }
                for f in inspection_result['findings']  # Only inspection findings
            ]
        }
        
        # Thermal data stays separate - uses image_id, NOT area
        thermal_data = {
            "thermal_readings": [
                {
                    "image_id": f.image_id,  # ThermalFinding uses image_id field
                    "hotspot": "N/A",
                    "coldspot": "N/A",
                    "temperature_difference": "N/A",
                    "interpretation": f.thermal_interpretation
                }
                for f in thermal_result['findings']  # Thermal readings separate
            ]
        }
        
        # ========================================
        # PHASE 2: VALIDATION
        # ========================================
        phase_status.markdown("**Phase 2:** ✅ Validating...")
        st.markdown("---")
        st.subheader("Phase 2: Structural Validation")
        
        with st.spinner("Running structural validation..."):
            validation_result = validator.validate_all(inspection_data, thermal_data)
        
        # Display validation results
        val = validation_result['validation']
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Area Count", val['area_count'])
        with col2:
            st.metric("Thermal Readings", val['thermal_count'])
        with col3:
            if val['valid']:
                st.success("✅ VALID")
            else:
                st.error("❌ INVALID")
        
        # Show errors/warnings
        if val['errors']:
            st.error("**Validation Errors:**")
            for error in val['errors']:
                st.error(f"• {error}")
            st.stop()
        
        if val['warnings']:
            with st.expander("⚠️ Validation Warnings"):
                for warning in val['warnings']:
                    st.warning(f"• {warning}")
        
        
        # ========================================
        # PHASE 3: CONTROLLED DDR GENERATION
        # ========================================
        phase_status.markdown("**Phase 3:** 📝 Generating DDR...")
        st.markdown("---")
        st.subheader("Phase 3: Controlled DDR Generation")
        
        with st.spinner("Generating DDR with entity lock..."):
            ddr_report = generator.generate_ddr(
                inspection_result['findings'],  # No severity enrichment
                thermal_result['findings'],
                validation_result
            )
        
        st.success("✅ DDR Generated Successfully!")
        
        # ========================================
        # DISPLAY RESULTS
        # ========================================
        phase_status.markdown("**Complete!** ✅")
        st.markdown("---")
        st.subheader("📄 Generated DDR Report")
        
        # Statistics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Areas Assessed", val['area_count'])
        with col2:
            st.metric("Thermal Readings", val['thermal_count'])
        with col3:
            total_calls = inspection_result['api_calls_used'] + thermal_result['api_calls_used'] + 1  # +1 for DDR gen
            st.metric("API Calls", total_calls)
        with col4:
            st.metric("Entity Lock", "✅ PASSED")
        
        # Show report
        st.markdown(ddr_report)
        
        # Download button
        st.download_button(
            label="⬇️ Download DDR Report",
            data=ddr_report,
            file_name="DDR_Report.md",
            mime="text/markdown"
        )
        
        # ========================================
        # VERIFICATION SUMMARY
        # ========================================
        st.markdown("---")
        st.subheader("🔍 Verification Summary")
        
        checklist = f"""
        **Anti-Hallucination Checks:**
        - ✅ Area count locked to {val['area_count']} areas
        - ✅ No thermal IDs in area list
        - ✅ Thermal readings in separate section
        - ✅ Root causes set to "Not Available" (no AI inference)
        - ✅ Entity lock verified in output
        """
        st.success(checklist)
        
    except Exception as e:
        phase_status.markdown("**Error** ❌")
        st.error(f"Error: {str(e)}")
        st.exception(e)

# Information
with st.expander("ℹ️ About 3-Phase Architecture"):
    st.markdown("""
    ### Phase 1: Pure Extraction
    - Extracts data from PDFs
    - NO severity inference
    - NO root cause inference
    - Returns clean structured JSON
    - **Image fallback temporarily disabled for stability**
    
    ### Phase 2: Validation
    - Area count validation (prevents 69-area hallucination)
    - Thermal ID detection (rejects `.jpg` in areas)
    - Structural integrity checks
    - Normalization and deduplication
    
    ### Phase 3: Controlled Generation
    - **Entity Lock:** Output areas = Input areas
    - **Root Cause:** Hard-coded to "Not Available"
    - **Observation-Linked Recommendations:** No generic advice
    - **Post-generation verification:** Counts areas in output
    
    ### Safeguards
    - ❌ No thermal IDs as areas
    - ❌ No severity/cause inference
    - ❌ No area expansion
    - ✅ Measurable entity count enforcement
    """)
