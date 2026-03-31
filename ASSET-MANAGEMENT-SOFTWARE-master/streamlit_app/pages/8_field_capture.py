"""Page 8: Field Capture — M1 Technician Input (G-08 voice + image + GPS)."""

import json

import streamlit as st
from streamlit_app import api_client
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style
from streamlit_app.components.feedback import feedback_widget
from streamlit_app.components.role_banner import role_context_banner

st.set_page_config(page_title="Field Capture", page_icon="\U0001f4f1", layout="wide")
page_init()
apply_style()
role_context_banner(8)

# Mobile-responsive CSS
st.markdown("""
<style>
/* Tablet (769-1024px) */
@media (min-width: 769px) and (max-width: 1024px) {
  .block-container { padding: 1rem 2rem !important; }
}
/* Mobile (max 768px) */
@media (max-width: 768px) {
  .block-container { padding: 0.5rem !important; }
  .stButton > button { font-size: 1.1rem; padding: 0.6rem 1rem; width: 100%; min-height: 44px; }
  .stTextInput > div, .stSelectbox > div { font-size: 1rem; }
}
/* Small phones (max 480px) */
@media (max-width: 480px) {
  .block-container { padding: 0.3rem !important; }
  .stButton > button { font-size: 1.2rem; padding: 0.8rem 1rem; width: 100%; min-height: 48px; }
  .stTextInput > div > input, .stSelectbox > div > div { font-size: 1.1rem; min-height: 44px; }
  .stTextArea > div > textarea { font-size: 1rem; }
  [data-testid="column"] { width: 100% !important; flex: 100% !important; }
}
/* Touch devices: remove hover-only effects */
@media (hover: none) {
  .stButton > button:hover { background: inherit; }
}
</style>
""", unsafe_allow_html=True)

st.title(t("capture.title"))
st.markdown(t("capture.subtitle"))

tab_submit, tab_history = st.tabs([t("capture.tab_submit"), t("capture.tab_history")])

# ── Tab 1: Submit Capture ──────────────────────────────────────────────────
with tab_submit:
    st.subheader(t("capture.new_capture"))

    # Step 1 — Technician + Location
    with st.expander("📍 Step 1 — Identify", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            technician_id = st.text_input(t("capture.technician_id"), value="TECH-001")
            capture_type = st.selectbox(
                t("capture.capture_type"),
                ["TEXT", "VOICE", "IMAGE", "VOICE+IMAGE"],
            )
            language = st.selectbox(t("capture.language"), ["en", "fr", "ar"])
        with col2:
            equipment_tag = st.text_input(
                t("capture.equipment_tag_manual"),
                placeholder="e.g., BRY-SAG-ML-001",
            )
            location_hint = st.text_input(
                t("capture.location_hint"),
                placeholder="e.g., Grinding area, level 2",
            )

        # GPS capture (requires streamlit-js-eval)
        gps_lat = None
        gps_lon = None
        try:
            from streamlit_js_eval import streamlit_js_eval
            if st.button("📡 Get GPS Location", use_container_width=True):
                gps_result = streamlit_js_eval(
                    js_expressions="""new Promise((resolve) => {
                        navigator.geolocation.getCurrentPosition(
                            pos => resolve({lat: pos.coords.latitude, lon: pos.coords.longitude, acc: pos.coords.accuracy}),
                            err => resolve(null),
                            {enableHighAccuracy: true, timeout: 10000}
                        );
                    })""",
                    key="gps_capture",
                )
                if gps_result and isinstance(gps_result, dict):
                    gps_lat = gps_result.get("lat")
                    gps_lon = gps_result.get("lon")
                    acc = gps_result.get("acc", "?")
                    st.success(f"GPS: {gps_lat:.5f}°N, {gps_lon:.5f}°W (±{acc:.0f}m)")
                    st.session_state["gps_lat"] = gps_lat
                    st.session_state["gps_lon"] = gps_lon
                elif gps_result is None:
                    st.warning("GPS unavailable. Enter equipment tag manually.")
        except ImportError:
            pass  # streamlit-js-eval not installed — GPS silently disabled

        # Restore GPS from session if available
        if gps_lat is None and "gps_lat" in st.session_state:
            gps_lat = st.session_state["gps_lat"]
            gps_lon = st.session_state.get("gps_lon")

    # Step 2 — Capture Content
    with st.expander("🎙️ Step 2 — Capture", expanded=True):
        raw_text = None
        voice_text = None
        image_analysis_json = None

        # TEXT input
        if capture_type in ("TEXT", "VOICE+IMAGE"):
            raw_text = st.text_area(
                t("capture.text_input"),
                placeholder=t("capture.text_placeholder"),
                height=120,
                key="raw_text",
            )

        # VOICE input — real audio recording + Whisper transcription
        if capture_type in ("VOICE", "VOICE+IMAGE"):
            st.markdown("**🎙️ Voice Recording**")
            audio_data = st.audio_input(
                "Record voice observation",
                key="audio_recorder",
            )
            if audio_data is not None:
                col_transcribe, col_clear = st.columns([3, 1])
                with col_transcribe:
                    if st.button("⚡ Transcribe", use_container_width=True, key="btn_transcribe"):
                        with st.spinner("Transcribing audio..."):
                            try:
                                result = api_client.transcribe_audio(
                                    audio_bytes=audio_data.getvalue(),
                                    filename="capture.webm",
                                    language=language,
                                )
                                st.session_state["voice_transcription"] = result.get("text", "")
                                detected = result.get("language_detected", language)
                                dur = result.get("duration_seconds")
                                st.success(
                                    f"Transcribed ({detected.upper()}"
                                    + (f", {dur:.1f}s" if dur else "")
                                    + ")"
                                )
                            except Exception as exc:
                                if "503" in str(exc):
                                    st.warning(
                                        "Voice transcription not configured (OPENAI_API_KEY missing). "
                                        "Enter transcription manually below."
                                    )
                                else:
                                    st.error(f"Transcription error: {exc}")

            voice_text = st.text_area(
                t("capture.voice_transcription"),
                value=st.session_state.get("voice_transcription", ""),
                placeholder=t("capture.voice_placeholder"),
                height=100,
                key="voice_text_area",
            )
            if voice_text:
                st.session_state["voice_transcription"] = voice_text

        # IMAGE input — camera or file upload + Claude Vision analysis
        if capture_type in ("IMAGE", "VOICE+IMAGE"):
            st.markdown("**📷 Image Capture**")
            img_col1, img_col2 = st.columns([1, 1])
            with img_col1:
                camera_photo = st.camera_input("Take photo (mobile)", key="camera_photo")
            with img_col2:
                uploaded_file = st.file_uploader(
                    "Upload image",
                    type=["jpg", "jpeg", "png", "webp"],
                    key="image_upload",
                )

            image_source = camera_photo or uploaded_file
            if image_source is not None:
                img_bytes = image_source.getvalue()
                img_name = getattr(image_source, "name", "capture.jpg")

                # Show thumbnail
                st.image(img_bytes, caption="Captured image", width=300)

                if st.button("🔍 Analyze Image (Claude Vision)", use_container_width=True, key="btn_analyze"):
                    with st.spinner("Analyzing equipment image..."):
                        try:
                            ctx = equipment_tag or location_hint or ""
                            analysis = api_client.analyze_image(
                                image_bytes=img_bytes,
                                filename=img_name,
                                context=ctx,
                            )
                            st.session_state["image_analysis"] = analysis
                            st.success("Image analyzed!")
                        except Exception as exc:
                            st.error(f"Image analysis error: {exc}")

            # Show analysis results
            if "image_analysis" in st.session_state:
                ia = st.session_state["image_analysis"]
                image_analysis_json = json.dumps(ia)
                with st.container():
                    st.markdown("**🔎 Vision Analysis Results:**")
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Component", ia.get("component_identified") or "Unknown")
                    col_b.metric("Severity", ia.get("severity_visual") or "LOW")
                    anomalies = ia.get("anomalies_detected") or []
                    col_c.metric("Anomalies", len(anomalies))
                    if anomalies:
                        st.write("Detected:", ", ".join(anomalies))

    # Step 3 — Review + Submit
    with st.expander("✅ Step 3 — Submit", expanded=True):
        submit_disabled = not (raw_text or voice_text or image_analysis_json)
        if submit_disabled:
            st.info("Add text, voice transcription, or analyze an image before submitting.")

        if st.button(t("capture.submit_capture"), type="primary", use_container_width=True, disabled=submit_disabled):
            data: dict = {
                "technician_id": technician_id,
                "technician_name": f"Tech {technician_id}",
                "capture_type": capture_type,
                "language": language,
                "equipment_tag_manual": equipment_tag or None,
                "location_hint": location_hint or None,
            }
            if raw_text:
                data["raw_text_input"] = raw_text
            if voice_text:
                data["raw_voice_text"] = voice_text
            if image_analysis_json:
                data["image_analysis_json"] = image_analysis_json
            if gps_lat is not None:
                data["gps_lat"] = gps_lat
                data["gps_lon"] = gps_lon

            with st.spinner("Processing capture..."):
                try:
                    result = api_client.submit_capture(data)
                    st.success(t("capture.capture_success"))

                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric(t("capture.equipment_tag"), result.get("equipment_tag", "UNKNOWN"))
                    col_b.metric(t("capture.confidence"), f"{result.get('equipment_confidence', 0):.0%}")
                    col_c.metric(t("capture.priority"), result.get("priority_suggested", "N/A"))
                    col_d.metric("Resolution", result.get("resolution_method", "N/A"))

                    if result.get("failure_mode_code"):
                        st.info(f"Failure Mode: {result['failure_mode_code']}")

                    # Clear session state after successful submission
                    for key in ["voice_transcription", "image_analysis", "gps_lat", "gps_lon"]:
                        st.session_state.pop(key, None)

                    with st.expander("Full result JSON"):
                        st.json(result)
                except Exception as e:
                    st.error(f"Error: {e}")

# ── Tab 2: History ─────────────────────────────────────────────────────────
with tab_history:
    st.subheader(t("capture.recent_captures"))
    try:
        captures = api_client.list_captures()
        if not captures:
            st.info(t("capture.no_captures"))
        else:
            st.dataframe(captures, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not load captures: {e}")

feedback_widget("field_capture")
