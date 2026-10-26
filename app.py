"""
app.py — Streamlit entry point for the Complaint Monitoring Dashboard.

This is the file you run with `streamlit run app.py`.
For now it shows:
  - A title and short description.
  - A database health indicator (green / red).
  - The current complaint count from SQLite.

All heavy logic lives in src/; this file is intentionally thin.
"""

from datetime import date

import altair as alt
import streamlit as st

from src.database import init_db, check_health, get_connection
from src.relationship_detection import detect_relationships


# Compact, read-only presentation layer for the demonstration.  The legacy
# scaffold below is intentionally retained but is not reached after this view.
st.set_page_config(page_title="Institution Complaint Monitoring", page_icon="IC", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
.stApp{background:#f6f2ea;color:#243447}.block-container{padding-top:1.15rem;padding-bottom:1.5rem;max-width:1440px}
[data-testid="stHeader"]{background:#f6f2ea}[data-testid="stSidebar"]{background:#132b46;border-right:1px solid #27415d}[data-testid="stSidebar"] *{color:#edf3f6!important}
[data-testid="stSidebar"] [data-testid="stRadio"] label{padding:.45rem .55rem!important;margin:.12rem 0!important;border-radius:3px!important;border-left:3px solid transparent!important;background:transparent!important}[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked){background:#224566!important;border-left-color:#d0953d!important;font-weight:700!important}[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#1a3b5a!important}
h1,h2,h3{color:#17324d!important}h1{font-size:1.7rem!important;margin:.1rem 0 .2rem!important}h2{font-size:1.15rem!important}.eyebrow{color:#157b78;font-size:.7rem;font-weight:700;letter-spacing:.1em}.subtitle{color:#5e6a70;margin:0}.chip{display:inline-block;border:1px solid #aeb9bb;color:#174f63;background:#fff;padding:.2rem .52rem;border-radius:3px;font-size:.68rem;font-weight:700;letter-spacing:.035em}.demo{border-color:#c58228;color:#815313;background:#fff8e9}.kpi{background:#fff;border:1px solid #d8d2c6;border-top:3px solid #17324d;border-radius:4px;padding:.65rem .75rem;min-height:74px}.kpi.teal{border-top-color:#167d78}.kpi.saffron{border-top-color:#c37b22}.kpi.green{border-top-color:#36715c}.kpi.stone{border-top-color:#77736c}.kpi.primary{min-height:86px;border-top-width:4px}.kpi.primary .kv{font-size:1.7rem}.kpi.secondary{min-height:70px;padding:.55rem .65rem}.kpi.secondary .kv{font-size:1.2rem}.kl{color:#667177;font-size:.72rem;font-weight:600}.kv{color:#17324d;font-size:1.38rem;font-weight:700}.kn{color:#6d777d;font-size:.67rem}.note{border-left:3px solid #167d78;background:#edf5f3;color:#294842;padding:.55rem .7rem;border-radius:2px;margin:.55rem 0 .9rem}.stTextArea textarea{font-size:.83rem;background:#fbfaf7!important;color:#243447!important}[data-testid="stDataFrame"]{border:1px solid #d8d2c6;border-radius:4px}.stButton>button{background:#17324d!important;color:#fff!important;border:1px solid #17324d!important;border-radius:3px!important}.stButton>button:focus{outline:3px solid #e5bd76!important;outline-offset:2px}.stSelectbox label,.stMultiSelect label{color:#40515d!important;font-size:.78rem!important;font-weight:600!important}
</style>""", unsafe_allow_html=True)

if "demo_db_ready" not in st.session_state:
    init_db()
    st.session_state.demo_db_ready = True
if "demo_reviewed" not in st.session_state:
    st.session_state.demo_reviewed = set()
if "demo_evidence_seen" not in st.session_state:
    st.session_state.demo_evidence_seen = set()


@st.cache_data(ttl=30, show_spinner=False)
def _demo_records():
    """Read records only; no dashboard workflow writes complaint data."""
    conn = get_connection()
    try:
        rows = [dict(row) for row in conn.execute("SELECT * FROM complaints ORDER BY reference_number")]
        orgs = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM institutions")}
    finally:
        conn.close()
    return rows, orgs


@st.cache_data(ttl=30, show_spinner=False)
def _demo_history(complaint_id):
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute("SELECT created_at, action_type, description, performed_by FROM action_history WHERE complaint_id = ? ORDER BY created_at ASC, id ASC", (complaint_id,))]
    finally:
        conn.close()


@st.cache_data(ttl=30, show_spinner=False)
def _demo_matches(rows, orgs):
    return detect_relationships(rows, orgs)


def _demo_age(row):
    try:
        return max(0, (date.today() - date.fromisoformat(str(row.get("date_received")))).days) if row.get("date_received") else None
    except ValueError:
        return None


def _demo_unresolved(row):
    return (row.get("status") or "").casefold() not in {"resolved", "closed"}


def _demo_name(row, orgs):
    return (orgs.get(row.get("institution_id"), {}).get("name") or row.get("institution_name_raw") or "Institution not recorded")


def _demo_priority(match):
    return {"likely related": "High", "potentially related": "Medium"}.get(match.classification, "Low")


def _demo_key(match):
    return f"{match.complaint_id_a}|{match.complaint_id_b}"


def _demo_open_matches():
    st.session_state.workspace_nav = "Potential Matches"


def _demo_kpi(column, label, value, note, tone="", emphasis="secondary"):
    with column:
        st.markdown(f'<div class="kpi {tone} {emphasis}"><div class="kl">{label}</div><div class="kv">{value}</div><div class="kn">{note}</div></div>', unsafe_allow_html=True)


health = check_health()
if health["status"] != "ok":
    st.error(f"Database connection unavailable: {health.get('detail', 'unknown error')}")
    st.stop()
rows, orgs = _demo_records()
matches = _demo_matches(rows, orgs) if len(rows) > 1 else []
actionable = [item for item in matches if item.classification != "insufficient evidence"]
pending_reviews = sum(_demo_key(item) not in st.session_state.demo_reviewed for item in actionable)
seed_count = sum((row.get("reference_number") or "").startswith("SEED-") for row in rows)

head, state = st.columns([4, 1])
with head:
    st.markdown('<div class="eyebrow">INTEGRATED INSTITUTION COMPLAINT MONITORING SYSTEM</div><h1>Complaint coordination dashboard</h1><p class="subtitle">Read-only AICTE hackathon demonstration for triaging complaints and reviewing potential overlaps across bureaus.</p>', unsafe_allow_html=True)
with state:
    st.markdown('<span class="chip demo">DEMO · SYNTHETIC DATA</span>', unsafe_allow_html=True)
    st.write("")
    st.markdown('<span class="chip">DATABASE CONNECTED</span>', unsafe_allow_html=True)
    st.caption(f"{seed_count} synthetic complaints · SQLite")
st.markdown('<div class="note">Potential relationships are advisory ranking signals only. Human review is required; the dashboard never merges institutions, changes assignments, resolves cases, or writes relationship records.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ICMS")
    st.caption("Internal demonstration workspace")
    workspace = st.radio("Navigate", ["Overview & Complaints", "Potential Matches"], label_visibility="collapsed", key="workspace_nav")
    st.divider()
    st.markdown("**Data notice**")
    st.caption(f"All {seed_count} current complaint records are synthetic demonstration data.")
    st.markdown("**Safety**")
    st.caption("Read-only review. No complaint record, institution assignment, or relationship is changed here.")

if workspace == "Overview & Complaints":
    st.subheader("Complaint overview")
    if not rows:
        st.info("No complaints are available. Overview, search, and history will appear when records are loaded.")
    else:
        unresolved = sum(_demo_unresolved(row) for row in rows)
        resolved = sum((row.get("status") or "").casefold() in {"resolved", "closed"} for row in rows)
        escalated = sum((row.get("status") or "").casefold() == "escalated" for row in rows)
        ageing = sum(_demo_unresolved(row) and (_demo_age(row) or 0) >= 30 for row in rows)
        cards = st.columns([1.35, 1.35, 1, 1, 1, 1])
        _demo_kpi(cards[0], "Total complaints", len(rows), "All records", "stone", "primary")
        _demo_kpi(cards[1], "Unresolved", unresolved, "Open, review, escalated", "teal", "primary")
        _demo_kpi(cards[2], "Resolved", resolved, "Resolved or closed", "green")
        _demo_kpi(cards[3], "Escalated", escalated, "Requires attention", "saffron")
        _demo_kpi(cards[4], "Ageing unresolved", ageing, "30+ days", "saffron")
        _demo_kpi(cards[5], "Matches awaiting review", pending_reviews, "Advisory candidates", "teal")
        distribution, attention = st.columns([1.5, 1])
        with distribution:
            status_counts = {}
            for row in rows:
                status = row.get("status") or "Not recorded"
                status_counts[status] = status_counts.get(status, 0) + 1
            status_order = ["Open", "Under Review", "Escalated", "Resolved", "Closed", "Not recorded"]
            status_data = [
                {"Status": status, "Complaints": status_counts[status]}
                for status in status_order if status in status_counts
            ] + [
                {"Status": status, "Complaints": count}
                for status, count in sorted(status_counts.items()) if status not in status_order
            ]
            st.markdown("**Status distribution**")
            colors = {"Open": "#17324d", "Under Review": "#167d78", "Escalated": "#c37b22", "Resolved": "#36715c", "Closed": "#36715c", "Not recorded": "#77736c"}
            base = alt.Chart(alt.Data(values=status_data)).encode(
                y=alt.Y("Status:N", sort=[item["Status"] for item in status_data], title=None, axis=alt.Axis(labelColor="#52616a", labelFontSize=11)),
                x=alt.X("Complaints:Q", title=None, axis=alt.Axis(tickMinStep=1, labelColor="#52616a", gridColor="#e5dfd4")),
                color=alt.Color("Status:N", scale=alt.Scale(domain=list(colors), range=list(colors.values())), legend=None),
                tooltip=[alt.Tooltip("Status:N"), alt.Tooltip("Complaints:Q")],
            )
            chart = (base.mark_bar(size=16, cornerRadiusEnd=2) + base.mark_text(align="left", baseline="middle", dx=5, color="#33444e").encode(text="Complaints:Q")).properties(height=max(100, 31 * len(status_data))).configure_view(stroke=None)
            st.altair_chart(chart, use_container_width=True)
        with attention:
            st.markdown("**Priority summary**")
            queue_one, queue_two = st.columns(2)
            queue_one.metric("Awaiting review", pending_reviews)
            queue_two.metric("Ageing cases", ageing)
            st.caption("Candidate matches and unresolved cases requiring attention.")
            st.button("Open potential matches", key="open_matches", use_container_width=True, on_click=_demo_open_matches)
    st.markdown("#### Complaint browser")
    if not rows:
        st.info("There are no complaint records to search or inspect.")
    else:
        search, stat, bureau, category = st.columns([2.2, 1, 1, 1])
        query = search.text_input("Search", placeholder="Reference, institution, or description", label_visibility="collapsed", key="demo_search")
        states = sorted({row.get("status") for row in rows if row.get("status")})
        bureaus = sorted({row.get("bureau") for row in rows if row.get("bureau")})
        categories = sorted({row.get("category") for row in rows if row.get("category")})
        wanted_states = stat.multiselect("Status", states, key="demo_status")
        wanted_bureaus = bureau.multiselect("Bureau", bureaus, key="demo_bureau")
        wanted_categories = category.multiselect("Category", categories, key="demo_category")
        needle = query.casefold().strip()
        visible = []
        for row in rows:
            text = " ".join((str(row.get("reference_number") or ""), _demo_name(row, orgs), str(row.get("complaint_text") or ""))).casefold()
            if (not needle or needle in text) and (not wanted_states or row.get("status") in wanted_states) and (not wanted_bureaus or row.get("bureau") in wanted_bureaus) and (not wanted_categories or row.get("category") in wanted_categories):
                visible.append(row)
        if not visible:
            st.info("No complaints match the current search and filters.")
        else:
            table = []
            for row in visible:
                age = _demo_age(row)
                table.append({"Reference": row.get("reference_number") or "—", "Institution": _demo_name(row, orgs), "Category": row.get("category") or "—", "Bureau": row.get("bureau") or "—", "Status": row.get("status") or "Not recorded", "Received": row.get("date_received") or "—", "Age": f"{age} days unresolved" if _demo_unresolved(row) and age is not None else "—"})
            st.dataframe(table, use_container_width=True, hide_index=True, height=250)
            ref = st.selectbox("Inspect complaint and action history", [row["reference_number"] for row in visible], key="demo_complaint")
            selected = next(row for row in visible if row["reference_number"] == ref)
            details, timeline = st.columns([1, 2])
            with details:
                st.markdown("**Selected complaint**")
                st.caption(_demo_name(selected, orgs))
                st.write(f"**Status:** {selected.get('status') or 'Not recorded'}")
                st.write(f"**Category:** {selected.get('category') or '—'}")
                st.write(f"**Bureau:** {selected.get('bureau') or '—'}")
                st.caption(selected.get("complaint_text") or "No description supplied.")
            with timeline:
                st.markdown(f"**Action history — {ref}**")
                history = _demo_history(selected["id"])
                if history:
                    st.dataframe([{"Timestamp": item.get("created_at") or "—", "Action": item.get("action_type") or "—", "Note": item.get("description") or "—", "Actor": item.get("performed_by") or "—"} for item in history], use_container_width=True, hide_index=True, height=180)
                else:
                    st.caption("No action-history entries are recorded for this complaint.")

else:
    st.subheader("Potential matches")
    st.caption("Institution resolution, issue-text similarity, and overall ranking are deterministic heuristic signals—not calibrated probabilities, semantic understanding, or automated decisions.")
    if len(rows) < 2:
        st.info("At least two complaints are required to generate potential-match comparisons.")
    else:
        classifications = ["likely related", "potentially related", "insufficient evidence"]
        left_filter, right_filter, explanation = st.columns([1.2, 1.2, 2])
        chosen_classes = left_filter.multiselect("Classification", classifications, default=classifications[:2], key="demo_class")
        chosen_priorities = right_filter.multiselect("Review priority", ["High", "Medium", "Low"], default=["High", "Medium"], key="demo_priority")
        explanation.caption("High = likely related; Medium = potentially related. Filters are read-only.")
        shown = [item for item in matches if item.classification in chosen_classes and _demo_priority(item) in chosen_priorities]
        progress, milestones = st.columns([1.2, 2])
        with progress:
            count = len(st.session_state.demo_reviewed)
            st.markdown("**Reviewer progress — demo only**")
            st.progress(min(count / max(len(actionable), 1), 1.0), text=f"{count} of {len(actionable)} actionable candidates reviewed")
            st.caption(f"{count * 10} demo XP · resets with the browser session")
        with milestones:
            st.markdown(f"**Milestones** · First Review: {'Complete' if st.session_state.demo_reviewed else 'Pending'} · Evidence Examined: {'Complete' if st.session_state.demo_evidence_seen else 'Pending'} · 10 Cases Reviewed: {min(len(st.session_state.demo_reviewed), 10)}/10")
            st.caption("Progress records demonstration review activity only—not approval, dismissal, a decision, an audit log, or a persistent reviewer account.")
        if not shown:
            st.info("No potential matches meet the selected filters. Broaden classification or priority filters to inspect other comparisons.")
        else:
            options = [f"{item.complaint_id_a} ↔ {item.complaint_id_b} · {_demo_priority(item)} · {item.classification.title()}" for item in shown]
            choice = st.selectbox("Select a comparison", options, key="demo_match")
            match = shown[options.index(choice)]
            first = next(row for row in rows if row["reference_number"] == match.complaint_id_a)
            second = next(row for row in rows if row["reference_number"] == match.complaint_id_b)
            match_key = _demo_key(match)
            a, b, score = st.columns([2, 2, 1.15])
            for column, row, label in ((a, first, "Complaint A"), (b, second, "Complaint B")):
                with column:
                    with st.container(border=True):
                        st.caption(label)
                        st.markdown(f"**{row['reference_number']}**")
                        st.write(_demo_name(row, orgs))
                        st.caption(f"{row.get('category') or '—'} · {row.get('bureau') or '—'} · {row.get('status') or 'Not recorded'}")
                        st.text_area("Description", row.get("complaint_text") or "No description supplied.", height=180, disabled=True, key=f"demo_{label}_{row['reference_number']}")
            with score:
                with st.container(border=True):
                    st.caption("ADVISORY REVIEW")
                    st.metric("Priority", _demo_priority(match))
                    st.metric("Institution match", f"{match.institution_confidence:.0%}")
                    st.metric("Issue-text similarity", f"{match.issue_confidence:.0%}")
                    st.metric("Overall ranking", f"{match.overall_confidence:.0%}")
                    st.caption(match.classification.title())
            st.markdown(f"**Evidence summary:** {'; '.join(match.evidence[:2]) or 'No comparable evidence was supplied.'}")
            with st.expander("Detailed matching evidence"):
                for evidence in match.evidence:
                    st.write(f"• {evidence}")
            st.markdown(f'<div class="note"><b>Human review required:</b> {match.review_recommendation}</div>', unsafe_allow_html=True)
            review, evidence = st.columns(2)
            with review:
                if st.button("Mark comparison reviewed (demo)", disabled=match_key in st.session_state.demo_reviewed, use_container_width=True):
                    st.session_state.demo_reviewed.add(match_key)
                    st.rerun()
            with evidence:
                if st.button("Record evidence examination (demo)", disabled=match_key in st.session_state.demo_evidence_seen, use_container_width=True):
                    st.session_state.demo_evidence_seen.add(match_key)
                    st.rerun()
            st.caption("These non-persistent demo interactions do not approve, dismiss, merge, close, or otherwise change complaint records.")

st.stop()

# ---------------------------------------------------------------------------
# Page configuration (must be the first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Complaint Monitoring Dashboard",
    page_icon="📋",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Ensure the database is initialized on first run
# ---------------------------------------------------------------------------
if "db_initialized" not in st.session_state:
    init_db()
    st.session_state.db_initialized = True

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📋 Integrated Institution Complaint Monitoring Dashboard")
st.caption("AICTE demonstration • Monitor complaints, review history, and coordinate potential overlaps across bureaus.")

# ---------------------------------------------------------------------------
# Health / status indicator
# ---------------------------------------------------------------------------
health = check_health()

if health["status"] == "ok":
    col1, col2, col3 = st.columns(3)
    col1.metric("Database Status", "✅ Connected")
    col2.metric("Tables", len(health["tables"]))
    col3.metric("Complaints on File", health["complaint_count"])

    # Indicate if synthetic seed data is loaded
    if health["complaint_count"] > 0:
        _conn = get_connection()
        _seed_count = _conn.execute(
            "SELECT COUNT(*) FROM complaints WHERE reference_number LIKE 'SEED-%';"
        ).fetchone()[0]
        _conn.close()
        if _seed_count > 0:
            st.caption(
                f"⚠️ {_seed_count} of {health['complaint_count']} complaints "
                "are synthetic demo data (SEED-* references)."
            )
else:
    st.error(f"Database error: {health.get('detail', 'unknown')}")

st.divider()


@st.cache_data(ttl=30, show_spinner=False)
def _load_matching_records():
    """Read records for advisory matching; this dashboard never writes data."""
    conn = get_connection()
    try:
        complaints = [dict(row) for row in conn.execute("SELECT * FROM complaints ORDER BY reference_number")]
        institutions = {
            row["id"]: dict(row)
            for row in conn.execute("SELECT * FROM institutions")
        }
    finally:
        conn.close()
    return complaints, institutions


@st.cache_data(ttl=30, show_spinner=False)
def _load_action_history(complaint_id):
    """Read one complaint's chronology without changing any record."""
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(
            """SELECT created_at, action_type, description, performed_by
               FROM action_history WHERE complaint_id = ? ORDER BY created_at ASC, id ASC""",
            (complaint_id,),
        )]
    finally:
        conn.close()


@st.cache_data(ttl=30, show_spinner=False)
def _detect_candidates(complaint_records, institution_records):
    """Cache deterministic, read-only comparisons between database refreshes."""
    return detect_relationships(complaint_records, institution_records)


def _review_priority(candidate):
    """Presentation-only priority for sorting human review candidates."""
    if candidate.classification == "likely related":
        return "High"
    if candidate.classification == "potentially related":
        return "Medium"
    return "Low"


def _age_in_days(complaint):
    """Return elapsed days from receipt, or None when no usable date exists."""
    received = complaint.get("date_received")
    if not received:
        return None
    try:
        return max(0, (date.today() - date.fromisoformat(str(received))).days)
    except ValueError:
        return None


def _is_unresolved(complaint):
    return (complaint.get("status") or "").casefold() not in {"resolved", "closed"}


def _status_label(status):
    icons = {"open": "🟠", "under review": "🔵", "resolved": "🟢", "closed": "🟢", "escalated": "🔴"}
    text = status or "Not recorded"
    return f"{icons.get(text.casefold(), '⚪')} {text}"


def _classification_label(classification):
    icons = {"likely related": "🔴", "potentially related": "🟠", "insufficient evidence": "⚪"}
    return f"{icons.get(classification, '⚪')} {classification.title()}"


complaints, institutions = _load_matching_records()

st.info(
    "Suggested relationships are advisory only. A human reviewer must assess the evidence; "
    "the dashboard never merges institutions, resolves complaints, or changes case records."
)

st.subheader("📊 Complaint Overview")
st.caption("Ageing unresolved complaints have remained open for 30 days or more.")
if not complaints:
    st.info("No complaints are available yet. Overview, search, and history will appear when records are added.")
else:
    open_or_pending = sum(
        (row.get("status") or "").casefold() in {"open", "under review"}
        for row in complaints
    )
    resolved = sum((row.get("status") or "").casefold() in {"resolved", "closed"} for row in complaints)
    escalated = sum((row.get("status") or "").casefold() == "escalated" for row in complaints)
    ageing = sum(_is_unresolved(row) and (_age_in_days(row) or 0) >= 30 for row in complaints)
    overview_columns = st.columns(5)
    overview_columns[0].metric("Total complaints", len(complaints))
    overview_columns[1].metric("Pending / open", open_or_pending)
    overview_columns[2].metric("Resolved", resolved)
    overview_columns[3].metric("Escalated", escalated)
    overview_columns[4].metric("Ageing unresolved", ageing)

st.subheader("📂 Complaint Browser")
if not complaints:
    st.info("There are no complaints to search or inspect.")
else:
    search_text = st.text_input("Search complaints", placeholder="Reference number, institution, or complaint text")
    browser_left, browser_middle, browser_right = st.columns(3)
    statuses = sorted({row.get("status") for row in complaints if row.get("status")})
    bureaus = sorted({row.get("bureau") for row in complaints if row.get("bureau")})
    categories = sorted({row.get("category") for row in complaints if row.get("category")})
    selected_statuses = browser_left.multiselect("Status", statuses, key="complaint_status_filter")
    selected_bureaus = browser_middle.multiselect("Bureau", bureaus, key="complaint_bureau_filter")
    selected_categories = browser_right.multiselect("Category", categories, key="complaint_category_filter")

    filtered_complaints = []
    query = search_text.casefold().strip()
    for complaint in complaints:
        institution = institutions.get(complaint.get("institution_id"), {})
        haystack = " ".join(str(value or "") for value in (
            complaint.get("reference_number"), institution.get("name", complaint.get("institution_name_raw")),
            complaint.get("complaint_text"),
        )).casefold()
        if query and query not in haystack:
            continue
        if selected_statuses and complaint.get("status") not in selected_statuses:
            continue
        if selected_bureaus and complaint.get("bureau") not in selected_bureaus:
            continue
        if selected_categories and complaint.get("category") not in selected_categories:
            continue
        filtered_complaints.append(complaint)

    if not filtered_complaints:
        st.info("No complaints match the current search and filters.")
    else:
        browser_rows = []
        for complaint in filtered_complaints:
            institution = institutions.get(complaint.get("institution_id"), {})
            age = _age_in_days(complaint)
            browser_rows.append({
                "Reference": complaint.get("reference_number"),
                "Institution": institution.get("name", complaint.get("institution_name_raw") or "—"),
                "Category": complaint.get("category") or "—",
                "Bureau": complaint.get("bureau") or "—",
                "Status": _status_label(complaint.get("status")),
                "Received": complaint.get("date_received") or "—",
                "Age": f"{age} days unresolved" if _is_unresolved(complaint) and age is not None else "—",
            })
        st.dataframe(browser_rows, use_container_width=True, hide_index=True)

        selected_reference = st.selectbox(
            "View complaint history",
            [row["reference_number"] for row in filtered_complaints],
            key="history_complaint",
        )
        selected_complaint = next(row for row in filtered_complaints if row["reference_number"] == selected_reference)
        history = _load_action_history(selected_complaint["id"])
        st.markdown(f"**Action history — {selected_reference}**")
        if not history:
            st.caption("No action-history entries are recorded for this complaint.")
        else:
            st.dataframe([
                {
                    "Timestamp": entry.get("created_at") or "—",
                    "Action": entry.get("action_type") or "—",
                    "Note": entry.get("description") or "—",
                    "Actor": entry.get("performed_by") or "—",
                }
                for entry in history
            ], use_container_width=True, hide_index=True)

st.divider()
st.subheader("🔎 Potential Matches")
st.caption(
    "Read-only advisory results from deterministic institution resolution and "
    "TF-IDF issue comparison. Scores are ranking heuristics, not probabilities "
    "or decisions; review is required before coordination or action."
)

if len(complaints) < 2:
    st.info("Add at least two complaints before potential matches can be compared.")
else:
    candidates = _detect_candidates(complaints, institutions)
    classifications = ["likely related", "potentially related", "insufficient evidence"]
    filter_left, filter_right = st.columns(2)
    selected_classifications = filter_left.multiselect(
        "Classification",
        classifications,
        default=["likely related", "potentially related"],
        help="Start with actionable advisory candidates; include insufficient evidence when needed.",
    )
    selected_priorities = filter_right.multiselect(
        "Review priority",
        ["High", "Medium", "Low"],
        default=["High", "Medium"],
        help="Priority is a display aid based on the advisory classification, not a case priority.",
    )
    filtered = [
        candidate for candidate in candidates
        if candidate.classification in selected_classifications
        and _review_priority(candidate) in selected_priorities
    ]

    if not filtered:
        st.info("No candidates match the selected filters. Adjust the filters to inspect other comparisons.")
    else:
        complaint_by_reference = {row["reference_number"]: row for row in complaints}
        summary_rows = []
        for candidate in filtered:
            first = complaint_by_reference[candidate.complaint_id_a]
            second = complaint_by_reference[candidate.complaint_id_b]
            first_institution = institutions.get(first["institution_id"], {})
            second_institution = institutions.get(second["institution_id"], {})
            summary_rows.append({
                "Review priority": _review_priority(candidate),
                "Classification": _classification_label(candidate.classification),
                "Complaint A": candidate.complaint_id_a,
                "Institution A": first_institution.get("name", first.get("institution_name_raw", "—")),
                "Bureau A": first.get("bureau") or "—",
                "Category A": first.get("category") or "—",
                "Status A": _status_label(first.get("status")),
                "Complaint B": candidate.complaint_id_b,
                "Institution B": second_institution.get("name", second.get("institution_name_raw", "—")),
                "Bureau B": second.get("bureau") or "—",
                "Category B": second.get("category") or "—",
                "Status B": _status_label(second.get("status")),
                "Institution match score (heuristic)": f"{candidate.institution_confidence:.0%}",
                "Issue similarity score (heuristic)": f"{candidate.issue_confidence:.0%}",
                "Overall advisory score (heuristic)": f"{candidate.overall_confidence:.0%}",
            })

        metric_one, metric_two, metric_three = st.columns(3)
        metric_one.metric("Matches shown", len(filtered))
        metric_two.metric("Human review", sum(item.classification != "insufficient evidence" for item in filtered))
        metric_three.metric("High priority", sum(_review_priority(item) == "High" for item in filtered))
        st.dataframe(summary_rows, use_container_width=True, hide_index=True)

        candidate_labels = [
            f"{item.complaint_id_a} ↔ {item.complaint_id_b} — {item.classification}"
            for item in filtered
        ]
        selected_label = st.selectbox("Inspect a candidate", candidate_labels)
        selected = filtered[candidate_labels.index(selected_label)]
        first = complaint_by_reference[selected.complaint_id_a]
        second = complaint_by_reference[selected.complaint_id_b]

        st.markdown(f"**Review recommendation:** {selected.review_recommendation}")
        with st.expander("Matching evidence", expanded=True):
            for item in selected.evidence:
                st.write(f"• {item}")

        left, right = st.columns(2)
        for column, complaint, label in (
            (left, first, "Complaint A"),
            (right, second, "Complaint B"),
        ):
            institution = institutions.get(complaint["institution_id"], {})
            with column:
                st.markdown(f"### {label}: {complaint['reference_number']}")
                st.caption(
                    f"{institution.get('name', complaint.get('institution_name_raw', '—'))} · "
                    f"{complaint.get('bureau') or '—'} · {_status_label(complaint.get('status'))}"
                )
                st.markdown(f"**Category:** {complaint.get('category') or '—'}")
                st.text_area(
                    "Complaint description",
                    value=complaint.get("complaint_text") or "No description supplied.",
                    height=220,
                    disabled=True,
                    key=f"description_{label}_{complaint['reference_number']}",
                )
