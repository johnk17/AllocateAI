"""Evidence-first catalog matching. Related skills never count as exact matches."""

import re
from sqlalchemy import select
from .db import Skill

DOMAINS = {
    "Programming": "Python|Java|C|C++|C#|Go|Rust|Kotlin|Swift|JavaScript|TypeScript|PHP|R|MATLAB|Bash|PowerShell|SQL|OOP|Data Structures|Algorithms",
    "Frontend and design": "HTML|CSS|React|Next.js|Angular|Vue|Svelte|Tailwind CSS|Bootstrap|Redux|Figma|Accessibility|Responsive Design",
    "Backend": "Spring Boot|Spring Security|Hibernate|Django|FastAPI|Flask|Node.js|Express|NestJS|ASP.NET Core|Laravel|REST|GraphQL|gRPC|Microservices",
    "Databases": "PostgreSQL|MySQL|SQL Server|Oracle Database|SQLite|MongoDB|Redis|DynamoDB|Elasticsearch|OpenSearch|pgvector|Qdrant|Neo4j",
    "AI and ML": "NumPy|pandas|SciPy|scikit-learn|PyTorch|TensorFlow|Keras|XGBoost|OpenCV|YOLO|OCR|Time-Series Forecasting|Classification|Regression",
    "LLMs and agents": "Prompt Engineering|Structured Outputs|Function Calling|Embeddings|RAG|Reranking|LangChain|LangGraph|LlamaIndex|Hugging Face Transformers|Sentence Transformers|Ollama|MCP|LoRA|PEFT|LLM Evaluation|Tracing|Human-in-the-loop",
    "Data and analytics": "Apache Spark|Kafka|Airflow|dbt|Databricks|Snowflake|BigQuery|ETL|ELT|Data Warehousing|Excel|Power BI|Tableau",
    "Cloud and DevOps": "AWS|Azure|Google Cloud|Linux|Git|Docker|Kubernetes|Helm|Terraform|Ansible|Jenkins|GitHub Actions|GitLab CI|Prometheus|Grafana|OpenTelemetry|MLflow",
    "Testing and security": "pytest|JUnit|Mockito|Selenium|Playwright|Cypress|Postman|API Testing|TCP/IP|DNS|HTTP|TLS|IAM|OAuth 2.0|OpenID Connect|Secure Coding|Vulnerability Management",
    "Mobile and embedded": "Android|Jetpack Compose|SwiftUI|Flutter|React Native|Arduino|ESP32|Raspberry Pi|STM32|FreeRTOS|MQTT|UART|I2C|SPI|CAN bus",
    "Engineering": "AutoCAD|SolidWorks|CATIA|Fusion 360|ANSYS|MATLAB Simulink|PLC|SCADA|Siemens TIA Portal|CNC|GD&T|PCB Design|KiCad|VHDL|Verilog|FPGA|ROS 2",
    "Business and operations": "Jira|Confluence|Scrum|Kanban|SAP|Salesforce|ERP|CRM|Supply Chain Analytics|Excel Power Query|Excel VBA|Financial Modeling",
}
ALIASES = {
    "PostgreSQL": ["Postgres"],
    "Kubernetes": ["k8s"],
    "JavaScript": ["JS"],
    "TypeScript": ["TS"],
    "React": ["React.js", "ReactJS"],
    "Node.js": ["NodeJS"],
    "Next.js": ["NextJS"],
    "C++": ["CPP"],
    "C#": ["CSharp"],
    "scikit-learn": ["sklearn"],
    "I2C": ["I²C"],
}


def install_curated(db):
    """Real technology names, explicitly project-curated, not claimed to be ESCO/O*NET."""
    if db.scalar(select(Skill.id).limit(1)):
        return
    for category, names in DOMAINS.items():
        for name in names.split("|"):
            db.add(
                Skill(
                    canonical_id="curated:" + name.lower(),
                    name=name,
                    aliases=ALIASES.get(name, []),
                    category=category,
                    source="AllocateAI project-curated technology names; pending admin review",
                    source_version="2026-11-17",
                    related=[],
                    reviewed=False,
                )
            )


def pattern(term):
    # Prevent C matching C++/C#, Java matching JavaScript, React matching React Native.
    tail = r"(?![\w+#])"
    if term.lower() == "react":
        tail = r"(?![\w+#]|\s+native\b)"
    return re.compile(r"(?<![\w+#])" + re.escape(term) + tail, re.I)


def match_skills(text, skills):
    hits = []
    for skill in skills:
        terms = [skill.name, *skill.aliases]
        found = next((m for term in terms if (m := pattern(term).search(text))), None)
        if not found:
            continue
        if skill.name in ("Go", "R", "Spring") and not re.search(
            r"program|language|develop|code|golang|rstats|framework|spring boot|r studio",
            text,
            re.I,
        ):
            continue
        start = max(text.rfind("\n", 0, found.start()) + 1, 0)
        end = text.find("\n", found.end())
        excerpt = text[start : end if end != -1 else len(text)].strip()[:2000]
        context = (
            "project"
            if re.search(r"project|built|developed|implemented", excerpt, re.I)
            else "skills_section"
            if re.search(r"skills|technologies|tools", excerpt, re.I)
            else "mentioned"
        )
        hits.append(
            {
                "skill_id": skill.id,
                "value": skill.name,
                "excerpt": excerpt,
                "context": context,
            }
        )
    return hits


def exact_skill(name, skills):
    matches = [
        s
        for s in skills
        if name.casefold() in [s.name.casefold(), *[a.casefold() for a in s.aliases]]
    ]
    return matches[0] if len(matches) == 1 else None


def claim_supported(kind, value, excerpt, skill=None):
    if kind == "skill":
        if re.search(
            r"\b(no experience|not experienced|never used|do not know|without knowledge|want to learn|planning to learn)\b",
            excerpt,
            re.I,
        ):
            return False
        return bool(skill and match_skills(excerpt, [skill]))
    if kind == "qualification":
        if value.strip().casefold() == "noc":
            return bool(re.search(r"\bnoc\b|no objection certificate", excerpt, re.I)
                        and re.search(r"issued|approved|signed|confirmed|obtained", excerpt, re.I)
                        and not re.search(r"not issued|unconfirmed|pending|missing|not obtained", excerpt, re.I))
        if value.casefold() not in excerpt.casefold():
            return False
        if re.search(
            r"collaborat|\bteam\b|pursuing|enrolled|aspir|do not hold|not completed|not graduated|without a|no degree|no certificate",
            excerpt,
            re.I,
        ):
            return False
        return bool(
            re.search(
                r"completed|graduated|degree|diploma|certificat|bachelor|master|b\.?tech|b\.?sc|b\.?com|education",
                excerpt,
                re.I,
            )
        )
    if kind == "participation":
        if value.casefold() == "yes":
            return bool(re.search(r"previously participated|prior participation confirmed", excerpt, re.I))
        if value.casefold() == "no":
            return bool(re.search(r"no prior participation|did not previously participate", excerpt, re.I))
        return False
    return value.casefold() in excerpt.casefold()
