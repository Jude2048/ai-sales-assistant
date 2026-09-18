import streamlit as st
import requests


# ============================================================
# CONFIG
# ============================================================

API_URL = "https://ai-sales-assistant-production-2c8c.up.railway.app"


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="AI Sales Assistant",
    page_icon="🤖",
    layout="wide",
)


# ============================================================
# API HELPERS
# ============================================================

def api_get(path, timeout=20):
    try:
        response = requests.get(
            f"{API_URL}{path}",
            timeout=timeout,
        )

        if response.ok:
            return response.json()

        return {
            "error": response.text,
            "status_code": response.status_code,
        }

    except Exception as e:
        return {"error": str(e)}


def api_post(path, data=None, timeout=120):
    try:
        response = requests.post(
            f"{API_URL}{path}",
            json=data or {},
            timeout=timeout,
        )

        if response.ok:
            return response.json()

        return {
            "error": response.text,
            "status_code": response.status_code,
        }

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# SMALL UI HELPERS
# ============================================================

def show_api_error(result, default_message="Request failed."):
    if isinstance(result, dict) and "error" in result:
        st.error(
            f"{default_message}\n\n"
            f"{result.get('error', 'Unknown error')}"
        )
        return True

    return False


def get_step(run, agent, attempt=None):
    steps = run.get("steps", [])

    matching = [
        step
        for step in steps
        if step.get("agent") == agent
    ]

    if attempt is not None:
        matching = [
            step
            for step in matching
            if step.get("attempt") == attempt
        ]

    if not matching:
        return None

    return matching[-1]


def get_agent_steps(run, agent):
    return [
        step
        for step in run.get("steps", [])
        if step.get("agent") == agent
    ]


def status_icon(status):
    icons = {
        "COMPLETED": "✅",
        "FAILED": "❌",
        "STALE": "⚠️",
        "RUNNING": "🔄",
        "PENDING": "⏳",
    }

    return icons.get(status, "•")


def format_fact(fact):
    category = fact.get("category", "unknown").replace("_", " ").title()
    fact_id = fact.get("fact_id", "unknown")
    content = fact.get("content", "")

    return f"**{fact_id} · {category}** — {content}"


def display_source_reference(fact):
    reference = fact.get("source_reference", {})

    quote = reference.get("quote", "")
    location = reference.get("location", "")

    if quote:
        st.caption(f'📌 "{quote}"')

    if location:
        st.caption(f"Source: {location}")


# ============================================================
# HEADER
# ============================================================

st.title("AI Sales Assistant")

st.caption(
    "Unified interface for lead qualification, booking, and AI workflow."
)


# ============================================================
# ASSIGNMENT TOGGLE
# ============================================================

assignment = st.radio(
    "Assignment",
    [
        "1 — Lead Qualification & Booking",
        "2 — AI Sales Workflow",
    ],
    horizontal=True,
)


st.divider()


# ============================================================
# ASSIGNMENT 1
# ============================================================

if assignment.startswith("1"):

    st.header("Assignment 1")

    # --------------------------------------------------------
    # Sidebar
    # --------------------------------------------------------

    st.sidebar.header("Controls")

    if st.sidebar.button(
        "🔄 Refresh",
        use_container_width=True,
    ):
        st.rerun()

    st.sidebar.divider()

    st.sidebar.subheader("Channels")

    show_instagram = st.sidebar.checkbox(
        "Instagram",
        value=True,
    )

    show_email = st.sidebar.checkbox(
        "Email",
        value=True,
    )

    show_whatsapp = st.sidebar.checkbox(
        "WhatsApp",
        value=False,
    )

    # --------------------------------------------------------
    # Main columns
    # --------------------------------------------------------

    left, middle, right = st.columns(
        [1.2, 2.5, 1.5]
    )

    # --------------------------------------------------------
    # LEFT — Unified Inbox
    # --------------------------------------------------------

    with left:

        st.subheader("Unified Inbox")

        leads = api_get("/api/leads")

        if "error" in leads:

            st.warning(
                "Lead API not available yet."
            )

            st.info(
                "The UI is ready for the backend lead endpoint."
            )

        else:

            lead_list = (
                leads
                if isinstance(leads, list)
                else leads.get("leads", [])
            )

            filtered = []

            for lead in lead_list:

                channel = lead.get(
                    "channel",
                    "",
                ).lower()

                if (
                    channel == "instagram"
                    and show_instagram
                ):
                    filtered.append(lead)

                elif (
                    channel == "email"
                    and show_email
                ):
                    filtered.append(lead)

                elif (
                    channel == "whatsapp"
                    and show_whatsapp
                ):
                    filtered.append(lead)

            if not filtered:

                st.info("No leads found.")

            else:

                for lead in filtered:

                    lead_id = lead.get(
                        "lead_id",
                        "unknown",
                    )

                    status = lead.get(
                        "status",
                        "unknown",
                    )

                    channel = lead.get(
                        "channel",
                        "",
                    )

                    label = (
                        f"{channel.upper()}  "
                        f"{lead_id}"
                    )

                    if st.button(
                        "Apply Fact Correction",
                         type="primary",
                    ):

                        st.session_state[
                            "selected_lead"
                        ] = lead_id

                        st.rerun()

    # --------------------------------------------------------
    # SELECTED LEAD
    # --------------------------------------------------------

    selected_lead = st.session_state.get(
        "selected_lead"
    )

    if not selected_lead:

        with middle:

            st.subheader("💬 Conversation")

            st.info(
                "Select a lead from the inbox."
            )

        with right:

            st.subheader("📊 Lead")

            st.info(
                "Select a lead to view details."
            )

    else:

        # ----------------------------------------------------
        # MIDDLE — Conversation
        # ----------------------------------------------------

        with middle:

            st.subheader("💬 Conversation")

            conversation = api_get(
                f"/api/leads/{selected_lead}/conversation"
            )

            if "error" in conversation:

                st.info(
                    "Conversation endpoint not available yet."
                )

            else:

                messages = conversation.get(
                    "messages",
                    [],
                )

                for message in messages:

                    direction = message.get(
                        "direction"
                    )

                    content = message.get(
                        "content",
                        "",
                    )

                    if direction == "inbound":

                        with st.chat_message("user"):
                            st.write(content)

                    else:

                        with st.chat_message("assistant"):
                            st.write(content)

        # ----------------------------------------------------
        # RIGHT — Lead Control
        # ----------------------------------------------------

        with right:

            st.subheader("📊 Lead")

            lead = api_get(
                f"/api/leads/{selected_lead}"
            )

            if "error" in lead:

                st.info(
                    "Lead detail endpoint not available yet."
                )

            else:

                status = lead.get(
                    "status",
                    "unknown",
                )

                st.metric(
                    "Qualification",
                    status,
                )

                assignment_data = lead.get(
                    "assignment",
                    {},
                )

                st.write(
                    "**Representative:**",
                    assignment_data.get(
                        "representative",
                        "Unassigned",
                    ),
                )

                qualification = lead.get(
                    "qualification",
                    {},
                )

                st.write("**Evidence**")

                evidence = qualification.get(
                    "evidence",
                    [],
                )

                for item in evidence:
                    st.write(f"• {item}")

                st.divider()

                # Human takeover
                automation_enabled = lead.get(
                    "automation_enabled",
                    True,
                )

                new_automation = st.toggle(
                    "Automation",
                    value=automation_enabled,
                    key=f"automation_{selected_lead}",
                )

                if new_automation != automation_enabled:

                    result = api_post(
                        f"/api/leads/{selected_lead}/automation",
                        {
                            "enabled": new_automation
                        },
                    )

                    if "error" not in result:

                        st.success(
                            "Automation updated."
                        )

                        st.rerun()

                    else:

                        st.error(
                            "Could not update automation."
                        )

    # --------------------------------------------------------
    # BOOKING
    # --------------------------------------------------------

    st.divider()

    st.header("📅 Meeting")

    booking_col1, booking_col2 = st.columns(2)

    with booking_col1:

        st.subheader("Booking status")

        if selected_lead:

            lead = api_get(
                f"/api/leads/{selected_lead}"
            )

            pending = lead.get(
                "pending_booking",
                {},
            )

            meeting_status = lead.get(
                "meeting_status",
                pending.get(
                    "status",
                    "none",
                ),
            )

            st.metric(
                "Meeting",
                meeting_status,
            )

            if pending.get("slot"):

                st.write(
                    "**Selected slot:**",
                    pending["slot"],
                )

        else:

            st.info(
                "Select a lead."
            )

    with booking_col2:

        st.subheader("Calendar")

        calendar = api_get(
            "/debug/calendar/availability"
        )

        if calendar.get("status") == "ok":

            st.success(
                "Google Calendar connected"
            )

        else:

            st.warning(
                "Calendar status unavailable."
            )

    # --------------------------------------------------------
    # ACTION LOG
    # --------------------------------------------------------

    st.divider()

    st.header("📝 Action Log")

    if selected_lead:

        logs = api_get(
            f"/api/leads/{selected_lead}/actions"
        )

        if "error" in logs:

            st.info(
                "Action log endpoint not available yet."
            )

        else:

            action_list = logs.get(
                "actions",
                [],
            )

            for action in action_list:

                st.write(
                    f"**{action.get('action', 'Unknown')}** — "
                    f"{action.get('status', '')}"
                )

    else:

        st.info(
            "Select a lead to view actions."
        )


# ============================================================
# ASSIGNMENT 2
# ============================================================

else:

    st.header("Assignment 2")

    st.caption(
        "Three-agent meeting operations workflow: "
        "Intake → Planning → Review"
    )

    # ========================================================
    # SESSION STATE
    # ========================================================

    if "assignment2_run_id" not in st.session_state:
        st.session_state.assignment2_run_id = None

    if "assignment2_run" not in st.session_state:
        st.session_state.assignment2_run = None

    if "assignment2_session_id" not in st.session_state:
        st.session_state.assignment2_session_id = "demo-session"

    # ========================================================
    # RUN CONFIGURATION
    # ========================================================

    st.subheader("Run Configuration")

    config_col1, config_col2 = st.columns(2)

    with config_col1:

        session_id = st.text_input(
            "Session ID",
            value=st.session_state.assignment2_session_id,
            help="Keeps this workflow run isolated from other sessions.",
        )

    with config_col2:

        st.write("Backend")

        st.code(
            API_URL,
            language="text",
        )

    transcript = st.text_area(
        "Meeting Transcript",
        height=180,
        placeholder=(
            "Paste the meeting transcript here..."
        ),
        value=st.session_state.get(
            "assignment2_transcript",
            "",
        ),
    )

    company_rules = st.text_area(
        "Company Rules",
        height=150,
        placeholder=(
            "Paste the company rules here..."
        ),
        value=st.session_state.get(
            "assignment2_rules",
            "",
        ),
    )

    # ========================================================
    # OPTIONAL FAULT SIMULATION
    # ========================================================

    with st.expander(
        "⚙️ Demo / Fault Simulation",
        expanded=False,
    ):

        simulate_failure = st.selectbox(
            "Simulate model failure at",
            [
                "None",
                "Intake",
                "Planning",
                "Review",
            ],
        )

        st.caption(
            "Use this only to demonstrate the required "
            "failure-recovery workflow."
        )

    # ========================================================
    # START RUN
    # ========================================================

    run_col1, run_col2 = st.columns(
        [1, 1]
    )

    with run_col1:

        run_clicked = st.button(
            "▶️ Run Workflow",
            type="primary",
            use_container_width=True,
        )

    with run_col2:

        reset_clicked = st.button(
            "🧹 Reset",
            use_container_width=True,
        )

    if reset_clicked:

        st.session_state.assignment2_run_id = None
        st.session_state.assignment2_run = None
        st.session_state.assignment2_transcript = ""
        st.session_state.assignment2_rules = ""
        st.session_state.assignment2_session_id = "demo-session"

        st.rerun()

    if run_clicked:

        if not transcript.strip():

            st.error(
                "Meeting transcript is required."
            )

        elif not company_rules.strip():

            st.error(
                "Company rules are required."
            )

        elif not session_id.strip():

            st.error(
                "Session ID is required."
            )

        else:

            failure_value = None

            if simulate_failure != "None":
                failure_value = simulate_failure.lower()

            payload = {
                "transcript": transcript,
                "company_rules": company_rules,
                "session_id": session_id,
                "simulate_failure_at": failure_value,
            }

            st.session_state.assignment2_session_id = session_id
            st.session_state.assignment2_transcript = transcript
            st.session_state.assignment2_rules = company_rules

            with st.spinner(
                "Running Intake → Planning → Review..."
            ):

                result = api_post(
                    "/assignment2/runs",
                    payload,
                    timeout=180,
                )

            if show_api_error(
                result,
                "Assignment 2 workflow failed to start.",
            ):

                pass

            else:

                st.session_state.assignment2_run_id = (
                    result.get("run_id")
                )

                st.session_state.assignment2_run = result

                st.success(
                    f"Workflow started: "
                    f"{result.get('run_id', 'unknown')}"
                )

                st.rerun()

    # ========================================================
    # LOAD EXISTING RUN
    # ========================================================

    run_id = st.session_state.assignment2_run_id
    run = st.session_state.assignment2_run

    if run_id and run is None:

        loaded = api_get(
            f"/assignment2/runs/"
            f"{run_id}"
            f"?session_id={session_id}"
        )

        if "error" not in loaded:

            run = loaded

            st.session_state.assignment2_run = loaded

    # ========================================================
    # WORKFLOW DISPLAY
    # ========================================================

    if run:

        st.divider()

        # ----------------------------------------------------
        # RUN HEADER
        # ----------------------------------------------------

        run_header_col1, run_header_col2, run_header_col3 = (
            st.columns(3)
        )

        with run_header_col1:

            st.metric(
                "Run ID",
                run.get(
                    "run_id",
                    "unknown",
                ),
            )

        with run_header_col2:

            st.metric(
                "Session",
                run.get(
                    "session_id",
                    "unknown",
                ),
            )

        with run_header_col3:

            status = run.get(
                "status",
                "UNKNOWN",
            )

            st.metric(
                "Workflow Status",
                status,
            )

        source_version = run.get(
            "source_version",
            1,
        )

        review_attempts = run.get(
            "review_attempts",
            0,
        )

        st.caption(
            f"Source version: v{source_version} · "
            f"Review attempts: {review_attempts}"
        )

        # ====================================================
        # FAILED RUN RECOVERY
        # ====================================================

        if status == "FAILED":

            st.warning(
                "This run contains a failed workflow step. "
                "You can resume the same run."
            )

            failed_steps = [
                step
                for step in run.get("steps", [])
                if step.get("status") == "FAILED"
            ]

            if failed_steps:

                st.write("**Failed step(s)**")

                for step in failed_steps:

                    st.error(
                        f"{step.get('agent', 'unknown').title()} "
                        f"— attempt {step.get('attempt', '?')}: "
                        f"{step.get('error', 'Unknown error')}"
                    )

            if st.button(
                "▶️ Resume Failed Run",
                type="primary",
            ):

                with st.spinner(
                    "Resuming workflow..."
                ):

                    resumed = api_post(
                        "/assignment2/runs/resume",
                        {
                            "run_id": run.get("run_id"),
                            "session_id": run.get("session_id"),
                        },
                        timeout=180,
                    )

                if show_api_error(
                    resumed,
                    "Could not resume the workflow.",
                ):

                    pass

                else:

                    st.session_state.assignment2_run = resumed

                    st.success(
                        "Run resumed successfully."
                    )

                    st.rerun()

        # ====================================================
        # SOURCE FACTS
        # ====================================================

        st.subheader("📚 Current Source Facts")

        st.caption(
            "These are the structured facts currently authoritative "
            "for downstream agents."
        )

        source_facts = run.get(
            "source_facts",
            [],
        )

        if not source_facts:

            st.info(
                "No source facts have been persisted yet."
            )

        else:

            for fact in source_facts:

                fact_id = fact.get(
                    "fact_id",
                    "unknown",
                )

                category = fact.get(
                    "category",
                    "unknown",
                )

                with st.expander(
                    f"{fact_id} · "
                    f"{category.title()}",
                    expanded=False,
                ):

                    st.write(
                        fact.get(
                            "content",
                            "",
                        )
                    )

                    display_source_reference(fact)

# ========================================================
# FACT CORRECTION
# ========================================================

if source_facts:

    with st.expander(
        "✏️ Correct a Source Fact",
        expanded=False,
    ):

        # Always read the current run from session state.
        # Do not depend on a local `run` variable inside buttons.
        current_run = st.session_state.get(
            "assignment2_run"
        )

        if not current_run:

            st.warning(
                "No active Assignment 2 run."
            )

        else:

            fact_options = [
                fact.get(
                    "fact_id",
                    "unknown",
                )
                for fact in current_run.get(
                    "source_facts",
                    [],
                )
            ]

            if not fact_options:

                st.info(
                    "No source facts available to correct."
                )

            else:

                selected_fact_id = st.selectbox(
                    "Fact",
                    fact_options,
                    key="assignment2_selected_fact",
                )

                selected_fact = next(
                    (
                        fact
                        for fact in current_run.get(
                            "source_facts",
                            [],
                        )
                        if fact.get("fact_id")
                        == selected_fact_id
                    ),
                    None,
                )

                current_content = ""

                if selected_fact:

                    current_content = selected_fact.get(
                        "content",
                        "",
                    )

                corrected_content = st.text_input(
                    "Corrected fact",
                    value=current_content,
                    key="assignment2_corrected_fact",
                )

                st.caption(
                    "Correcting a fact creates a new source "
                    "version and marks previous agent outputs stale."
                )

                if st.button(
                    "Apply Fact Correction",
                    type="primary",
                    use_container_width=True,
                    key="assignment2_apply_fact_correction",
                ):

                    correction_result = api_post(
                        "/assignment2/runs/correct-fact",
                        {
                            "run_id": current_run.get(
                                "run_id"
                            ),
                            "session_id": current_run.get(
                                "session_id"
                            ),
                            "fact_id": selected_fact_id,
                            "new_content": corrected_content,
                        },
                        timeout=30,
                    )

                    if "error" in correction_result:

                        st.error(
                            "Could not correct the source fact."
                        )

                        st.code(
                            correction_result.get(
                                "error",
                                "Unknown error",
                            )
                        )

                    else:

                        # Refresh the same run.
                        refreshed = api_get(
                            f"/assignment2/runs/"
                            f"{current_run.get('run_id')}"
                            f"?session_id="
                            f"{current_run.get('session_id')}"
                        )

                        if "error" in refreshed:

                            st.error(
                                "Fact was corrected, but the "
                                "updated run could not be loaded."
                            )

                            st.code(
                                refreshed.get(
                                    "error",
                                    "Unknown error",
                                )
                            )

                        else:

                            st.session_state.assignment2_run = (
                                refreshed
                            )

                            st.session_state.assignment2_run_id = (
                                refreshed.get("run_id")
                            )

                            st.success(
                                f"Source fact corrected. "
                                f"Source version is now "
                                f"v{refreshed.get('source_version')}."
                            )

                            st.rerun()

            # ------------------------------------------------
            # RERUN STALE WORKFLOW
            # ------------------------------------------------

            latest_run = st.session_state.get(
                "assignment2_run"
            )

            if latest_run:

                latest_status = latest_run.get(
                    "status"
                )

                latest_version = latest_run.get(
                    "source_version",
                    1,
                )

                has_stale_steps = any(
                    step.get("status") == "STALE"
                    for step in latest_run.get(
                        "steps",
                        [],
                    )
                )

                if (
                    latest_version > 1
                    and has_stale_steps
                    and latest_status == "RUNNING"
                ):

                    st.divider()

                    st.warning(
                        f"Source facts changed to v{latest_version}. "
                        "Previous agent outputs are stale."
                    )

                    if st.button(
                        "▶️ Rerun Corrected Workflow",
                        type="primary",
                        use_container_width=True,
                        key="assignment2_rerun_corrected",
                    ):

                        # IMPORTANT:
                        # Read the run directly from session state
                        # inside the button action.
                        rerun_run = st.session_state.get(
                            "assignment2_run"
                        )

                        if not rerun_run:

                            st.error(
                                "No active run available."
                            )

                        else:

                            with st.spinner(
                                "Rerunning Intake → Planning → Review "
                                "using the corrected source facts..."
                            ):

                                resumed = api_post(
                                    "/assignment2/runs/resume",
                                    {
                                        "run_id": rerun_run.get(
                                            "run_id"
                                        ),
                                        "session_id": rerun_run.get(
                                            "session_id"
                                        ),
                                    },
                                    timeout=180,
                                )

                            if "error" in resumed:

                                st.error(
                                    "Could not rerun the corrected workflow."
                                )

                                st.code(
                                    resumed.get(
                                        "error",
                                        "Unknown error",
                                    )
                                )

                            else:

                                st.session_state.assignment2_run = (
                                    resumed
                                )

                                st.session_state.assignment2_run_id = (
                                    resumed.get("run_id")
                                )

                                st.success(
                                    "Corrected workflow completed."
                                )

                                st.rerun()

        # ====================================================
        # WORKFLOW TRACE
        # ====================================================

        st.divider()

        st.subheader("🔎 Agent Workflow")

        intake_steps = get_agent_steps(
            run,
            "intake",
        )

        planning_steps = get_agent_steps(
            run,
            "planning",
        )

        review_steps = get_agent_steps(
            run,
            "review",
        )

        # ----------------------------------------------------
        # INTAKE
        # ----------------------------------------------------

        intake_step = intake_steps[-1] if intake_steps else None

        with st.expander(
            "1️⃣ Intake Agent",
            expanded=True,
        ):

            if not intake_step:

                st.info(
                    "Intake has not run yet."
                )

            else:

                intake_status = intake_step.get(
                    "status",
                    "UNKNOWN",
                )

                st.write(
                    f"{status_icon(intake_status)} "
                    f"Status: **{intake_status}**"
                )

                st.caption(
                    f"Attempt {intake_step.get('attempt', '?')} · "
                    f"Input version "
                    f"v{intake_step.get('input_version', '?')} · "
                    f"Output version "
                    f"v{intake_step.get('output_version', '?')}"
                )

                if intake_step.get("error"):

                    st.error(
                        intake_step["error"]
                    )

                intake_output = (
                    intake_step.get(
                        "output_data"
                    )
                    or {}
                )

                if intake_output:

                    intake_col1, intake_col2 = st.columns(2)

                    with intake_col1:

                        st.write("**Decisions**")

                        decisions = intake_output.get(
                            "decisions",
                            [],
                        )

                        if decisions:

                            for fact in decisions:

                                st.write(
                                    format_fact(fact)
                                )

                                display_source_reference(
                                    fact
                                )

                        else:

                            st.caption(
                                "None identified."
                            )

                        st.write("**Requirements**")

                        requirements = intake_output.get(
                            "requirements",
                            [],
                        )

                        if requirements:

                            for fact in requirements:

                                st.write(
                                    format_fact(fact)
                                )

                                display_source_reference(
                                    fact
                                )

                        else:

                            st.caption(
                                "None identified."
                            )

                    with intake_col2:

                        st.write("**Constraints**")

                        constraints = intake_output.get(
                            "constraints",
                            [],
                        )

                        if constraints:

                            for fact in constraints:

                                st.write(
                                    format_fact(fact)
                                )

                                display_source_reference(
                                    fact
                                )

                        else:

                            st.caption(
                                "None identified."
                            )

                        st.write(
                            "**Missing information**"
                        )

                        missing_information = (
                            intake_output.get(
                                "missing_information",
                                [],
                            )
                        )

                        if missing_information:

                            for item in missing_information:

                                st.write(
                                    f"• {item}"
                                )

                        else:

                            st.caption(
                                "None identified."
                            )

                        st.write("**Conflicts**")

                        conflicts = intake_output.get(
                            "conflicts",
                            [],
                        )

                        if conflicts:

                            for item in conflicts:

                                st.warning(
                                    item
                                )

                        else:

                            st.caption(
                                "None identified."
                            )

        # ----------------------------------------------------
        # INTAKE → PLANNING HANDOFF
        # ----------------------------------------------------

        intake_handoffs = [
            handoff
            for handoff in run.get("handoffs", [])
            if (
                handoff.get("from_agent") == "intake"
                and handoff.get("to_agent") == "planning"
            )
        ]

        if intake_handoffs:

            latest_handoff = intake_handoffs[-1]

            st.caption(
                "🔗 Intake → Planning · "
                f"v{latest_handoff.get('input_version', '?')} → "
                f"v{latest_handoff.get('output_version', '?')} · "
                f"{latest_handoff.get('validation_status', 'UNKNOWN')}"
            )

        # ----------------------------------------------------
        # PLANNING
        # ----------------------------------------------------

        with st.expander(
            "2️⃣ Planning Agent",
            expanded=True,
        ):

            if not planning_steps:

                st.info(
                    "Planning has not run yet."
                )

            else:

                for index, planning_step in enumerate(
                    planning_steps
                ):

                    if len(planning_steps) > 1:

                        st.markdown(
                            f"**Planning attempt "
                            f"{planning_step.get('attempt', index + 1)}**"
                        )

                    planning_status = planning_step.get(
                        "status",
                        "UNKNOWN",
                    )

                    st.write(
                        f"{status_icon(planning_status)} "
                        f"Status: **{planning_status}**"
                    )

                    st.caption(
                        f"Input version "
                        f"v{planning_step.get('input_version', '?')} · "
                        f"Output version "
                        f"v{planning_step.get('output_version', '?')}"
                    )

                    if planning_step.get("error"):

                        st.error(
                            planning_step["error"]
                        )

                    planning_output = (
                        planning_step.get(
                            "output_data"
                        )
                        or {}
                    )

                    tasks = planning_output.get(
                        "tasks",
                        [],
                    )

                    if tasks:

                        for task in tasks:

                            task_id = task.get(
                                "task_id",
                                "unknown",
                            )

                            task_name = task.get(
                                "task",
                                "Unnamed task",
                            )

                            owner = task.get(
                                "owner"
                            )

                            deadline = task.get(
                                "deadline"
                            )

                            dependencies = task.get(
                                "dependencies",
                                [],
                            )

                            basis = task.get(
                                "basis",
                                "unknown",
                            )

                            st.markdown(
                                f"**{task_id} — {task_name}**"
                            )

                            task_col1, task_col2, task_col3, task_col4 = (
                                st.columns(4)
                            )

                            with task_col1:

                                st.write(
                                    "**Owner**"
                                )

                                st.write(
                                    owner or "Unassigned"
                                )

                            with task_col2:

                                st.write(
                                    "**Deadline**"
                                )

                                st.write(
                                    deadline or "Not specified"
                                )

                            with task_col3:

                                st.write(
                                    "**Dependencies**"
                                )

                                if dependencies:

                                    st.write(
                                        ", ".join(
                                            dependencies
                                        )
                                    )

                                else:

                                    st.write(
                                        "None"
                                    )

                            with task_col4:

                                st.write(
                                    "**Basis**"
                                )

                                st.write(
                                    basis.replace(
                                        "_",
                                        " ",
                                    ).title()
                                )

                            st.divider()

                    else:

                        st.caption(
                            "No tasks produced."
                        )

                    supported_facts = planning_output.get(
                        "supported_facts",
                        [],
                    )

                    recommendations = planning_output.get(
                        "recommendations",
                        [],
                    )

                    unresolved_questions = planning_output.get(
                        "unresolved_questions",
                        [],
                    )

                    if supported_facts:

                        st.write(
                            "**Supported facts**"
                        )

                        for item in supported_facts:

                            st.write(
                                f"• {item}"
                            )

                    if recommendations:

                        st.write(
                            "**Recommendations**"
                        )

                        for item in recommendations:

                            st.write(
                                f"• {item}"
                            )

                    if unresolved_questions:

                        st.write(
                            "**Unresolved questions**"
                        )

                        for item in unresolved_questions:

                            st.write(
                                f"• {item}"
                            )

                    if index < len(planning_steps) - 1:

                        st.divider()

        # ----------------------------------------------------
        # PLANNING → REVIEW HANDOFF
        # ----------------------------------------------------

        planning_handoffs = [
            handoff
            for handoff in run.get("handoffs", [])
            if (
                handoff.get("from_agent") == "planning"
                and handoff.get("to_agent") == "review"
            )
        ]

        if planning_handoffs:

            latest_handoff = planning_handoffs[-1]

            st.caption(
                "🔗 Planning → Review · "
                f"v{latest_handoff.get('input_version', '?')} → "
                f"v{latest_handoff.get('output_version', '?')} · "
                f"{latest_handoff.get('validation_status', 'UNKNOWN')}"
            )

        # ----------------------------------------------------
        # REVIEW
        # ----------------------------------------------------

        with st.expander(
            "3️⃣ Review Agent",
            expanded=True,
        ):

            if not review_steps:

                st.info(
                    "Review has not run yet."
                )

            else:

                for index, review_step in enumerate(
                    review_steps
                ):

                    if len(review_steps) > 1:

                        st.markdown(
                            f"**Review attempt "
                            f"{review_step.get('attempt', index + 1)}**"
                        )

                    review_status = review_step.get(
                        "status",
                        "UNKNOWN",
                    )

                    st.write(
                        f"{status_icon(review_status)} "
                        f"Step status: **{review_status}**"
                    )

                    review_output = (
                        review_step.get(
                            "output_data"
                        )
                        or {}
                    )

                    if review_step.get("error"):

                        st.error(
                            review_step["error"]
                        )

                    if review_output:

                        decision = review_output.get(
                            "status",
                            "UNKNOWN",
                        )

                        if decision == "PASS":

                            st.success(
                                "REVIEW PASS"
                            )

                        elif decision == "FAIL":

                            st.error(
                                "REVIEW FAIL"
                            )

                        corrections = review_output.get(
                            "corrections",
                            [],
                        )

                        if corrections:

                            st.write(
                                "**Corrections sent back to Planning**"
                            )

                            for correction in corrections:

                                issue = correction.get(
                                    "issue",
                                    "",
                                )

                                task_id = correction.get(
                                    "task_id"
                                )

                                correction_text = correction.get(
                                    "correction",
                                    "",
                                )

                                evidence = correction.get(
                                    "evidence",
                                    "",
                                )

                                st.warning(
                                    f"**Issue:** {issue}"
                                )

                                if task_id:

                                    st.write(
                                        f"**Task:** {task_id}"
                                    )

                                st.write(
                                    f"**Correction:** "
                                    f"{correction_text}"
                                )

                                if evidence:

                                    st.caption(
                                        f"Evidence: {evidence}"
                                    )

                        unresolved_issues = review_output.get(
                            "unresolved_issues",
                            [],
                        )

                        if unresolved_issues:

                            st.write(
                                "**Unresolved issues**"
                            )

                            for issue in unresolved_issues:

                                st.warning(
                                    issue
                                )

                    if index < len(review_steps) - 1:

                        st.divider()

        # ----------------------------------------------------
        # REVIEW → PLANNING CORRECTION HANDOFF
        # ----------------------------------------------------

        correction_handoffs = [
            handoff
            for handoff in run.get("handoffs", [])
            if (
                handoff.get("from_agent") == "review"
                and handoff.get("to_agent") == "planning"
            )
        ]

        if correction_handoffs:

            st.caption(
                f"↩️ Review → Planning corrections: "
                f"{len(correction_handoffs)}"
            )

            latest_correction = correction_handoffs[-1]

            with st.expander(
                "View latest correction handoff",
                expanded=False,
            ):

                st.json(
                    latest_correction.get(
                        "payload",
                        {},
                    )
                )

        # ====================================================
        # HANDOFF TRACE
        # ====================================================

        st.divider()

        st.subheader("🔗 Handoff Trace")

        handoffs = run.get(
            "handoffs",
            [],
        )

        if not handoffs:

            st.info(
                "No handoffs recorded."
            )

        else:

            for handoff in handoffs:

                from_agent = handoff.get(
                    "from_agent",
                    "unknown",
                )

                to_agent = handoff.get(
                    "to_agent",
                    "unknown",
                )

                validation = handoff.get(
                    "validation_status",
                    "UNKNOWN",
                )

                input_version = handoff.get(
                    "input_version",
                    "?",
                )

                output_version = handoff.get(
                    "output_version",
                    "?",
                )

                if validation == "VALID":

                    st.success(
                        f"{from_agent.title()} → "
                        f"{to_agent.title()} · "
                        f"VALID · "
                        f"v{input_version} → v{output_version}"
                    )

                else:

                    st.error(
                        f"{from_agent.title()} → "
                        f"{to_agent.title()} · "
                        f"{validation} · "
                        f"v{input_version} → v{output_version}"
                    )

        # ====================================================
        # FINAL PLAN
        # ====================================================

        st.divider()

        st.subheader("📋 Final Plan")

        final_plan = run.get(
            "final_plan"
        )

        if final_plan:

            final_tasks = final_plan.get(
                "tasks",
                [],
            )

            if final_tasks:

                for task in final_tasks:

                    task_id = task.get(
                        "task_id",
                        "unknown",
                    )

                    task_name = task.get(
                        "task",
                        "Unnamed task",
                    )

                    owner = task.get(
                        "owner"
                    )

                    deadline = task.get(
                        "deadline"
                    )

                    dependencies = task.get(
                        "dependencies",
                        [],
                    )

                    basis = task.get(
                        "basis",
                        "unknown",
                    )

                    st.markdown(
                        f"### {task_id} — {task_name}"
                    )

                    final_col1, final_col2, final_col3, final_col4 = (
                        st.columns(4)
                    )

                    with final_col1:

                        st.write("**Owner**")

                        st.write(
                            owner or "Unassigned"
                        )

                    with final_col2:

                        st.write("**Deadline**")

                        st.write(
                            deadline or "Not specified"
                        )

                    with final_col3:

                        st.write("**Dependencies**")

                        if dependencies:

                            st.write(
                                ", ".join(
                                    dependencies
                                )
                            )

                        else:

                            st.write(
                                "None"
                            )

                    with final_col4:

                        st.write("**Basis**")

                        st.write(
                            basis.replace(
                                "_",
                                " ",
                            ).title()
                        )

                    st.divider()

            else:

                st.info(
                    "The workflow completed without "
                    "a final task list."
                )

        else:

            if status == "UNRESOLVED":

                st.warning(
                    "The review loop reached its bounded attempt "
                    "limit. No final plan was accepted."
                )

            elif status == "FAILED":

                st.warning(
                    "The run has not produced a final plan. "
                    "Resume the failed run above."
                )

            else:

                st.info(
                    "A final plan will appear after "
                    "Review passes."
                )

        # ====================================================
        # REFRESH / LOAD RUN
        # ====================================================

        st.divider()

        refresh_col1, refresh_col2 = st.columns(2)

        with refresh_col1:

            if st.button(
                "🔄 Refresh Run",
                use_container_width=True,
            ):

                refreshed = api_get(
                    f"/assignment2/runs/"
                    f"{run.get('run_id')}"
                    f"?session_id={run.get('session_id')}"
                )

                if show_api_error(
                    refreshed,
                    "Could not refresh the run.",
                ):

                    pass

                else:

                    st.session_state.assignment2_run = (
                        refreshed
                    )

                    st.rerun()

        with refresh_col2:

            if st.button(
                "🆕 Start New Run",
                use_container_width=True,
            ):

                st.session_state.assignment2_run_id = None
                st.session_state.assignment2_run = None

                st.rerun()
            else:

        # ====================================================
        # EMPTY ASSIGNMENT 2 STATE
        # ====================================================

                st.divider()

                st.info(
            "Enter a meeting transcript and company rules, "
            "then run the workflow."
            )

                st.markdown(
            """
            **Workflow**

            `Meeting Transcript`
            → **Intake Agent**
            → **Planning Agent**
            → **Review Agent**
            → `Final Plan`

            If Review finds a problem, the correction is sent
            back to Planning and the bounded review loop runs again.
            """
            )