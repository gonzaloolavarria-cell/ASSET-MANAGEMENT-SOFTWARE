"""Page 20: Equipment Manual Chat — Claude Native RAG with prompt caching.

"NotebookLM para equipos" — technicians ask questions about equipment manuals
in any language. Claude responds using 200K context window loaded with manual
content and equipment library data. No vector DB required.
"""

import streamlit as st
from streamlit_app.i18n import page_init, t
from streamlit_app.style import apply_style

st.set_page_config(page_title="Equipment Chat", page_icon="💬", layout="wide")
page_init()
apply_style()
try:
    from streamlit_app.components.role_banner import role_context_banner
    role_context_banner(20)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Lazy imports (avoid import errors if anthropic not installed)
# ---------------------------------------------------------------------------

def _get_anthropic_client():
    """Create Anthropic client, or return None if not configured."""
    try:
        from anthropic import Anthropic
        from api.config import settings
        if not settings.ANTHROPIC_API_KEY:
            return None
        return Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    except Exception:
        return None


def _get_equipment_types() -> dict[str, str]:
    """Return {equipment_type_id: display_name} from equipment library."""
    try:
        from tools.engines.manual_loader import get_equipment_type_names
        return get_equipment_type_names()
    except Exception:
        return {}


def _build_system_prompt(equipment_type_id: str, equipment_tag: str) -> list[dict]:
    """Build system prompt with prompt caching."""
    from tools.engines.manual_loader import build_chat_system_prompt
    return build_chat_system_prompt(equipment_type_id, equipment_tag)


def _get_context_info(equipment_type_id: str) -> tuple[int, bool]:
    """Return (total_tokens, has_manuals) for the equipment type."""
    from tools.engines.manual_loader import load_equipment_context
    sections = load_equipment_context(equipment_type_id)
    total = sum(s.token_estimate for s in sections)
    has_manuals = any(s.source != "equipment-library" for s in sections)
    return total, has_manuals


# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "chat_equipment_type" not in st.session_state:
    st.session_state.chat_equipment_type = None
if "chat_system_prompt" not in st.session_state:
    st.session_state.chat_system_prompt = None

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title(t("equipment_chat.title"))
st.markdown(t("equipment_chat.subtitle"))

# ---------------------------------------------------------------------------
# Check API key
# ---------------------------------------------------------------------------

client = _get_anthropic_client()
if client is None:
    st.warning(t("equipment_chat.no_api_key"))
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar: Equipment selector
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader(t("equipment_chat.equipment_info"))

    equipment_types = _get_equipment_types()
    if not equipment_types:
        st.error("Equipment library not found.")
        st.stop()

    type_options = {name: type_id for type_id, name in sorted(equipment_types.items(), key=lambda x: x[1])}
    selected_name = st.selectbox(
        t("equipment_chat.select_equipment_type"),
        list(type_options.keys()),
    )
    selected_type_id = type_options[selected_name]

    equipment_tag = st.text_input(
        t("equipment_chat.equipment_tag"),
        placeholder="e.g., BRY-SAG-ML-001",
    )

    # Detect equipment change → reset chat
    if st.session_state.chat_equipment_type != selected_type_id:
        st.session_state.chat_equipment_type = selected_type_id
        st.session_state.chat_messages = []
        st.session_state.chat_system_prompt = None

    # Load context info
    total_tokens, has_manuals = _get_context_info(selected_type_id)

    if has_manuals:
        st.success(t("equipment_chat.manual_loaded", sections="", tokens=str(total_tokens // 1000)))
    else:
        st.info(t("equipment_chat.using_library_only"))

    st.metric("Context", f"~{total_tokens // 1000}K tokens")

    if st.button(t("equipment_chat.clear_chat"), use_container_width=True):
        st.session_state.chat_messages = []
        st.session_state.chat_system_prompt = None
        st.rerun()

# ---------------------------------------------------------------------------
# Build system prompt (cached in session state per equipment type)
# ---------------------------------------------------------------------------

if st.session_state.chat_system_prompt is None:
    st.session_state.chat_system_prompt = _build_system_prompt(selected_type_id, equipment_tag)

# ---------------------------------------------------------------------------
# Welcome message and suggested questions
# ---------------------------------------------------------------------------

if not st.session_state.chat_messages:
    with st.chat_message("assistant"):
        st.markdown(t("equipment_chat.welcome_message", equipment=selected_name))

    st.markdown(f"**{t('equipment_chat.suggested_questions')}:**")
    cols = st.columns(3)
    suggestions = [
        t("equipment_chat.sq_maintenance"),
        t("equipment_chat.sq_troubleshooting"),
        t("equipment_chat.sq_failure_modes"),
    ]
    for i, suggestion in enumerate(suggestions):
        if cols[i].button(suggestion, key=f"suggestion_{i}", use_container_width=True):
            st.session_state.chat_messages.append({"role": "user", "content": suggestion})
            st.rerun()

# ---------------------------------------------------------------------------
# Display chat history
# ---------------------------------------------------------------------------

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

if user_input := st.chat_input(t("equipment_chat.ask_placeholder")):
    # Append user message
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Generate response
    with st.chat_message("assistant"):
        try:
            with client.messages.stream(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4096,
                system=st.session_state.chat_system_prompt,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.chat_messages
                ],
            ) as stream:
                response_text = st.write_stream(
                    chunk.text for chunk in stream.text_stream
                )
            st.session_state.chat_messages.append({"role": "assistant", "content": response_text})
        except Exception as e:
            error_msg = t("equipment_chat.error_response", error=str(e))
            st.error(error_msg)
            st.session_state.chat_messages.append({"role": "assistant", "content": f"Error: {e}"})
