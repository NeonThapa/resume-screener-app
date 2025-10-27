# skills.py
# This is our central "knowledge base" for all skills and their variations.

# The "key" is the official skill name.
# The "value" is a list of all possible ways it might be written (case-insensitivity is handled separately).

MASTER_SKILL_LIST = {
    # --- Technical / IT Skills ---
    "Python": ["Python", "py"],
    "SQL": ["SQL", "PostgreSQL", "MySQL", "MSSQL"],
    "AWS": ["AWS", "Amazon Web Services"],
    "Azure": ["Azure", "Microsoft Azure"],
    "GCP": ["GCP", "Google Cloud Platform"],
    "JavaScript": ["JavaScript", "JS"],
    "React": ["React", "React.js"],
    "Node.js": ["Node.js", "NodeJS"],
    "Django": ["Django"],
    "Flask": ["Flask"],
    "Redis": ["Redis"],
    "Jenkins": ["Jenkins"],
    "Git": ["Git", "GitHub", "GitLab"],
    "Docker": ["Docker"],
    "Kubernetes": ["Kubernetes", "K8s"],
    "RESTful APIs": ["RESTful APIs", "REST API", "REST"],
    "CI/CD": ["CI/CD", "Continuous Integration", "Continuous Deployment"],
    "TensorFlow": ["TensorFlow", "TF"],
    "PyTorch": ["PyTorch"],
    "Scikit-learn": ["Scikit-learn", "sklearn"],
    "Pandas": ["Pandas"],
    "NumPy": ["NumPy"],
    "Tableau": ["Tableau"],
    "PowerBI": ["Power BI", "PowerBI"],
    "Artificial Intelligence": ["Artificial Intelligence", "AI"],
    "Machine Learning": ["Machine Learning", "ML"],

    # --- HR Skills (Example of how to expand) ---
    "Recruitment": ["Recruitment", "Recruiting", "Talent Acquisition"],
    "Onboarding": ["Onboarding", "Employee Onboarding"],
    "HRIS": ["HRIS", "Human Resources Information System"],
    "Performance Management": ["Performance Management"],
    "Compensation & Benefits": ["Compensation & Benefits", "Comp & Ben"],

    # --- Add more categories and skills as needed ---
    "Agile Methodology": ["Agile", "Agile Methodology"],
    "Scrum": ["Scrum", "Scrum Master"],
    "Kanban": ["Kanban"],
    "Waterfall Methodology": ["Waterfall", "Waterfall Methodology"],
    "PMP": ["PMP", "Project Management Professional"],
    "PRINCE2": ["PRINCE2"],
    "JIRA": ["JIRA", "Atlassian JIRA"],
    "Confluence": ["Confluence"],
    "Trello": ["Trello"],
    "Asana": ["Asana"],
    "Microsoft Project": ["Microsoft Project", "MS Project"],
    "Risk Management": ["Risk Management", "Risk Mitigation"],
    "Stakeholder Management": ["Stakeholder Management", "Stakeholder Communication"],
    "Budget Management": ["Budget Management", "Budgeting", "Financial Planning"],
    "Scope Management": ["Scope Management", "Scope Creep"],
    "Resource Allocation": ["Resource Allocation", "Resource Management"],
    "Gantt Charts": ["Gantt Charts", "Gantt"],
    "SDLC": ["SDLC", "Software Development Life Cycle"],
    "Change Management": ["Change Management", "Change Control"],
    "ITIL": ["ITIL", "Information Technology Infrastructure Library"],
    "SLA Management": ["SLA Management", "Service Level Agreement"],

    # --- Core Soft Skills for Management ---
    "Leadership": ["Leadership", "Team Leadership"],
    "Communication": ["Communication", "Verbal Communication", "Written Communication"],
    "Negotiation": ["Negotiation"],
    "Problem Solving": ["Problem Solving", "Analytical Skills"],
    "Decision Making": ["Decision Making"],

    # --- Role-Specific Skills ---
    "Sr. Full Stack Developer": [
        "Full Stack Development", "Front-End", "Back-End", "HTML", "CSS", "JavaScript",
        "TypeScript", "React", "Angular", "Vue.js", "Node.js", "Express.js",
        "REST APIs", "GraphQL", "Docker", "Kubernetes", "CI/CD", "Unit Testing",
        "Jest", "Mocha", "Webpack", "Babel", "Microservices"
    ],
    "Manager Lead - Finance": [
        "Manager Lead - Finance", "Manager Lead – Finance", "Lead - Finance", "Lead – Finance",
        "Financial Reporting", "Budget Management", "Forecasting", "Financial Analysis",
        "Variance Analysis", "Cost Accounting", "SAP FI", "Oracle Financials",
        "Excel", "Power BI", "Financial Modeling", "Risk Management",
        "Regulatory Compliance", "GAAP", "IFRS", "Stakeholder Management"
    ],
}
