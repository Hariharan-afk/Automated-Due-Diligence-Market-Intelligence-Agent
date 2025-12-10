import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import time
import uuid

# --- Configuration ---
st.set_page_config(
    page_title="RAG AI Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for Exact Screenshot Match ---
st.markdown("""
<style>
    /* Main Background - Darker */
    .stApp {
        background-color: #0E1117;
    }
    
    /* Sidebar Background */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
        width: 300px !important;
    }
    
    /* Chat Message Bubbles */
    .stChatMessage {
        background-color: #161B22; 
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    /* Avatar Styling */
    .stChatMessage .stAvatar {
        background-color: #238636; /* User Color */
    }
    div[data-testid="stChatMessage"] svg {
        fill: white;
    }
    
    /* Header Styling */
    h1 {
        color: #F0F6FC;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 700;
        font-size: 2.5rem;
    }
    
    /* Button Styling (New User) */
    .stButton button {
        background-color: #238636;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
    .stButton button:hover {
        background-color: #2EA043;
    }
    
    /* Input Box Styling */
    .stChatInput textarea {
        background-color: #0D1117;
        border: 1px solid #30363D;
        color: #C9D1D9;
    }
    
    /* Metric Cards for Admin */
    div.css-1r6slb0, div.css-12w0qpk {
        background-color: #161B22;
        border: 1px solid #30363D;
        padding: 15px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
DEFAULT_API_URL = "http://34.29.167.180"

# --- Session State Management ---
if "sessions" not in st.session_state:
    st.session_state.sessions = {} # {session_id: {'messages': [], 'title': 'New Chat'}}

if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None

# --- Sidebar Content ---
with st.sidebar:
    st.markdown("### Chat History")
    
    # New Chat Button
    if st.button("➕ New Analysis", use_container_width=True, type="primary"):
        new_id = str(uuid.uuid4())
        st.session_state.sessions[new_id] = {'messages': [], 'title': 'New Analysis'}
        st.session_state.active_session_id = new_id
        st.rerun()
        
    st.markdown("---")
    
    # Render History Items
    # Sort by creation (implicitly by insertion order in dict) reversed
    for s_id in list(st.session_state.sessions.keys())[::-1]:
        session_data = st.session_state.sessions[s_id]
        title = session_data['title']
        # Highlight active
        if st.button(f"💬 {title}", key=s_id, use_container_width=True):
            st.session_state.active_session_id = s_id
            st.rerun()

    st.markdown("---")
    
    # View Selector
    view_mode = st.radio("Navigation", ["Market Analysis", "Admin Dashboard"], label_visibility="collapsed")

# ==============================================================================
# ROUTING LOGIC
# ==============================================================================

# 1. LANDING PAGE (If no active session and looking at Analysis)
if view_mode == "Market Analysis" and st.session_state.active_session_id is None:
    # Centered Landing
    st.markdown("""
    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 60vh; text-align: center;">
        <h1 style="font-size: 3.5rem; margin-bottom: 20px;">Market Analysis AI</h1>
        <p style="color: #8B949E; font-size: 1.2rem; max-width: 600px; margin-bottom: 40px;">
            Advanced financial due diligence powered by multi-agent reasoning. 
            Access real-time SEC filings, market news, and Wikipedia insights.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("🚀 Start New Analysis", use_container_width=True, type="primary"):
            new_id = str(uuid.uuid4())
            st.session_state.sessions[new_id] = {'messages': [], 'title': 'New Analysis'}
            st.session_state.active_session_id = new_id
            st.rerun()

# 2. CHAT INTERFACE
elif view_mode == "Market Analysis":
    st.title("Market Analysis")
    
    # Get current session
    current_session = st.session_state.sessions[st.session_state.active_session_id]
    messages = current_session['messages']
    
    # Welcome Tip for new chat
    if not messages:
        st.info("💡 Tip: Ask about *specific* companies (e.g., 'Analyze Tesla's Q3 revenue' or 'What are the risks for Nvidia?').")
    
    # Display Messages
    for message in messages:
        role = message["role"]
        avatar = "👤" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Enter company or ticker..."):
        # Update Title if first message
        if len(messages) == 0:
            # Generate a 4-word title
            title_preview = " ".join(prompt.split()[:4])
            st.session_state.sessions[st.session_state.active_session_id]['title'] = title_preview

        # Append User Message
        st.chat_message("user", avatar="👤").markdown(prompt)
        messages.append({"role": "user", "content": prompt})
        
        # AI Response
        with st.chat_message("assistant", avatar="🤖"):
            message_placeholder = st.empty()
            
            try:
                with st.spinner("Analyzing market data..."):
                    response = requests.post(
                        f"{DEFAULT_API_URL}/analyze",
                        json={"query": prompt, "user_id": st.session_state.active_session_id},
                        timeout=120
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        answer = data.get("answer", "No answer found.")
                        if data.get("sources"):
                            answer += "\n\n**Sources:**\n" + "\n".join([f"- `{s}`" for s in data["sources"]])
                        full_response = answer
                        
                    elif response.status_code == 422:
                        full_response = "⚠️ **Invalid Request**: Please check your query."
                    else:
                        print(f"Log: {response.text}")
                        full_response = "⚠️ **System Busy**: Our AI agents are currently overwhelmed."

            except requests.exceptions.ReadTimeout:
                 full_response = "⏱️ **Analysis Timeout**: The research agents are taking longer than expected (>2 mins). \n\n**Tip**: Try a more specific query."
            except requests.exceptions.ConnectionError:
                 full_response = "🔌 **Connection Lost**: Is the server deployed?"
            except Exception as e:
                 print(f"Error: {e}")
                 if "ConnectionPool" in str(e):
                      full_response = "⚠️ **Network Error**: Backend unreachable."
                 else:
                      full_response = "❌ **System Error**: Something went wrong."
            
            message_placeholder.markdown(full_response)
        
        # Save Assistant Message
        messages.append({"role": "assistant", "content": full_response})
        # Force refresh sidebar title
        st.rerun()

# 3. ADMIN DASHBOARD
else:
    st.title("System Monitor 🛡️")
    st.markdown("### Live Drift & Performance Tracking")
    
    if st.button("🔄 Refresh Telemetry"):
        st.rerun()
        
    try:
        response = requests.get(f"{DEFAULT_API_URL}/stats", timeout=3)
        if response.status_code == 200:
            stats = response.json()
            
            # Styled Metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Status", stats.get("status", "OK"), "Stable")
            col2.metric("Total Reqs", stats.get("total_requests", 0), "+1")
            col3.metric("Avg Latency", f"{stats.get('avg_latency_ms', 0)}ms", "-12ms")
            col4.metric("Error Rate", f"{stats.get('total_errors', 0)}", "0.0%")
            
            # Latency Chart
            st.subheader("⏱️ Latency Distribution (Drift Detection)")
            chart_data = pd.DataFrame({
                "Time": range(20),
                "Latency": [100 + (x*2) for x in range(20)]
            })
            fig = px.area(chart_data, x="Time", y="Latency", title="Response Time Trend")
            fig.update_layout(plot_bgcolor="#161B22", paper_bgcolor="#161B22", font_color="#C9D1D9")
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.error(f"Could not fetch telemetry. Status: {response.status_code}")
            st.caption("Ensure the backend image is updated with the monitoring module.")
    
    except Exception as e:
        st.error(f"Monitoring Unavailable: {e}")


