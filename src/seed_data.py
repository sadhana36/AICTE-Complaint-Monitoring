"""
seed_data.py — Populate the database with synthetic institutions, complaints,
and action-history records for development and demonstration.

Design notes:
- All synthetic records use stable identifiers (SEED-xxx reference numbers,
  SEED-INST-xxx identifier codes) so that repeated seeding is idempotent.
- INSERT OR IGNORE on unique columns prevents duplication.
- Records are entirely fictional — no real institution data.
- Deliberate test scenarios (A–E) are documented inline and use predictable
  reference numbers so automated tests can locate them.

Usage:
    python -m src.seed_data          # from project root
    python -m src.seed_data path.db  # override database path
"""

from __future__ import annotations

import sys
from pathlib import Path
from src.database import init_db, get_connection

# ═══════════════════════════════════════════════════════════════════════════
# INSTITUTIONS — 10 fictional educational institutions
# ═══════════════════════════════════════════════════════════════════════════
# Each tuple: (identifier_code, name, name_normalized, institution_type, city, state)

INSTITUTIONS = [
    ("SEED-INST-001", "Lakshmi Narasimha Institute of Technology",
     "lakshmi narasimha institute of technology", "Engineering College",
     "Vijayawada", "Andhra Pradesh"),

    ("SEED-INST-002", "L.N. Institute of Tech.",                        # abbreviation of INST-001
     "ln institute of tech", "Engineering College",
     "Vijayawada", "Andhra Pradesh"),
    # NOTE: INST-001 and INST-002 are intentionally the *same* real institution
    # entered with different name formatting.  The relationship-detection engine
    # should eventually resolve them.  For seeding purposes they are stored as
    # separate rows so we can test institution resolution.

    ("SEED-INST-003", "Bharathi Vidyapeeth College of Engineering",
     "bharathi vidyapeeth college of engineering", "Engineering College",
     "Pune", "Maharashtra"),

    ("SEED-INST-004", "Sunrise School of Management & Technology",
     "sunrise school of management and technology", "Management College",
     "Jaipur", "Rajasthan"),

    ("SEED-INST-005", "Greenfield Polytechnic",
     "greenfield polytechnic", "Polytechnic",
     "Coimbatore", "Tamil Nadu"),

    ("SEED-INST-006", "Kalpana Chawla Women's Engineering College",
     "kalpana chawla womens engineering college", "Engineering College",
     "Lucknow", "Uttar Pradesh"),

    ("SEED-INST-007", "Saraswati National University",
     "saraswati national university", "University",
     "Bhopal", "Madhya Pradesh"),

    ("SEED-INST-008", "Pinnacle Institute of Pharmacy",
     "pinnacle institute of pharmacy", "Pharmacy College",
     "Hyderabad", "Telangana"),

    ("SEED-INST-009", "Eastbridge Technical College",
     "eastbridge technical college", "Engineering College",
     "Kolkata", "West Bengal"),

    ("SEED-INST-010", "Heritage Academy of Architecture",
     "heritage academy of architecture", "Architecture College",
     "Ahmedabad", "Gujarat"),
]

# ═══════════════════════════════════════════════════════════════════════════
# BUREAUS — realistic cell / bureau names
# ═══════════════════════════════════════════════════════════════════════════

BUREAUS = [
    "PGRC",                     # Public Grievance Redressal Cell
    "Regulation Bureau",
    "Approval Bureau",
    "Academic Bureau",
    "Finance Bureau",
    "Administration Bureau",
]

# ═══════════════════════════════════════════════════════════════════════════
# COMPLAINTS
# ═══════════════════════════════════════════════════════════════════════════
# Each dict maps directly to columns in the complaints table.
# institution_code is resolved to institution_id at insert time.
#
# ---- Test Scenario Key ----
# A  : Same institution, same fee issue, different bureaus & wording
#      → SEED-C-001, SEED-C-002
# B  : Same institution, clearly unrelated issues (fee vs hostel water)
#      → SEED-C-001, SEED-C-003
# C  : Textually similar descriptions but different institutions
#      → SEED-C-010, SEED-C-011
# D  : Similar issues but weak evidence to link
#      → SEED-C-020, SEED-C-021
# E  : Varied statuses and action histories (aging / pending)
#      → SEED-C-030, SEED-C-031, SEED-C-032

COMPLAINTS = [
    # ── Scenario A: same institution + same fee issue, different bureau/wording ──
    {
        "reference_number": "SEED-C-001",
        "institution_code": "SEED-INST-001",
        "institution_name_raw": "Lakshmi Narasimha Institute of Technology",
        "complainant_name": "Ramesh Kumar",
        "complaint_text": (
            "The institute is charging excess tuition fees beyond the amount "
            "approved by the fee fixation committee.  Students in the B.Tech "
            "CSE programme are being asked to pay Rs 1,50,000 per annum instead "
            "of the approved Rs 95,000.  Multiple students have raised this "
            "issue with the college administration but no corrective action has "
            "been taken."
        ),
        "category": "Fee Irregularity",
        "bureau": "PGRC",
        "status": "Open",
        "priority": "High",
        "date_received": "2026-06-10",
    },
    {
        "reference_number": "SEED-C-002",
        "institution_code": "SEED-INST-002",   # same institution, abbreviated name
        "institution_name_raw": "L.N. Institute of Tech., Vijayawada",
        "complainant_name": "Sita Devi",
        "complaint_text": (
            "I am writing to complain about the unauthorised fee hike at LN "
            "Institute of Technology.  The college has increased the annual "
            "fee from the sanctioned ninety-five thousand to one lakh fifty "
            "thousand without proper approval.  This is causing severe "
            "financial hardship to students and their families.  Please "
            "investigate."
        ),
        "category": "Fee Overcharging",
        "bureau": "Regulation Bureau",
        "status": "Under Review",
        "priority": "High",
        "date_received": "2026-06-18",
    },

    # ── Scenario B: same institution, clearly UNRELATED issue (hostel water) ──
    {
        "reference_number": "SEED-C-003",
        "institution_code": "SEED-INST-001",
        "institution_name_raw": "Lakshmi Narasimha Institute of Technology, Vijayawada",
        "complainant_name": "Priya Sharma",
        "complaint_text": (
            "The hostel water supply at Lakshmi Narasimha Institute has been "
            "irregular for the past three months.  Residents of Hostel Block C "
            "receive water for only two hours per day, which is grossly "
            "insufficient.  The administration has not responded to repeated "
            "written complaints from the hostel warden."
        ),
        "category": "Infrastructure",
        "bureau": "PGRC",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-07-02",
    },

    # ── Scenario C: textually similar descriptions, DIFFERENT institutions ──
    {
        "reference_number": "SEED-C-010",
        "institution_code": "SEED-INST-003",
        "institution_name_raw": "Bharathi Vidyapeeth College of Engg, Pune",
        "complainant_name": "Anil Joshi",
        "complaint_text": (
            "The placement cell of the college is not functioning properly.  "
            "Final-year students have not received any placement assistance this "
            "academic year.  The college website claims a 90% placement rate but "
            "in reality fewer than 20 students out of 180 in the CS department "
            "have received offers."
        ),
        "category": "Placement Grievance",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-05-15",
    },
    {
        "reference_number": "SEED-C-011",
        "institution_code": "SEED-INST-009",
        "institution_name_raw": "East Bridge Technical College, Kolkata",
        "complainant_name": "Debashis Mitra",
        "complaint_text": (
            "The placement cell is completely non-functional.  Final-year "
            "students of the Computer Science department have received no "
            "placement support whatsoever.  The college brochure advertises "
            "a 95% placement record but fewer than 15 students out of 160 "
            "have received any offer this year."
        ),
        "category": "Placement Grievance",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-05-22",
    },

    # ── Scenario D: similar issues, insufficient evidence to confidently link ──
    {
        "reference_number": "SEED-C-020",
        "institution_code": "SEED-INST-004",
        "institution_name_raw": "Sunrise School of Mgmt & Tech",
        "complainant_name": "Kavita Mehra",
        "complaint_text": (
            "Some faculty members in the MBA programme do not meet the minimum "
            "qualification requirements.  At least three visiting faculty do "
            "not hold a postgraduate degree in their teaching subject."
        ),
        "category": "Faculty Qualification",
        "bureau": "Regulation Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-04-28",
    },
    {
        "reference_number": "SEED-C-021",
        "institution_code": "SEED-INST-007",
        "institution_name_raw": "Saraswati National Univ.",
        "complainant_name": "Vikram Singh",
        "complaint_text": (
            "Several lecturers in the management department appear to lack "
            "the required academic qualifications.  I believe at least two "
            "faculty members do not have a Master's degree in the relevant "
            "discipline."
        ),
        "category": "Faculty Qualification",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-05-05",
    },

    # ── Scenario E: varied statuses and action histories ──
    {
        "reference_number": "SEED-C-030",
        "institution_code": "SEED-INST-005",
        "institution_name_raw": "Green Field Polytechnic, Coimbatore",
        "complainant_name": "Muthu Lakshmi",
        "complaint_text": (
            "The polytechnic is running an unapproved diploma programme in "
            "Artificial Intelligence since July 2025.  No approval from the "
            "competent authority has been obtained."
        ),
        "category": "Unapproved Programme",
        "bureau": "Approval Bureau",
        "status": "Resolved",
        "priority": "High",
        "date_received": "2025-08-12",
        "date_closed": "2026-01-20",
    },
    {
        "reference_number": "SEED-C-031",
        "institution_code": "SEED-INST-006",
        "institution_name_raw": "Kalpana Chawla Womens Engg College",
        "complainant_name": "Neha Gupta",
        "complaint_text": (
            "The college library does not have sufficient books or journal "
            "subscriptions.  The NAAC peer team had recommended a minimum "
            "of 5,000 titles but the library currently holds fewer than 800."
        ),
        "category": "Infrastructure",
        "bureau": "PGRC",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-02-14",
    },
    {
        "reference_number": "SEED-C-032",
        "institution_code": "SEED-INST-008",
        "institution_name_raw": "Pinnacle Inst. of Pharmacy, Hyderabad",
        "complainant_name": "Rajesh Reddy",
        "complaint_text": (
            "The pharmacy college has not refunded the caution deposit of "
            "final-year students who graduated in May 2025.  Despite repeated "
            "requests over nine months, the college accounting office claims "
            "the refunds are 'under processing'."
        ),
        "category": "Fee Irregularity",
        "bureau": "Finance Bureau",
        "status": "Escalated",
        "priority": "High",
        "date_received": "2025-11-05",
    },

    # ── Additional complaints for volume and variety ──

    {
        "reference_number": "SEED-C-040",
        "institution_code": "SEED-INST-003",
        "institution_name_raw": "Bharathi Vidyapeeth College of Engineering",
        "complainant_name": "Sneha Patil",
        "complaint_text": (
            "The college is not providing the laboratory facilities promised "
            "in the prospectus.  The VLSI and Embedded Systems labs have no "
            "functional equipment."
        ),
        "category": "Infrastructure",
        "bureau": "Approval Bureau",
        "status": "Under Review",
        "priority": "Normal",
        "date_received": "2026-03-20",
    },
    {
        "reference_number": "SEED-C-041",
        "institution_code": "SEED-INST-004",
        "institution_name_raw": "Sunrise School of Management & Technology, Jaipur",
        "complainant_name": "Rohit Agarwal",
        "complaint_text": (
            "The institute is collecting a mandatory 'development fee' of "
            "Rs 25,000 that does not appear in the approved fee structure.  "
            "Students who refuse to pay are denied examination hall tickets."
        ),
        "category": "Fee Irregularity",
        "bureau": "PGRC",
        "status": "Open",
        "priority": "High",
        "date_received": "2026-07-11",
    },
    {
        "reference_number": "SEED-C-042",
        "institution_code": "SEED-INST-005",
        "institution_name_raw": "Greenfield Polytechnic",
        "complainant_name": "Karthik S",
        "complaint_text": (
            "The workshop instructor for the Mechanical Engineering diploma "
            "has been absent for over two months.  No substitute has been "
            "arranged, and students are losing practical training hours."
        ),
        "category": "Faculty Shortage",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-08-01",
    },
    {
        "reference_number": "SEED-C-043",
        "institution_code": "SEED-INST-006",
        "institution_name_raw": "K. C. Women's Engineering College, Lucknow",
        "complainant_name": "Aarti Verma",
        "complaint_text": (
            "There are serious safety concerns in the chemistry and chemical "
            "engineering laboratories.  Fire extinguishers are expired, and "
            "the fume hoods in Lab 3 and Lab 5 are non-operational."
        ),
        "category": "Safety",
        "bureau": "Regulation Bureau",
        "status": "Open",
        "priority": "High",
        "date_received": "2026-06-25",
    },
    {
        "reference_number": "SEED-C-044",
        "institution_code": "SEED-INST-007",
        "institution_name_raw": "Saraswati National University, Bhopal",
        "complainant_name": "Mohan Yadav",
        "complaint_text": (
            "The university has been awarding degrees for a B.Arch programme "
            "that does not appear in the list of approved programmes on the "
            "Council's website.  This raises questions about the validity of "
            "degrees awarded to approximately 120 students."
        ),
        "category": "Unapproved Programme",
        "bureau": "Approval Bureau",
        "status": "Open",
        "priority": "High",
        "date_received": "2026-04-10",
    },
    {
        "reference_number": "SEED-C-045",
        "institution_code": "SEED-INST-008",
        "institution_name_raw": "Pinnacle Inst of Pharmacy",
        "complainant_name": "Swathi Nair",
        "complaint_text": (
            "The college is admitting students to the D.Pharm programme in "
            "excess of the sanctioned intake.  Approved intake is 60, but "
            "approximately 85 students are enrolled in the current batch."
        ),
        "category": "Intake Violation",
        "bureau": "Regulation Bureau",
        "status": "Under Review",
        "priority": "Normal",
        "date_received": "2026-05-30",
    },
    {
        "reference_number": "SEED-C-046",
        "institution_code": "SEED-INST-009",
        "institution_name_raw": "Eastbridge Technical College",
        "complainant_name": "Sourav Banerjee",
        "complaint_text": (
            "The hostel fee has been increased by 40% with no prior notice "
            "and no improvement in facilities.  The hostel mess quality is "
            "extremely poor and students have fallen ill multiple times."
        ),
        "category": "Fee Irregularity",
        "bureau": "PGRC",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-07-20",
    },
    {
        "reference_number": "SEED-C-047",
        "institution_code": "SEED-INST-010",
        "institution_name_raw": "Heritage Academy of Architecture, Ahmedabad",
        "complainant_name": "Pallavi Shah",
        "complaint_text": (
            "The architecture college does not have a qualified structural "
            "engineering faculty member, which is a mandatory requirement for "
            "the B.Arch programme.  The subject is being taught by a civil "
            "engineering graduate without a Master's degree."
        ),
        "category": "Faculty Qualification",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-06-05",
    },
    {
        "reference_number": "SEED-C-048",
        "institution_code": "SEED-INST-010",
        "institution_name_raw": "Heritage Academy of Architecture",
        "complainant_name": "Chirag Patel",
        "complaint_text": (
            "The studio spaces allocated for final-year B.Arch students are "
            "inadequate.  Each student is supposed to have 3 sq.m of studio "
            "space per the norms, but the actual allocation is less than "
            "1.5 sq.m per student."
        ),
        "category": "Infrastructure",
        "bureau": "Regulation Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-08-12",
    },

    # Additional volume to reach ~35 complaints
    {
        "reference_number": "SEED-C-050",
        "institution_code": "SEED-INST-001",
        "institution_name_raw": "Lakshmi Narasimha Inst. of Technology",
        "complainant_name": "Suresh Babu",
        "complaint_text": (
            "The institute's anti-ragging committee is not functional.  "
            "First-year students have reported verbal harassment in hostels "
            "and no action has been taken despite written complaints."
        ),
        "category": "Ragging",
        "bureau": "Administration Bureau",
        "status": "Open",
        "priority": "High",
        "date_received": "2026-08-20",
    },
    {
        "reference_number": "SEED-C-051",
        "institution_code": "SEED-INST-003",
        "institution_name_raw": "B.V. College of Engg., Pune",
        "complainant_name": "Pooja Kulkarni",
        "complaint_text": (
            "The college has changed its internal assessment pattern mid-semester "
            "without informing students.  Weightage of assignments was increased "
            "from 20% to 40% after the first assessment was already graded."
        ),
        "category": "Academic Irregularity",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-09-01",
    },
    {
        "reference_number": "SEED-C-052",
        "institution_code": "SEED-INST-004",
        "institution_name_raw": "Sunrise Sch. of Mgmt & Tech, Jaipur",
        "complainant_name": "Deepak Sharma",
        "complaint_text": (
            "The college is not returning original documents of students who "
            "wish to withdraw their admission within the refund window.  "
            "Several students have been waiting for over 45 days."
        ),
        "category": "Admission Grievance",
        "bureau": "PGRC",
        "status": "Under Review",
        "priority": "Normal",
        "date_received": "2026-08-15",
    },
    {
        "reference_number": "SEED-C-053",
        "institution_code": "SEED-INST-005",
        "institution_name_raw": "Greenfield Polytechnic, Coimbatore",
        "complainant_name": "Revathi M",
        "complaint_text": (
            "The drinking water facility in the main campus building has been "
            "out of order for two weeks.  Students are forced to purchase "
            "bottled water from the canteen at inflated prices."
        ),
        "category": "Infrastructure",
        "bureau": "PGRC",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-09-10",
    },
    {
        "reference_number": "SEED-C-054",
        "institution_code": "SEED-INST-007",
        "institution_name_raw": "Saraswati Natl. University",
        "complainant_name": "Ankit Tiwari",
        "complaint_text": (
            "The university convocation for the 2024-25 batch has been "
            "indefinitely postponed.  Students who graduated in May 2025 "
            "have still not received their degree certificates and it is "
            "affecting their job applications."
        ),
        "category": "Academic Irregularity",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-09-18",
    },
    {
        "reference_number": "SEED-C-055",
        "institution_code": "SEED-INST-006",
        "institution_name_raw": "Kalpana Chawla Women's Engg. College",
        "complainant_name": "Ritu Singh",
        "complaint_text": (
            "The college transport service is unreliable and unsafe.  Buses "
            "are overcrowded, do not follow the published schedule, and at "
            "least two buses have no valid fitness certificate."
        ),
        "category": "Safety",
        "bureau": "Administration Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-07-30",
    },
    {
        "reference_number": "SEED-C-056",
        "institution_code": "SEED-INST-009",
        "institution_name_raw": "Eastbridge Tech. College, Kolkata",
        "complainant_name": "Amit Roy",
        "complaint_text": (
            "The college has not conducted internal examinations for the "
            "Electronics and Communication department for two consecutive "
            "semesters.  Students fear this will affect their university "
            "examination eligibility."
        ),
        "category": "Academic Irregularity",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "High",
        "date_received": "2026-08-25",
    },
    {
        "reference_number": "SEED-C-057",
        "institution_code": "SEED-INST-002",
        "institution_name_raw": "LN Inst. of Technology, Vijayawada",
        "complainant_name": "Venkat Rao",
        "complaint_text": (
            "The institute is not maintaining a proper student grievance "
            "redressal cell as mandated.  The cell's contact details on the "
            "website are outdated and emails bounce."
        ),
        "category": "Governance",
        "bureau": "Regulation Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-09-05",
    },
    {
        "reference_number": "SEED-C-058",
        "institution_code": "SEED-INST-008",
        "institution_name_raw": "Pinnacle Institute of Pharmacy, Hyd",
        "complainant_name": "Lavanya K",
        "complaint_text": (
            "The pharmacy lab does not have the required drug samples and "
            "chemicals for the practical examinations.  Students from the "
            "B.Pharm 3rd year had to postpone their practical exam twice."
        ),
        "category": "Infrastructure",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-09-15",
    },
    {
        "reference_number": "SEED-C-059",
        "institution_code": "SEED-INST-010",
        "institution_name_raw": "Heritage Acad. of Architecture",
        "complainant_name": "Neeraj Mehta",
        "complaint_text": (
            "The visiting faculty for the Environmental Design course has "
            "not conducted a single class in the current semester.  Students "
            "have paid full fees but are not receiving the instruction."
        ),
        "category": "Faculty Shortage",
        "bureau": "Academic Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-09-22",
    },
    {
        "reference_number": "SEED-C-060",
        "institution_code": "SEED-INST-003",
        "institution_name_raw": "Bharathi Vidyapeeth College of Engineering, Pune",
        "complainant_name": "Rahul Deshmukh",
        "complaint_text": (
            "The college is charging an undisclosed 'technology fee' of "
            "Rs 15,000 per semester for Wi-Fi access which is supposed to "
            "be included in the tuition fee as per the approved structure."
        ),
        "category": "Fee Irregularity",
        "bureau": "Finance Bureau",
        "status": "Open",
        "priority": "Normal",
        "date_received": "2026-10-01",
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# ACTION HISTORY — pre-populated actions for select complaints
# ═══════════════════════════════════════════════════════════════════════════
# Each tuple: (complaint_ref, action_type, description, performed_by, timestamp)
# Uses the complaint reference_number to look up complaint_id at insert time.

ACTION_HISTORY = [
    # Scenario A – SEED-C-001
    ("SEED-C-001", "Status Change", "Complaint received and logged.",
     "System", "2026-06-10 09:30:00"),
    ("SEED-C-001", "Note", "Forwarded to PGRC desk officer for initial review.",
     "Desk Officer", "2026-06-11 11:00:00"),
    ("SEED-C-001", "Note",
     "Fee fixation committee records requested from the institution.",
     "PGRC Officer", "2026-06-15 14:20:00"),

    # Scenario A – SEED-C-002
    ("SEED-C-002", "Status Change", "Complaint received and logged.",
     "System", "2026-06-18 10:15:00"),
    ("SEED-C-002", "Status Change", "Status changed to Under Review.",
     "Regulation Bureau", "2026-06-22 16:00:00"),

    # Scenario B – SEED-C-003
    ("SEED-C-003", "Status Change", "Complaint received and logged.",
     "System", "2026-07-02 08:45:00"),

    # Scenario E – SEED-C-030 (resolved)
    ("SEED-C-030", "Status Change", "Complaint received and logged.",
     "System", "2025-08-12 10:00:00"),
    ("SEED-C-030", "Note",
     "Approval records verified — programme not in approved list.",
     "Approval Bureau", "2025-09-05 13:30:00"),
    ("SEED-C-030", "Note",
     "Show-cause notice issued to the institution.",
     "Approval Bureau", "2025-09-20 10:00:00"),
    ("SEED-C-030", "Note",
     "Institution responded; programme discontinued effective Dec 2025.",
     "Approval Bureau", "2025-11-15 15:45:00"),
    ("SEED-C-030", "Status Change",
     "Complaint resolved — programme discontinued, students transferred.",
     "Approval Bureau", "2026-01-20 11:30:00"),

    # Scenario E – SEED-C-031 (aging, no follow-up since filing)
    ("SEED-C-031", "Status Change", "Complaint received and logged.",
     "System", "2026-02-14 09:00:00"),
    # Deliberately NO further actions — this is an aging case.

    # Scenario E – SEED-C-032 (escalated)
    ("SEED-C-032", "Status Change", "Complaint received and logged.",
     "System", "2025-11-05 10:30:00"),
    ("SEED-C-032", "Note",
     "Institution asked to provide refund status for all pending deposits.",
     "Finance Bureau", "2025-12-01 14:00:00"),
    ("SEED-C-032", "Note",
     "No response from institution within 30 days.",
     "Finance Bureau", "2026-01-05 09:00:00"),
    ("SEED-C-032", "Status Change",
     "Escalated due to non-compliance.  Reminder sent to institution head.",
     "Finance Bureau", "2026-01-10 11:15:00"),
    ("SEED-C-032", "Note",
     "Second reminder issued.  Matter flagged for regulatory action.",
     "Finance Bureau", "2026-03-15 16:00:00"),

    # A few actions on other complaints for realism
    ("SEED-C-010", "Status Change", "Complaint received and logged.",
     "System", "2026-05-15 09:00:00"),
    ("SEED-C-044", "Status Change", "Complaint received and logged.",
     "System", "2026-04-10 09:00:00"),
    ("SEED-C-044", "Note", "Programme approval list cross-checked.",
     "Approval Bureau", "2026-04-25 14:00:00"),
    ("SEED-C-041", "Status Change", "Complaint received and logged.",
     "System", "2026-07-11 09:00:00"),
    ("SEED-C-043", "Status Change", "Complaint received and logged.",
     "System", "2026-06-25 09:00:00"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Scenario tag lookup (for tests and documentation)
# ═══════════════════════════════════════════════════════════════════════════

SCENARIO_REFS = {
    "A_same_institution_same_issue": ("SEED-C-001", "SEED-C-002"),
    "B_same_institution_unrelated": ("SEED-C-001", "SEED-C-003"),
    "C_similar_text_different_inst": ("SEED-C-010", "SEED-C-011"),
    "D_similar_issue_weak_evidence": ("SEED-C-020", "SEED-C-021"),
    "E_varied_statuses": ("SEED-C-030", "SEED-C-031", "SEED-C-032"),
}


# ═══════════════════════════════════════════════════════════════════════════
# Seeding logic
# ═══════════════════════════════════════════════════════════════════════════

def seed(db_path: Path | str | None = None) -> dict:
    """
    Populate the database with synthetic data.

    Idempotency strategy:
      - Institutions: INSERT OR IGNORE keyed on identifier_code (UNIQUE).
        Since the schema doesn't currently have a UNIQUE on identifier_code,
        we check for existence before inserting.
      - Complaints: INSERT OR IGNORE keyed on reference_number (UNIQUE).
      - Action history: We delete existing actions for seed complaints before
        re-inserting, so history stays consistent on re-seed.

    Returns a summary dict: {"institutions": N, "complaints": N, "actions": N}
    """
    path = init_db(db_path)
    conn = get_connection(path)

    stats = {"institutions": 0, "complaints": 0, "actions": 0}

    try:
        # ── Institutions ──
        for code, name, norm, itype, city, state in INSTITUTIONS:
            existing = conn.execute(
                "SELECT id FROM institutions WHERE identifier_code = ?;",
                (code,),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO institutions
                       (name, name_normalized, identifier_code,
                        institution_type, city, state)
                       VALUES (?, ?, ?, ?, ?, ?);""",
                    (name, norm, code, itype, city, state),
                )
                stats["institutions"] += 1

        conn.commit()

        # Build lookup: identifier_code → institution.id
        inst_lookup = {
            row["identifier_code"]: row["id"]
            for row in conn.execute(
                "SELECT id, identifier_code FROM institutions "
                "WHERE identifier_code LIKE 'SEED-INST-%';"
            ).fetchall()
        }

        # ── Complaints ──
        for c in COMPLAINTS:
            existing = conn.execute(
                "SELECT id FROM complaints WHERE reference_number = ?;",
                (c["reference_number"],),
            ).fetchone()
            if existing is None:
                inst_id = inst_lookup.get(c["institution_code"])
                conn.execute(
                    """INSERT INTO complaints
                       (reference_number, institution_id, institution_name_raw,
                        complainant_name, complaint_text, category, bureau,
                        status, priority, date_received, date_closed)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
                    (
                        c["reference_number"],
                        inst_id,
                        c.get("institution_name_raw"),
                        c.get("complainant_name"),
                        c["complaint_text"],
                        c.get("category"),
                        c.get("bureau"),
                        c.get("status", "Open"),
                        c.get("priority", "Normal"),
                        c.get("date_received"),
                        c.get("date_closed"),
                    ),
                )
                stats["complaints"] += 1

        conn.commit()

        # Build lookup: reference_number → complaint.id
        complaint_lookup = {
            row["reference_number"]: row["id"]
            for row in conn.execute(
                "SELECT id, reference_number FROM complaints "
                "WHERE reference_number LIKE 'SEED-C-%';"
            ).fetchall()
        }

        # ── Action history ──
        # Delete existing seed actions to avoid duplicates on re-seed.
        seed_complaint_ids = list(complaint_lookup.values())
        if seed_complaint_ids:
            placeholders = ",".join("?" * len(seed_complaint_ids))
            conn.execute(
                f"DELETE FROM action_history WHERE complaint_id IN ({placeholders})"
                " AND performed_by IS NOT NULL;",
                seed_complaint_ids,
            )

        for ref, atype, desc, by, ts in ACTION_HISTORY:
            cid = complaint_lookup.get(ref)
            if cid is not None:
                conn.execute(
                    """INSERT INTO action_history
                       (complaint_id, action_type, description,
                        performed_by, created_at)
                       VALUES (?, ?, ?, ?, ?);""",
                    (cid, atype, desc, by, ts),
                )
                stats["actions"] += 1

        conn.commit()
    finally:
        conn.close()

    return stats



# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point:  python -m src.seed_data [db_path]
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    db_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = seed(db_arg)
    print(f"Seeding complete: {result}")
