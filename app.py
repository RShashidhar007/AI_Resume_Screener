import streamlit as st
import pandas as pd
import os
import io
import plotly.express as px
from streamlit_option_menu import option_menu
from streamlit_lottie import st_lottie
import requests
import re
from pypdf import PdfReader

def load_lottieurl(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib
import uuid
from datetime import datetime
import sqlite3

# --- Streamlit Page Config ---
st.set_page_config(
    page_title="HireSense AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Database Setup ---
def init_db():
    """Initialize SQLite database with necessary tables"""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        name TEXT,
        job_title TEXT,
        company TEXT,
        date_joined TEXT,
        last_login TEXT
    )
    ''')
    
    # Create ranking history table
    c.execute('''
    CREATE TABLE IF NOT EXISTS ranking_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        job_title TEXT,
        description TEXT,
        results TEXT,
        FOREIGN KEY (email) REFERENCES users (email)
    )
    ''')
    
    # Auto-create default user 'raghu' for easy access
    c.execute("SELECT email FROM users WHERE email = 'raghu'")
    if not c.fetchone():
        salt = uuid.uuid4().hex
        hashed = hashlib.sha256(salt.encode() + "raghu123".encode()).hexdigest()
        hashed_password = f"{salt}${hashed}"
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("raghu", hashed_password, "Raghu", "", "", current_date, current_date)
        )
    
    conn.commit()
    conn.close()

# --- Initialize Session State ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["user_email"] = None
    st.session_state["user_name"] = None
    st.session_state["profile_tab"] = "profile"
    st.session_state["current_page"] = "login"  # Default page: login, register, dashboard, profile

# --- Security Functions ---
def hash_password(password, salt=None):
    """Hash a password for storing."""
    if salt is None:
        salt = uuid.uuid4().hex
    hashed = hashlib.sha256(salt.encode() + password.encode()).hexdigest()
    return f"{salt}${hashed}"

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    salt, hashed = stored_password.split('$')
    return hashed == hashlib.sha256(salt.encode() + provided_password.encode()).hexdigest()

# --- User Management Functions ---
def save_user(email, password, name=""):
    """Registers a new user in the database."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT email FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return False  # User already exists
    
    # Hash the password
    hashed_password = hash_password(password)
    
    # Create new user with timestamp
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
        (email, hashed_password, name, "", "", current_date, current_date)
    )
    
    conn.commit()
    conn.close()
    return True

def authenticate_user(email, password):
    """Authenticate a user with email and password."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute("SELECT password FROM users WHERE email = ?", (email,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return False
    
    stored_password = result[0]
    
    if verify_password(stored_password, password):
        # Update last login time
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE users SET last_login = ? WHERE email = ?", (current_date, email))
        conn.commit()
        conn.close()
        return True
    
    conn.close()
    return False

def update_profile(email, name, job_title, company):
    """Update user profile information."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute(
        "UPDATE users SET name = ?, job_title = ?, company = ? WHERE email = ?",
        (name, job_title, company, email)
    )
    
    conn.commit()
    conn.close()
    return True

def get_user_profile(email):
    """Get user profile data."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute(
        "SELECT email, name, job_title, company, date_joined, last_login FROM users WHERE email = ?",
        (email,)
    )
    
    result = c.fetchone()
    conn.close()
    
    if not result:
        return None
    
    return {
        "email": result[0],
        "name": result[1],
        "job_title": result[2],
        "company": result[3],
        "date_joined": result[4],
        "last_login": result[5]
    }

def change_password(email, current_password, new_password):
    """Change user password."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    c.execute("SELECT password FROM users WHERE email = ?", (email,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return False, "User not found"
    
    stored_password = result[0]
    
    if not verify_password(stored_password, current_password):
        conn.close()
        return False, "Current password is incorrect"
    
    # Hash the new password
    hashed_password = hash_password(new_password)
    
    # Update password
    c.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
    conn.commit()
    conn.close()
    
    return True, "Password changed successfully"

# --- Resume History Functions ---
def save_ranking_history(email, job_title, description, results):
    """Save resume ranking history for the user."""
    conn = sqlite3.connect('Resume.db')
    c = conn.cursor()
    
    # Create new history entry
    c.execute(
        "INSERT INTO ranking_history (email, timestamp, job_title, description, results) VALUES (?, ?, ?, ?, ?)",
        (
            email,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            job_title,
            description,
            results.to_json()
        )
    )
    
    conn.commit()
    conn.close()

def get_user_history(email):
    """Get resume ranking history for the user."""
    conn = sqlite3.connect('Resume.db')
    
    # Get all history records for the user
    query = "SELECT id, timestamp, job_title, description, results FROM ranking_history WHERE email = ? ORDER BY timestamp DESC"
    history_df = pd.read_sql_query(query, conn, params=(email,))
    
    conn.close()
    
    return history_df

# --- Resume Processing Functions ---
def extract_text_from_pdf(file):
    """Extracts text from an uploaded PDF file."""
    try:
        pdf = PdfReader(file)
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip() if text else "No readable text found."
    except Exception as e:
        return f"Error extracting text: {str(e)}"

def rank_resumes(job_description, resumes):
    """Ranks resumes based on their similarity to the job description."""
    documents = [job_description] + resumes
    vectorizer = TfidfVectorizer().fit_transform(documents)
    vectors = vectorizer.toarray()
    job_description_vector = vectors[0]
    resume_vectors = vectors[1:]
    cosine_similarities = cosine_similarity([job_description_vector], resume_vectors).flatten()
    return cosine_similarities


# Add custom CSS for better styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }
        
        .stButton>button {
            background-color: #1fc7d4;
            color: #1d252c;
            font-size: 16px;
            font-weight: 600;
            border-radius: 8px;
            padding: 12px 24px;
            border: none;
            transition: all 0.3s ease;
            box-shadow: 0 4px 6px -1px rgba(31, 199, 212, 0.2), 0 2px 4px -1px rgba(31, 199, 212, 0.1);
        }
        .stButton>button:hover {
            background-color: #17a9b4;
            color: white;
            box-shadow: 0 6px 8px -1px rgba(31, 199, 212, 0.3), 0 3px 6px -1px rgba(31, 199, 212, 0.2);
            transform: translateY(-1px);
        }
        .stButton>button:active {
            color: white;
        }
        
        .stTextInput>div>div>input {
            font-size: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            padding: 12px 16px;
            transition: border-color 0.2s ease;
            background-color: #f8fafc;
        }
        .stTextInput>div>div>input:focus {
            border-color: #1fc7d4;
            box-shadow: 0 0 0 1px #1fc7d4;
        }
        .stTextArea>div>div>textarea {
            font-size: 15px;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
            padding: 12px 16px;
            background-color: #f8fafc;
        }
        
        /* Titles and Text */
        h1, h2, h3 {
            color: #1e293b;
        }
        p {
            color: #475569;
        }
        
        .stTabs>div>div>button {
            font-size: 16px;
            font-weight: 600;
            color: #475569;
        }
        .stTabs>div>div>button[data-baseweb="tab"][aria-selected="true"] {
            color: #1fc7d4;
        }
        
        /* Card Styling for Login/Register */
        [data-testid="column"]:nth-of-type(3) > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
            background: white;
            border-radius: 16px;
            padding: 1rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
            border: 1px solid #f1f5f9;
        }
        
        /* General app background for unauthenticated state */
        .stApp {
            background-color: #fafbfc;
        }
    </style>
""", unsafe_allow_html=True)

# --- Main Navigation --- 
def show_login_page():
    st.markdown("<h2 style='text-align: center; color: #1e293b; margin-bottom: 0.5rem;'>Welcome back</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; margin-bottom: 2rem;'>Enter your credentials to access your account.</p>", unsafe_allow_html=True)
    
    login_email = st.text_input("👤 Username", value="raghu", key="login_email", placeholder="Enter your username")
    login_password = st.text_input("🔑 Password", value="raghu123", type="password", key="login_password", placeholder="Enter your password")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🔐 Login", use_container_width=True):
        if authenticate_user(login_email, login_password):
            st.session_state["authenticated"] = True
            st.session_state["user_email"] = login_email
            profile = get_user_profile(login_email)
            st.session_state["user_name"] = profile["name"]
            st.session_state["current_page"] = "dashboard"
            st.rerun()
        else:
            st.error("❌ Invalid username or password")
            
    st.markdown("<p style='text-align: center; margin-top: 1.5rem;'>Don't have an account?</p>", unsafe_allow_html=True)
    if st.button("📝 Create an account", use_container_width=True):
        st.session_state["current_page"] = "register"
        st.rerun()

def show_register_page():
    st.markdown("<h2 style='text-align: center; color: #1e293b; margin-bottom: 0.5rem;'>Create an account</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; margin-bottom: 2rem;'>Join HireSense AI to streamline your hiring.</p>", unsafe_allow_html=True)
    
    reg_email = st.text_input("👤 Username*", key="reg_email", placeholder="Enter your username")
    reg_name = st.text_input("👤 Full Name", key="reg_name", placeholder="Enter your full name")
    reg_password = st.text_input("🔑 Password*", type="password", key="reg_password", placeholder="Enter your password")
    reg_confirm_password = st.text_input("🔑 Confirm Password*", type="password", key="reg_confirm_password", placeholder="Confirm your password")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("✅ Register", use_container_width=True):
        if not reg_email or not reg_password:
            st.error("❌ Username and password are required")
        elif reg_password != reg_confirm_password:
            st.error("❌ Passwords do not match")
        else:
            if save_user(reg_email, reg_password, reg_name):
                st.toast("✅ Registration successful! You can now log in.")
                st.session_state["current_page"] = "login"
                st.rerun()
            else:
                st.warning("⚠ Username already taken. Please log in instead.")
                st.session_state["current_page"] = "login"
                st.rerun()
                
    st.markdown("<p style='text-align: center; margin-top: 1.5rem;'>Already have an account?</p>", unsafe_allow_html=True)
    if st.button("↩️ Log in", use_container_width=True):
        st.session_state["current_page"] = "login"
        st.rerun()

def show_profile_page():
    st.title("👤 User Profile")
    st.markdown("### Manage your profile information and preferences.")
    
    profile = get_user_profile(st.session_state["user_email"])
    if not profile:
        st.error("❌ Error loading profile data")
        return
    
    # Profile tabs
    profile_tab, password_tab, history_tab = st.tabs(["✏️ Edit Profile", "🔐 Change Password", "📊 History"])
    
    with profile_tab:
        st.subheader("Personal Information")
        
        name = st.text_input("Full Name", value=profile["name"] if profile["name"] else "")
        job_title = st.text_input("Job Title", value=profile["job_title"] if profile["job_title"] else "")
        company = st.text_input("Company", value=profile["company"] if profile["company"] else "")
        
        if st.button("💾 Save Profile"):
            if update_profile(profile["email"], name, job_title, company):
                st.session_state["user_name"] = name
                st.toast("✅ Profile updated successfully!")
                st.rerun()
            else:
                st.error("❌ Error updating profile")
    
    with password_tab:
        st.subheader("Change Password")
        
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_new_password = st.text_input("Confirm New Password", type="password")
        
        if st.button("🔄 Update Password"):
            if not current_password or not new_password or not confirm_new_password:
                st.error("❌ All fields are required")
            elif new_password != confirm_new_password:
                st.error("❌ New passwords do not match")
            else:
                success, message = change_password(profile["email"], current_password, new_password)
                if success:
                    st.toast(f"✅ {message}")
                else:
                    st.error(f"❌ {message}")
    
    with history_tab:
        st.subheader("Resume Ranking History")
        
        history = get_user_history(profile["email"])
        if history.empty:
            st.info("📝 No ranking history found")
        else:
            for idx, row in history.iterrows():
                with st.expander(f"Job: {row['job_title']} - {row['timestamp']}"):
                    st.text_area("Job Description", value=row["description"], height=100, disabled=True, key=f"job_desc_{idx}")
        try:
            results = pd.read_json(row["results"])
            st.dataframe(results, hide_index=True)
        except:
            st.warning("⚠ Error loading results data")



def show_dashboard():
    welcome_name = st.session_state["user_name"] or st.session_state["user_email"]

    # Title with gradient effect using HTML
    st.markdown("""
        <h2 style="
            background: -webkit-linear-gradient(45deg, #1FA2FF, #12D8FA);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            text-align: center;
            font-size: 2.5rem;">
            🚀 Welcome to HireSense AI
        </h2>
    """, unsafe_allow_html=True)

    st.markdown(f"<div style='text-align:center; font-size:18px;'>Welcome back, <b style='color:#4CAF50'>{welcome_name}</b> 👋</div>", unsafe_allow_html=True)
    st.markdown("### ")

    # --- Job Information Section ---
    with st.container():
        st.subheader("📄 Job Information")
        st.markdown("Fill in the job details to start screening candidates.")
        job_title = st.text_input("Job Title", placeholder="e.g., Trainee Engineer", label_visibility="visible")

    st.markdown("---")

    # --- Job Description & Resume Upload ---
    st.subheader("📋 Job Description & 📂 Resume Upload")

    col1, col2 = st.columns([1.2, 1])

    with col1:
        job_description = st.text_area(
            "Job Description",
            placeholder="Paste or write the full job description here...",
            height=220,
            key="job_desc"
        )

    with col2:
        st.markdown("#### Upload Resumes")
        uploaded_files = st.file_uploader(
            "Select PDF resumes",
            type=["pdf"],
            accept_multiple_files=True,
            key="resume_files"
        )

        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} resume(s) uploaded successfully")

    st.markdown("---")

    # Optional: Next step / action button
    st.markdown("### Ready to rank candidates?")

    # --- Processing & Ranking ---
    if st.button("🔍 Rank Resumes", disabled=not (uploaded_files and job_description)):
        with st.spinner("🔍 Processing resumes..."):
            resumes = []
            file_names = []
            error_files = []
            
            # Process each resume
            progress_bar = st.progress(0)
            status_text = st.empty()
            total_files = len(uploaded_files)
            
            for i, file in enumerate(uploaded_files):
                status_text.text(f"Processing {file.name} ({i+1}/{total_files})...")
                text = extract_text_from_pdf(file)
                if "Error extracting text" in text:
                    error_files.append(file.name)
                else:
                    resumes.append(text)
                    file_names.append(file.name)
                progress_bar.progress((i + 1) / total_files)
            
            status_text.empty()
            progress_bar.empty()
            
            if error_files:
                st.warning(f"⚠ Could not process {len(error_files)} files: {', '.join(error_files)}")
            
            if resumes:
                scores = rank_resumes(job_description, resumes)
                ranked_resumes = sorted(zip(file_names, scores), key=lambda x: x[1], reverse=True)
                
                # Create results dataframe
                results_df = pd.DataFrame({
                    "Rank": range(1, len(ranked_resumes) + 1),
                    "Resume Name": [name for name, _ in ranked_resumes],
                    "Match Score": [score for _, score in ranked_resumes],
                    "Raw Score": [score for _, score in ranked_resumes]
                })

                # --- Summary Metrics ---
                st.markdown("---")
                st.subheader("📈 Quick Insights")
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Resumes Scanned", len(results_df))
                avg_score = f"{results_df['Raw Score'].mean() * 100:.1f}%"
                m2.metric("Average Match Score", avg_score)
                highly_rec = len(results_df[results_df["Raw Score"] >= 0.75])
                m3.metric("Highly Recommended (>75%)", highly_rec)
                
                # --- Candidate Profile Cards (Top 3) ---
                st.markdown("---")
                st.subheader("🌟 Top Candidates Profiles")
                top_3 = results_df.head(3)
                cols = st.columns(len(top_3))
                for idx, (_, row) in enumerate(top_3.iterrows()):
                    with cols[idx]:
                        with st.container(border=True):
                            st.markdown(f"<h3 style='text-align: center;'>👤 {row['Resume Name']}</h3>", unsafe_allow_html=True)
                            st.markdown(f"<h2 style='text-align: center; color: #4CAF50;'>{row['Match Score']*100:.1f}%</h2>", unsafe_allow_html=True)
                            st.markdown(f"<p style='text-align: center;'>Rank: #{row['Rank']}</p>", unsafe_allow_html=True)
                            with st.expander("🧠 Why this score?"):
                                resume_text = resumes[file_names.index(row['Resume Name'])].lower()
                                jd_words = set(re.findall(r'\b[a-z]{5,}\b', job_description.lower()))
                                matched = [w for w in jd_words if w in resume_text]
                                if matched:
                                    st.markdown("**Matched Keywords:**")
                                    st.markdown(" ".join([f"`{w}`" for w in matched[:12]]))
                                else:
                                    st.markdown("*Matched general semantics.*")
                
                # --- Detailed Results ---
                st.markdown("---")
                st.subheader("🏆 Ranked Resumes (All Data)")
                styled_df = results_df.drop(columns=["Raw Score"]).style.format({"Match Score": "{:.1%}"}).background_gradient(subset=["Match Score"], cmap="Greens")
                st.dataframe(styled_df, hide_index=True)
                
                # --- Visualize top candidates (Plotly) ---
                st.subheader("📊 Match Score Distribution")
                top_n = min(len(results_df), 10)
                chart_data = results_df.head(top_n).copy()
                fig = px.bar(
                    chart_data, 
                    x="Resume Name", 
                    y="Raw Score",
                    color="Raw Score",
                    color_continuous_scale="Viridis",
                    text_auto='.1%'
                )
                fig.update_layout(
                    yaxis_tickformat='.0%',
                    xaxis_title="Candidate Name",
                    yaxis_title="Match Score",
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Save ranking history
                save_ranking_history(
                    st.session_state["user_email"],
                    job_title if job_title else "Unnamed Job",
                    job_description,
                    results_df
                )
                
                # Download options
                col1, col2 = st.columns(2)
                with col1:
                    csv = results_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download CSV", csv, "ranked_resumes.csv", "text/csv")
                with col2:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        results_df.to_excel(writer, index=False)
                    buffer.seek(0)
                    st.download_button("📥 Download Excel", buffer, "ranked_resumes.xlsx", 
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.error("❌ No valid resumes to process")

# --- App Sidebar ---
def render_sidebar():
    if not st.session_state.get("authenticated", False):
        return  # Hide sidebar content for unauthenticated users

    st.sidebar.markdown("""
<h2 style="
    text-align: center;
    font-weight: bold;
    font-size: 48px;
    background: linear-gradient(90deg, #4CAF50, #2196F3);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
">
    HireSense AI
</h2>
                        """, unsafe_allow_html=True)
    
    if st.session_state["authenticated"]:
        st.sidebar.subheader(f"👤 {st.session_state['user_email']}")
        
        # Navigation
        st.sidebar.markdown("---")
        with st.sidebar:
            selected = option_menu(
                menu_title="Navigation",
                options=["Dashboard", "My Profile", "Logout"],
                icons=["house", "person", "box-arrow-right"],
                menu_icon="cast",
                default_index=0 if st.session_state["current_page"] == "dashboard" else 1
            )
            
        if selected == "Dashboard" and st.session_state["current_page"] != "dashboard":
            st.session_state["current_page"] = "dashboard"
            st.rerun()
        elif selected == "My Profile" and st.session_state["current_page"] != "profile":
            st.session_state["current_page"] = "profile"
            st.rerun()
        elif selected == "Logout":
            st.session_state["authenticated"] = False
            st.session_state["user_email"] = None
            st.session_state["user_name"] = None
            st.session_state["current_page"] = "login"
            st.toast("👋 Logged out successfully!")
            st.rerun()

# --- Global Footer (outside sidebar) ---
def render_footer():
    st.markdown("""
        <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            background-color: #f1f1f1;
            color: #555;
            text-align: center;
            padding: 10px 0;
            font-size: 14px;
            border-top: 1px solid #ccc;
        }
        </style>
        <div class="footer">
            © 2026 AI HireSense AI
        </div>
    """, unsafe_allow_html=True)


# --- Main App Logic ---
def main():
    # Initialize database
    init_db()
    
    render_sidebar()
    
    if not st.session_state.get("authenticated", False):
        # Hide the sidebar toggle and sidebar itself via CSS for clean landing page
        st.markdown("""
            <style>
                [data-testid="collapsedControl"] { display: none; }
                section[data-testid="stSidebar"] { display: none; }
                .main .block-container { max-width: 1200px; padding-top: 3rem; }
            </style>
        """, unsafe_allow_html=True)

        # Layout for landing page & login/register
        col1, col2, col3 = st.columns([1.2, 0.1, 1])
        
        with col1:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <h1 style='
                text-align: left;
                font-weight: 800;
                font-size: 4rem;
                color: #0f172a;
                line-height: 1.1;
                margin-bottom: 1.5rem;
            '>
            Hire smarter, <br>
            <span style="color: #1fc7d4;">not harder.</span>
            </h1>
            """, unsafe_allow_html=True)
            
            st.markdown("""
            <p style='font-size: 1.2rem; color: #475569; margin-bottom: 2rem; line-height: 1.6;'>
            Transform your recruitment process with AI-powered resume matching. 
            Find the perfect candidates instantly and eliminate manual screening.
            </p>
            """, unsafe_allow_html=True)
            
            # Feature list
            st.markdown("""
            <div style="display: flex; flex-direction: column; gap: 1rem; margin-bottom: 2rem;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: #e0fcfc; color: #1fc7d4; padding: 4px; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;">✓</div>
                    <span style="color: #334155; font-weight: 500; font-size: 1.1rem;">Intelligent Resume Matching</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: #e0fcfc; color: #1fc7d4; padding: 4px; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;">✓</div>
                    <span style="color: #334155; font-weight: 500; font-size: 1.1rem;">Unbiased Data-Driven Ranking</span>
                </div>
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="background: #e0fcfc; color: #1fc7d4; padding: 4px; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;">✓</div>
                    <span style="color: #334155; font-weight: 500; font-size: 1.1rem;">Secure Candidate Profiles</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            lottie_url = "https://assets3.lottiefiles.com/packages/lf20_qp1q7mct.json"
            lottie_json = load_lottieurl(lottie_url)
            if lottie_json:
                st_lottie(lottie_json, height=200, key="landing_lottie")

        with col2:
            st.empty() # Spacer
            
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            with st.container(border=True):
                if st.session_state["current_page"] == "login":
                    show_login_page()
                elif st.session_state["current_page"] == "register":
                    show_register_page()
    
    else:
        # Authenticated pages
        if st.session_state["current_page"] == "dashboard":
            show_dashboard()
        elif st.session_state["current_page"] == "profile":
            show_profile_page()

if __name__ == "__main__":
    main()