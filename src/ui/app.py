import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import uuid
import time
import os

# -------------------------------
# PAGE CONFIG
# -------------------------------
st.set_page_config(
    page_title="RAG AI Chat",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------------
# API + ADMIN CONFIG
# -------------------------------
DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8000")
ADMIN_USERNAME = "admin" # Fixed missing variable
ADMIN_PASSWORD = "admin"

# -------------------------------
# CUSTOM CSS (ENHANCED)
# -------------------------------
st.markdown("""
<style>
    /* Main Background */
    .stApp { 
        background-color: #0E1117;
        color: #C9D1D9; /* Light Text */
    }
    
    /* Animation Keyframes */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* Card Styles for Role Selection */
    .role-card {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 2rem;
        text-align: center;
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
        height: 100%;
        animation: fadeIn 0.8s ease-out;
    }
    .role-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
        border-color: #58A6FF;
    }
    .role-title {
        color: #F0F6FC;
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .role-desc {
        color: #8B949E;
        font-size: 1rem;
    }

    /* Sidebar & Chat Styles */
    section[data-testid="stSidebar"] {
        background-color: #161B22;
        border-right: 1px solid #30363D;
        width: 300px !important;
    }
    .stChatMessage {
        background-color: #161B22;
        border: 1px solid #30363D;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .stChatMessage .stAvatar { background-color: #238636; }
    div[data-testid="stChatMessage"] svg { fill: white; }
    
    /* Headers */
    h1, h2, h3 { color: #F0F6FC; }
    
    /* Buttons */
    .stButton button {
        background-color: #238636; 
        color: white; 
        border: none;
        border-radius: 6px; 
        font-weight: 600; 
        padding: 0.5rem 1rem;
        transition: all 0.2s;
    }
    .stButton button:hover { background-color: #2EA043; transform: scale(1.02); }
    
    /* Input Fields */
    .stChatInput textarea, .stTextInput input {
        background-color: #0D1117;
        border: 1px solid #30363D;
        color: #C9D1D9;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------
# STATE MANAGEMENT
# -------------------------------
if "initialized" not in st.session_state:
    st.session_state.initialized = True
    st.session_state.sessions = {}
    st.session_state.active_session_id = None
    st.session_state.admin_logged_in = False
    st.session_state.view_mode = "Splash" # Splash -> RoleSelect -> App (User/Admin)
    st.session_state.role = None # "User" or "Admin"
    st.session_state.intro_complete = False

# -------------------------------
# OPTIMIZATION: CACHED REQUESTS
# -------------------------------
@st.cache_data(ttl=5)
def fetch_telemetry_stats():
    """Fetches stats from the API with a 5-second cache to avoid spamming the backend."""
    try:
        res = requests.get(f"{DEFAULT_API_URL}/stats", timeout=5)
        if res.status_code == 200:
            return res.json()
    except:
        pass
    return None

# -------------------------------
# 1️⃣ SPLASH SCREEN (ANIMATION)
# -------------------------------
if st.session_state.view_mode == "Splash":
    empty_slot = st.empty()
    
    if not st.session_state.intro_complete:
        # Simple Typewriter Eillfect
        welcome_text = "Welcome to Market Analysis AI..."
        displayed_text = ""
        
        # Center the text
        with empty_slot.container():
            st.markdown("<br><br><br><br><br>", unsafe_allow_html=True) # Spacing
            title_placeholder = st.empty()
            
            for char in welcome_text:
                displayed_text += char
                title_placeholder.markdown(f"<h1 style='text-align: center; font-size: 3rem;'>{displayed_text}</h1>", unsafe_allow_html=True)
                time.sleep(0.05) # Speed of typing
            
            time.sleep(0.5)
            st.session_state.intro_complete = True
            st.session_state.view_mode = "RoleSelect"
            st.rerun()
    else:
        st.session_state.view_mode = "RoleSelect"
        st.rerun()

# -------------------------------
# 2️⃣ ROLE SELECTION
# -------------------------------
elif st.session_state.view_mode == "RoleSelect":
    st.markdown("<h1 style='text-align: center; margin-bottom: 50px;'>Choose Your Access</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("""
            <div class="role-card">
                <div style="font-size: 3rem;">👤</div>
                <div class="role-title">User Access</div>
                <div class="role-desc">Analyze markets and companies</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Enter as User", key="btn_user", use_container_width=True):
                st.session_state.role = "User"
                st.session_state.view_mode = "UserLanding"
                st.rerun()
                
        with c2:
            st.markdown("""
            <div class="role-card">
                <div style="font-size: 3rem;">🛡️</div>
                <div class="role-title">Admin Portal</div>
                <div class="role-desc">System monitoring & logs</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Enter as Admin", key="btn_admin", use_container_width=True):
                st.session_state.role = "Admin"
                st.session_state.view_mode = "AdminLogin"
                st.rerun()

# -------------------------------
# 3️⃣ USER ACCESS FLOW
# -------------------------------
elif st.session_state.role == "User":
    
    # Back to Home
    with st.sidebar:
        if st.button("⬅️ Switch Role"):
            st.session_state.view_mode = "RoleSelect"
            st.session_state.role = None
            st.rerun()
        st.markdown("---")

    # A. USER LANDING
    if st.session_state.view_mode == "UserLanding":
        st.markdown("""
            <div style="text-align:center; margin-top:50px; animation: fadeIn 1s;">
                <h1>Ready to Analyze?</h1>
                <p style="color:#8B949E; font-size:1.2rem;">Get insights on companies, trends, and financial risks.</p>
            </div>
        """, unsafe_allow_html=True)
        
        _, col, _ = st.columns([1, 2, 1])
        with col:
            if st.button("🚀 Start Analysis", use_container_width=True):
                 # Create fresh session if needed
                if not st.session_state.active_session_id:
                     sid = str(uuid.uuid4())
                     st.session_state.sessions[sid] = {"messages": [], "title": "New Analysis"}
                     st.session_state.active_session_id = sid
                
                st.session_state.view_mode = "Market Analysis"
                st.rerun()

    # B. CHAT INTERFACE
    elif st.session_state.view_mode == "Market Analysis":
        with st.sidebar:
            st.markdown("### Chat History")
            if st.button("➕ New Chat", use_container_width=True):
                sid = str(uuid.uuid4())
                st.session_state.sessions[sid] = {"messages": [], "title": "New Analysis"}
                st.session_state.active_session_id = sid
                st.rerun()
            
            st.markdown("---")
            for sid in reversed(list(st.session_state.sessions.keys())):
                if st.button(f"💬 {st.session_state.sessions[sid]['title']}", use_container_width=True, key=sid):
                    st.session_state.active_session_id = sid
                    st.rerun()

        st.title("Market Analysis")

        if st.session_state.active_session_id not in st.session_state.sessions:
             # Fallback creates a new session
             sid = str(uuid.uuid4())
             st.session_state.sessions[sid] = {"messages": [], "title": "New Analysis"}
             st.session_state.active_session_id = sid

        session = st.session_state.sessions[st.session_state.active_session_id]
        messages = session["messages"]

        if not messages:
            st.info("💡 Tip: Ask about specific companies (e.g., 'Analyze Tesla's Q3 revenue').")

        for msg in messages:
            avatar = "👤" if msg["role"] == "user" else "🤖"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        # 🔄 RECOVERY: Check if last message was user (interrupted state)
        if messages and messages[-1]["role"] == "user":
            st.warning("⚠️ The last response was interrupted.")
            if st.button("🔄 Retry Last Request"):
                last_query = messages[-1]["content"]
                with st.chat_message("assistant", avatar="🤖"):
                    placeholder = st.empty()
                    with st.spinner("Retrying analysis..."):
                        try:
                            # Use the NEW granular stats variable to avoid breaking things? 
                            # No, just standard request.
                            res = requests.post(
                                f"{DEFAULT_API_URL}/analyze",
                                json={"query": last_query, "user_id": st.session_state.active_session_id},
                                timeout=600
                            )
                            if res.status_code == 200:
                                ans = res.json().get("answer", "No answer found.")
                            else:
                                ans = f"⚠️ System Busy (Status: {res.status_code})"
                        except Exception as e:
                            ans = f"❌ Error: {str(e)}"
                    
                    placeholder.markdown(ans)
                    messages.append({"role": "assistant", "content": ans})
                st.rerun()

        if prompt := st.chat_input("Enter company or ticker..."):
            if len(messages) == 0:
                session["title"] = " ".join(prompt.split()[:4])
            
            # 1. Add User Message to State AND Display Immediately
            messages.append({"role": "user", "content": prompt})
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
            
            # 2. Generate Assistant Response
            with st.chat_message("assistant", avatar="🤖"):
                placeholder = st.empty()
                ans = ""
                
                with st.spinner("Analyzing market data..."):
                    try:
                        res = requests.post(
                            f"{DEFAULT_API_URL}/analyze",
                            json={"query": prompt, "user_id": st.session_state.active_session_id},
                            timeout=600
                        )
                        if res.status_code == 200:
                            ans = res.json().get("answer", "No answer found.")
                        else:
                            ans = f"⚠️ System Busy (Status: {res.status_code})"
                    except Exception as e:
                        ans = f"❌ Error: {str(e)}"
                
                placeholder.markdown(ans)
                messages.append({"role": "assistant", "content": ans})
            
            # Optional: Rerun not strictly needed if we rendered in-place, 
            # but good for strict state sync. limiting to avoid flicker.
            # st.rerun()

# -------------------------------
# 4️⃣ ADMIN ACCESS FLOW
# -------------------------------
elif st.session_state.role == "Admin":
    
    # Back to Home
    with st.sidebar:
        if st.button("⬅️ Switch Role"):
            st.session_state.view_mode = "RoleSelect"
            st.session_state.role = None
            st.session_state.admin_logged_in = False
            st.rerun()

    if st.session_state.view_mode == "AdminLogin":
        st.markdown("<div style='text-align: center;'><h1>🔐 Admin Login</h1></div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,1,1])
        with col2:
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True):
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    st.session_state.admin_logged_in = True
                    st.session_state.view_mode = "AdminDashboard"
                    st.rerun()
                else:
                    st.error("❌ Invalid Credentials")

    elif st.session_state.view_mode == "AdminDashboard":
        if not st.session_state.admin_logged_in:
             st.session_state.view_mode = "AdminLogin"
             st.rerun()

        st.title("System Monitor 🛡️")
        
        # Logout
        if st.button("🚪 Logout", key="logout_btn"):
            st.session_state.admin_logged_in = False
            st.session_state.view_mode = "AdminLogin"
            st.rerun()

        st.markdown("### Live System Metrics")
        
        if st.button("🔄 Refresh Data"):
            fetch_telemetry_stats.clear() # Clear cache to force refresh
            st.rerun()

        stats = fetch_telemetry_stats() # Uses Cache

        if stats:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Status", stats.get("status", "Unknown"))
            col2.metric("Total Requests", stats.get("total_requests", 0))
            col3.metric("Avg Latency", f"{stats.get('avg_latency_ms', 0)} ms")
            col4.metric("Total Errors", stats.get("total_errors", 0))

            tab1, tab2, tab3, tab4 = st.tabs(["🚀 Latency", "⚠️ Errors", "💸 Cost & Tokens", "🧠 AI Performance"])
            
            # --- TAB 1: LATENCY ---
            with tab1:
                history = stats.get("history", [])
                if history:
                    # Line Chart: Total Latency
                    timestamps = [pd.to_datetime(x["timestamp"], unit='s') for x in history]
                    latencies = [x["latency_ms"] for x in history]
                    df_lat = pd.DataFrame({"Time": timestamps, "Latency": latencies})
                    st.plotly_chart(px.line(df_lat, x="Time", y="Latency", title="Total Latency Over Time (ms)"), use_container_width=True)
                    
                    # Pie Chart: Average Agent Breakdown
                    # Aggregate timings from all requests
                    total_breakdown = {}
                    count = 0
                    for x in history:
                        bd = x.get("breakdown", {})
                        if bd:
                            count += 1
                            for agent, duration in bd.items():
                                total_breakdown[agent] = total_breakdown.get(agent, 0) + duration
                    
                    if total_breakdown and count > 0:
                        # Average seconds
                        avg_breakdown = {k: v/count for k,v in total_breakdown.items()}
                        df_pie = pd.DataFrame(list(avg_breakdown.items()), columns=["Agent", "AvgSeconds"])
                        st.subheader("Avg Agent Latency Breakdown")
                        st.plotly_chart(px.pie(df_pie, values="AvgSeconds", names="Agent", title="Where is time being spent?"), use_container_width=True)
                else:
                    st.info("No latency data yet.")

            # --- TAB 2: ERRORS ---
            with tab2:
                history = stats.get("history", [])
                if history:
                    timestamps = [pd.to_datetime(x["timestamp"], unit='s') for x in history]
                    errors = [x.get("error", 0) for x in history] 
                    df_err = pd.DataFrame({"Time": timestamps, "Error Event": errors})
                    st.plotly_chart(px.scatter(df_err, x="Time", y="Error Event", title="Error Events (1=Error, 0=Success)"), use_container_width=True)
                else:
                    st.info("No error data yet.")
            
            # --- TAB 3: COST & TOKENS ---
            with tab3:
                history = stats.get("history", [])
                if history:
                    # Extract last request cost for quick view
                    last_req = history[-1]
                    c1, c2 = st.columns(2)
                    c1.metric("Last Query Tokens", last_req.get("tokens", 0))
                    c2.metric("Last Query Est. Cost", f"${last_req.get('cost', 0):.4f}")
                    
                    # Plot Token Usage Over Time
                    timestamps = [pd.to_datetime(x["timestamp"], unit='s') for x in history]
                    tokens = [x.get("tokens", 0) for x in history]
                    df_tok = pd.DataFrame({"Time": timestamps, "Tokens": tokens})
                    st.plotly_chart(px.bar(df_tok, x="Time", y="Tokens", title="Token Usage Per Query"), use_container_width=True)
                else:
                    st.info("No data yet.")

            # --- TAB 4: AI PERFORMANCE ---
            with tab4:
                history = stats.get("history", [])
                if history:
                    # RAG Hit Rate (Rolling Avg)
                    hits = [x.get("rag_hit", 0) for x in history]
                    hit_rate = sum(hits) / len(hits) * 100 if hits else 0
                    
                    st.metric("Global RAG Retrieval Rate", f"{hit_rate:.1f}%")
                    
                    if hit_rate < 50:
                        st.warning("⚠️ Retrieval rate is low. Check Researcher agent.")
                    else:
                        st.success("✅ Retrieval system is healthy.")
                else:
                    st.info("No data yet.")
        else:
            st.error("⚠️ Unable to fetch telemetry. Is the backend running?")