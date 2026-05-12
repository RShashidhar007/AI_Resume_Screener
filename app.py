import streamlit as st
import pandas as pd
import os
import io
from dotenv import load_dotenv
load_dotenv()
import plotly.express as px
from streamlit_option_menu import option_menu
from streamlit_lottie import st_lottie
import requests
import re
from pypdf import PdfReader
import docx
try:
    import groq
except ImportError:
    groq = None

def load_lottieurl(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
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

def extract_text_from_docx(file):
    """Extracts text from an uploaded DOCX file."""
    try:
        doc = docx.Document(file)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
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

def rank_resumes_with_ai(job_description, resumes, file_names, progress_bar, status_text):
    """Ranks resumes using the Groq AI model based on their match to the job description."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    
    # Defaults for fallback
    fallback_recommendations = [{"recommendation": "N/A", "reason": "AI Scoring disabled", "missing_skills": []} for _ in resumes]
    
    if not api_key:
        st.warning("⚠ Groq API key is missing from environment. Falling back to keyword matching.")
        return rank_resumes(job_description, resumes), fallback_recommendations
        
    if groq is None:
        st.warning("⚠ Groq library is not installed. Please run pip install -r requirements.txt. Falling back to keyword matching.")
        return rank_resumes(job_description, resumes), fallback_recommendations
    
    try:
        client = groq.Groq(api_key=api_key)
    except Exception as e:
        st.error(f"Failed to initialize Groq client: {e}")
        return rank_resumes(job_description, resumes), fallback_recommendations

    scores = []
    ai_insights = []
    total_files = len(resumes)
    
    for i, (resume, name) in enumerate(zip(resumes, file_names)):
        status_text.text(f"AI Scoring {name} ({i+1}/{total_files})...")
        resume_snippet = resume[:3000] 
        prompt = f"""You are an expert technical recruiter. Compare the candidate's resume to the job description.
Provide the following in valid JSON format:
{{
  "score": integer (0-100),
  "missing_skills": ["skill1", "skill2", ...],
  "recommendation": "Hire" | "Maybe" | "Reject",
  "reason": "1-sentence summary for HR why this decision was made"
}}
Return ONLY the JSON.

Job Description:
{job_description}

Resume:
{resume_snippet}
"""
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            import json
            data = json.loads(completion.choices[0].message.content)
            score_val = float(data.get("score", 0)) / 100.0
            score_val = max(0.0, min(1.0, score_val))
            scores.append(score_val)
            ai_insights.append({
                "missing_skills": data.get("missing_skills", []),
                "recommendation": data.get("recommendation", "Maybe"),
                "reason": data.get("reason", "N/A")
            })
        except Exception as e:
            st.error(f"Groq API Error for {name}: {e}")
            scores.append(0.0)
            ai_insights.append({"missing_skills": [], "recommendation": "Error", "reason": str(e)})
            
        progress_bar.progress((i + 1) / total_files)
            
    if not scores or sum(scores) == 0.0:
        st.warning("⚠ AI Scoring failed for all resumes. Falling back to keyword matching.")
        return rank_resumes(job_description, resumes), fallback_recommendations
        
    return scores, ai_insights

JOB_ROLE_KEYWORDS = {
    "Software Engineer": "btech b.tech computer science bsc it masters mca python java c++ programming coding software development algorithms data structures backend frontend fullstack web developer react nodejs sql database",
    "Data Scientist": "phd masters statistics mathematics btech computer science machine learning python r sql data analysis pandas scikit-learn deep learning tensorflow artificial intelligence nlp computer vision",
    "Product Manager": "mba bba business administration management product strategy roadmap agile scrum leadership market research user experience stakeholder management product lifecycle jira communication",
    "Trainee Engineer": "btech b.tech fresher intern recent graduate basic programming engineering concepts eager to learn basic python c java academic projects",
    "HR Manager": "mba hr human resources management recruitment employee relations talent acquisition payroll onboarding interviewing performance management culture",
    "Marketing Executive": "mba marketing bba mass communication digital marketing seo sem social media content creation campaign management google analytics branding email marketing copywriting",
    "Sales Manager": "mba bba business sales b2b lead generation CRM negotiation communication account management revenue growth closing deals business development",
    "UX/UI Designer": "bdes design fine arts human computer interaction figma adobe xd wireframing prototyping user research visual design interaction design user interface user experience sketch",
    "DevOps Engineer": "btech computer science aws azure docker kubernetes ci cd pipeline linux sysadmin infrastructure as code terraform jenkins git cloud",
}

def extract_skills_and_education(text):
    """Attempts to extract both skills and education sections from resume text."""
    lines = text.split('\n')
    extracted_text = []
    in_relevant_section = False
    
    target_headers = ['skills', 'technical skills', 'core competencies', 'skills & expertise', 'technologies', 'technical expertise', 'education', 'academic background', 'qualifications', 'academic qualifications', 'educational background']
    other_headers = ['experience', 'projects', 'certifications', 'summary', 'profile', 'work history', 'employment history', 'languages', 'interests', 'achievements', 'awards', 'objective', 'activities', 'professional experience']
    
    for line in lines:
        line_clean = line.strip().lower()
        if not line_clean:
            continue
            
        header_candidate = line_clean.strip(':').strip()
        
        # Check if entering a relevant section
        if header_candidate in target_headers or any(line_clean.startswith(th + ':') for th in target_headers):
            in_relevant_section = True
            parts = line.split(':', 1)
            if len(parts) > 1 and parts[1].strip():
                extracted_text.append(parts[1].strip())
            continue
            
        # Check if exiting a relevant section
        if in_relevant_section:
            if len(line_clean.split()) <= 4 and header_candidate in other_headers:
                in_relevant_section = False
                continue
            extracted_text.append(line)
            
    extracted = ' '.join(extracted_text).strip()
    return extracted if extracted else text

def suggest_job_role(resume_text):
    """Suggests a suitable job role based on resume's skills and education sections."""
    skills_text = extract_skills_and_education(resume_text)
    
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    
    if api_key and groq is not None:
        try:
            client = groq.Groq(api_key=api_key)
            prompt = f"Analyze the following skills and education extracted from a resume. Suggest the single most appropriate standard job title (e.g., Software Engineer, Data Scientist, Product Manager, etc.). Return ONLY the exact job title and nothing else.\n\nResume data:\n{skills_text}"
            
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            # Optionally show an error, then fall back
            pass
            
    roles = list(JOB_ROLE_KEYWORDS.keys())
    descriptions = list(JOB_ROLE_KEYWORDS.values())
    
    try:
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform([skills_text] + descriptions)
        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()
        
        best_match_idx = similarities.argmax()
        best_score = similarities[best_match_idx]
        
        if best_score > 0.05:
            return roles[best_match_idx]
        return "General / Other"
    except Exception:
        return "General / Other"

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
        
        job_titles = [
            "Trainee Engineer", "Software Engineer", "Data Scientist", "Product Manager", 
            "HR Manager", "Marketing Executive", "Sales Manager", "UX/UI Designer", "Other"
        ]
        current_title = profile["job_title"] if profile["job_title"] else "Other"
        if current_title not in job_titles:
            job_titles.append(current_title)
            
        job_title = st.selectbox("Job Title", options=job_titles, index=job_titles.index(current_title))
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
        
        job_titles = [
            "Trainee Engineer", "Software Engineer", "Data Scientist", "Product Manager", 
            "HR Manager", "Marketing Executive", "Sales Manager", "UX/UI Designer", "Other"
        ]
        job_title = st.selectbox("Job Title", options=job_titles, label_visibility="visible")

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
            "Select PDF or DOCX resumes",
            type=["pdf", "docx"],
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
                
                if file.name.lower().endswith('.pdf'):
                    text = extract_text_from_pdf(file)
                elif file.name.lower().endswith('.docx'):
                    text = extract_text_from_docx(file)
                else:
                    text = "Error extracting text: Unsupported format"
                    
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
                progress_bar = st.progress(0)
                status_text = st.empty()
                status_text.text("Connecting to AI Scoring Engine...")
                scores, ai_insights_list = rank_resumes_with_ai(job_description, resumes, file_names, progress_bar, status_text)
                status_text.empty()
                progress_bar.empty()
                
                # Create a lookup for AI insights
                insights_map = {name: insight for name, insight in zip(file_names, ai_insights_list)}
                
                ranked_resumes = sorted(zip(file_names, scores), key=lambda x: x[1], reverse=True)
                
                # Create results dataframe
                suggested_roles = [suggest_job_role(resumes[file_names.index(name)]) for name, _ in ranked_resumes]
                missing_skills_for_df = [insights_map.get(name, {}).get("missing_skills", []) for name, _ in ranked_resumes]
                recommendations = [insights_map.get(name, {}).get("recommendation", "Maybe") for name, _ in ranked_resumes]
                reasons = [insights_map.get(name, {}).get("reason", "N/A") for name, _ in ranked_resumes]
                
                results_df = pd.DataFrame({
                    "Rank": range(1, len(ranked_resumes) + 1),
                    "Resume Name": [name for name, _ in ranked_resumes],
                    "Match Score": [score for _, score in ranked_resumes],
                    "Suggested Role": suggested_roles,
                    "Recommendation": recommendations,
                    "Reason": reasons,
                    "Missing Skills": missing_skills_for_df,
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
                            st.markdown(f"<p style='text-align: center; color: #1fc7d4; font-weight: bold;'>💡 Suggested Role: {row['Suggested Role']}</p>", unsafe_allow_html=True)
                            
                            # Recommendation Badge
                            rec_color = "#4CAF50" if row['Recommendation'] == "Hire" else "#FFC107" if row['Recommendation'] == "Maybe" else "#F44336"
                            st.markdown(f"""
                                <div style='background-color: {rec_color}; color: white; padding: 5px 10px; border-radius: 15px; text-align: center; font-weight: bold; margin-bottom: 10px;'>
                                    Decision: {row['Recommendation']}
                                </div>
                            """, unsafe_allow_html=True)
                            st.info(f"📝 {row['Reason']}")

                            with st.expander("🧠 Why this score?"):
                                resume_text = resumes[file_names.index(row['Resume Name'])].lower()
                                jd_words = set(re.findall(r'\b[a-z]{5,}\b', job_description.lower()))
                                jd_words = jd_words - ENGLISH_STOP_WORDS
                                
                                matched = [w for w in jd_words if w in resume_text]
                                missing = [w for w in jd_words if w not in resume_text]
                                
                                if matched:
                                    st.markdown("**Matched Keywords:**")
                                    st.markdown(" ".join([f"`{w}`" for w in matched[:12]]))
                                else:
                                    st.markdown("*Matched general semantics.*")
                                    
                                if missing:
                                    st.markdown("**Missing Keywords:**")
                                    st.markdown(" ".join([f"`{w}`" for w in missing[:12]]))
                                
                                ai_missing = row.get('Missing Skills', [])
                                if ai_missing:
                                    st.markdown("**🚀 AI Recommended Skills (to reach 100%):**")
                                    st.markdown(" ".join([f"`{s}`" for s in ai_missing]))
                
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

    # Professional Sidebar Branding
    st.sidebar.markdown(f"""
        <div style="text-align: center; padding: 20px 0;">
            <h1 style="color: #1fc7d4; font-size: 32px; font-weight: 800; margin-bottom: 0;">HireSense AI</h1>
            <p style="color: #64748b; font-size: 14px; letter-spacing: 1px; text-transform: uppercase;">Next-Gen Recruitment</p>
        </div>
    """, unsafe_allow_html=True)

    if st.session_state["authenticated"]:
        # User Context Card
        st.sidebar.markdown(f"""
            <div style="background-color: #f8fafc; border-radius: 12px; padding: 15px; border: 1px solid #e2e8f0; margin-bottom: 20px;">
                <p style="margin: 0; color: #64748b; font-size: 12px; font-weight: 600; text-transform: uppercase;">Active Recruiter</p>
                <p style="margin: 0; color: #0f172a; font-size: 14px; font-weight: 700; overflow: hidden; text-overflow: ellipsis;">{st.session_state['user_email']}</p>
            </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        st.sidebar.markdown("---")
        with st.sidebar:
            selected = option_menu(
                menu_title=None,
                options=["Dashboard", "My Profile", "Logout"],
                icons=["grid-1x2-fill", "person-badge-fill", "door-open-fill"],
                menu_icon="cast",
                default_index=0 if st.session_state["current_page"] == "dashboard" else 1,
                styles={
                    "container": {"padding": "0!important", "background-color": "transparent"},
                    "icon": {"color": "#64748b", "font-size": "18px"}, 
                    "nav-link": {
                        "font-size": "16px", 
                        "text-align": "left", 
                        "margin": "5px 0", 
                        "font-weight": "500",
                        "color": "#475569",
                        "--hover-color": "#f1f5f9"
                    },
                    "nav-link-selected": {"background-color": "#1fc7d4", "color": "white"},
                }
            )
            
            # System Status
            st.sidebar.markdown("---")
            api_key = os.getenv("GROQ_API_KEY", "").strip()
            engine_status = "Online" if api_key else "Offline (Keyword Mode)"
            status_color = "#10b981" if api_key else "#f59e0b"
            
            st.sidebar.markdown(f"""
                <div style="padding: 10px;">
                    <p style="margin: 0; color: #64748b; font-size: 12px; font-weight: 600; text-transform: uppercase;">AI Engine Status</p>
                    <div style="display: flex; align-items: center; gap: 8px; margin-top: 5px;">
                        <div style="width: 10px; height: 10px; background-color: {status_color}; border-radius: 50%;"></div>
                        <p style="margin: 0; color: #0f172a; font-size: 14px; font-weight: 600;">{engine_status}</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            st.sidebar.markdown(f"""
                <div style="margin-top: 50px; text-align: center; color: #94a3b8; font-size: 12px;">
                    <p>© 2024 HireSense AI<br>v2.1.0-AI</p>
                </div>
            """, unsafe_allow_html=True)
            
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