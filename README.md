# 📋 Integrated Institution Complaint Monitoring Dashboard

**SIH26264** — Track, coordinate, and detect related complaints across bureaus.

## What This Does

Officials across different bureaus and cells receive complaints about
educational institutions. This dashboard helps them:

- **Register and track** complaints with full action history.
- **Detect related complaints** — same institution, similar issues, or both —
  with transparent evidence so humans make the final call.
- **Coordinate across bureaus** by surfacing potential overlaps before they
  become duplicates or contradictions.

The system **never** automatically merges complaints, determines guilt, or
makes official decisions.

---

## Tech Stack

| Layer         | Tool             |
|---------------|------------------|
| Interface     | Streamlit        |
| Database      | SQLite (local)   |
| Data handling | pandas           |
| Text analysis | scikit-learn     |
| Testing       | pytest           |

No cloud services, no paid APIs, no separate backend server.

---

## Setup (Windows)

### Prerequisites

- **Python 3.10+** installed and available on PATH.
  Verify: `python --version`

### Step-by-step

```powershell
# 1. Open a terminal in the project folder
cd E:\Projects\SIH26264

# 2. Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run tests to verify everything works
python -m pytest tests/ -v

# 5. Load synthetic demo data (also auto-loads on first launch if empty)
python -m src.seed_data

# 6. Launch the dashboard
streamlit run app.py
```

The app opens in your browser at **http://localhost:8501**.

### Quick launch (after initial setup)

```powershell
cd E:\Projects\SIH26264
.venv\Scripts\activate
streamlit run app.py
```

---

## Project Structure

```
SIH26264/
├── app.py                  # Streamlit entry point (thin — delegates to src/)
├── requirements.txt        # Python dependencies
├── README.md               # You are here
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── database.py         # SQLite schema, connection helper, health check
│   ├── relationship_detection.py # Explainable, deterministic relationship detection
│   └── seed_data.py        # Synthetic dataset (institutions, complaints, actions)
├── tests/
│   ├── __init__.py
│   ├── test_database.py    # Verifies DB initialisation and health check
│   ├── test_relationship_detection.py # Verifies matching heuristics and scenarios
│   └── test_seed_data.py   # Verifies seed data, idempotency, test scenarios
└── data/                   # Created at runtime — holds complaints.db
```

---

## Loading Synthetic Data

The project includes ~30 fictional complaints across 10 institutions and 6
bureaus for development and demonstration.  All records are clearly synthetic
(reference numbers start with `SEED-`).

```powershell
# Load synthetic data into the database
python -m src.seed_data

# Safe to run multiple times — will not duplicate records
python -m src.seed_data
```

The seed module includes deliberate test scenarios for relationship detection:

| Scenario | What it tests | Reference numbers |
|----------|---------------|-------------------|
| A | Same institution, same fee issue, different bureaus | SEED-C-001, SEED-C-002 |
| B | Same institution, unrelated issues | SEED-C-001, SEED-C-003 |
| C | Similar text, different institutions | SEED-C-010, SEED-C-011 |
| D | Similar issue, weak linking evidence | SEED-C-020, SEED-C-021 |
| E | Varied statuses and aging cases | SEED-C-030, SEED-C-031, SEED-C-032 |

---

## Running Tests

```powershell
python -m pytest tests/ -v
```

Tests use temporary databases and never touch `data/complaints.db`.


---

## Current Status

- [x] Project scaffold and dependencies
- [x] SQLite database schema (institutions, complaints, action history, relationships)
- [x] Database health check
- [x] Streamlit app with government-oriented light theme
- [x] Automated test suite (42 tests passing)
- [x] Complaint monitoring & KPI metrics (unresolved, resolved, escalated, ageing)
- [x] Complaint browser with search, multi-filter, and action-history timeline
- [x] Explainable relationship detection (two-stage: institution resolution + text similarity)
- [x] Potential match inspection with side-by-side evidence review
- [x] Synthetic demonstration dataset with documented test scenarios

---

## License

Hackathon prototype — SIH 2026.
