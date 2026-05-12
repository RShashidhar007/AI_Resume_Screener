# 🤖 HireSense AI – Next-Gen Resume Screening & Ranking System

**HireSense AI** is a professional-grade recruitment platform that leverages **Llama 3.1 LLMs** and **NLP** to automatically screen, evaluate, and rank resumes with human-like intelligence. It transforms the hiring process from manual keyword searching into data-driven talent acquisition.

## 📌 Overview
Traditional recruitment tools rely on rigid keyword matching. **HireSense AI** goes beyond that by using advanced Large Language Models (via Groq API) to understand the context, experience, and potential of every candidate, providing recruiters with instant, actionable insights.

## 🚀 Key Features
- **🧠 AI-Powered Scoring** – Uses Llama 3.1 to intelligently score resumes (0-100%) based on context, not just keywords.
- **✅ Automated Hiring Decisions** – Get instant "Hire," "Maybe," or "Reject" recommendations for every candidate.
- **🚀 Gap Analysis** – Automatically identifies missing technical skills needed for a 100% match to the job role.
- **📄 Multi-Format Support** – Seamlessly parses and analyzes both **PDF** and **DOCX** resumes.
- **📊 Interactive Dashboard** – Beautiful visualizations of candidate distributions and ranking history.
- **💼 Professional HR Reports** – Export ranked results and AI insights directly to **CSV** or **Excel**.
- **🔒 Enterprise Security** – Secure API management via environment variables (`.env`).

## 🛠️ Technology Stack
- **Frontend**: Streamlit (Modern Python Web Framework)
- **AI Engine**: Groq API (Llama 3.1-8B-Instant)
- **NLP**: Scikit-learn (Fallback matching & TF-IDF)
- **Database**: SQLite (Ranking history and user profiles)
- **Parsing**: PyPDF, Python-Docx
- **Visualization**: Plotly Express

## 📂 How It Works
1. **Configure API**: Set up your Groq API key in the `.env` file.
2. **Upload Resumes**: Drop PDF or DOCX files into the dashboard.
3. **Job Input**: Select a job title from the professional dropdowns and provide a job description.
4. **AI Processing**: The system extracts education/skills and uses the LLM to score and recommend candidates.
5. **Review & Decide**: Use the "Why this score?" insights to make fast, informed hiring decisions.

## 📦 Installation & Setup

### 🔹 Prerequisites
- Python 3.9+
- Groq API Key (get one at [console.groq.com](https://console.groq.com/))

### 🔹 Steps
1. **Clone the Repository**
   ```bash
   git clone https://github.com/RShashidhar007/hiresence_AI.git
   cd hiresence_AI
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create a `.env` file in the root directory and add your key:
   ```env
   GROQ_API_KEY=your_gsk_api_key_here
   ```

4. **Run the Application**
   ```bash
   streamlit run app.py
   ```

---
*Empowering HR teams with AI-driven intelligence.*
