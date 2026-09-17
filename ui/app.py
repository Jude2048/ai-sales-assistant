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
# HELPERS
# ============================================================

def api_get(path):
    try:
        response = requests.get(
            f"{API_URL}{path}",
            timeout=10,
        )

        if response.ok:
            return response.json()

        return {"error": response.text}

    except Exception as e:
        return {"error": str(e)}


def api_post(path, data=None):
    try:
        response = requests.post(
            f"{API_URL}{path}",
            json=data or {},
            timeout=10,
        )

        if response.ok:
            return response.json()

        return {"error": response.text}

    except Exception as e:
        return {"error": str(e)}


# ============================================================
# HEADER
# ============================================================

st.title("AI Sales Assistant")

st.caption(
    "Unified interface for Mudita AI Generalist Assignments"
)


# ============================================================
# ASSIGNMENT TOGGLE
# ============================================================

assignment = st.radio(
    "Assignment",
    [
        "Assignment 1 — Lead Qualification & Booking",
        "Assignment 2 — AI Sales Workflow",
    ],
    horizontal=True,
)


st.divider()


# ============================================================
# ASSIGNMENT 1
# ============================================================

if assignment.startswith("Assignment 1"):

    st.header("Assignment 1")

    # --------------------------------------------------------
    # Sidebar
    # --------------------------------------------------------

    st.sidebar.header("Controls")

    if st.sidebar.button("🔄 Refresh"):
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
        st.subheader("📥 Unified Inbox")

        leads_response = api_get("/api/leads")

        if "error" in leads_response:
            st.error(leads_response["error"])
        else:
            lead_list = leads_response.get("leads", [])

            if not lead_list:
                st.info("No leads found.")
            else:
                for lead in lead_list:
                    lead_id = lead.get("lead_id", "")
                    channel = lead.get("channel", "").upper()
                    status = lead.get("status", "new")

                    if st.button(
                        f"{channel} — {lead_id} — {status}",
                        key=f"lead_{lead_id}",
                        use_container_width=True,
                    ):
                        st.session_state["selected_lead"] = lead_id
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
                    []
                )

                for message in messages:

                    direction = message.get(
                        "direction"
                    )

                    content = message.get(
                        "content",
                        ""
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
                f"/leads/{selected_lead}"
            )

            if "error" in lead:

                st.info(
                    "Lead detail endpoint not available yet."
                )

            else:

                status = lead.get(
                    "status",
                    "unknown"
                )

                st.metric(
                    "Qualification",
                    status,
                )

                assignment_data = lead.get(
                    "assignment",
                    {}
                )

                st.write(
                    "**Representative:**",
                    assignment_data.get(
                        "representative",
                        "Unassigned"
                    ),
                )

                qualification = lead.get(
                    "qualification",
                    {}
                )

                st.write("**Evidence**")

                evidence = qualification.get(
                    "evidence",
                    []
                )

                for item in evidence:
                    st.write(f"• {item}")

                st.divider()

                # Human takeover
                automation_enabled = lead.get(
                    "automation_enabled",
                    True
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
                {}
            )

            meeting_status = lead.get(
                "meeting_status",
                pending.get(
                    "status",
                    "none"
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
                []
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

    st.info(
        "Assignment 2 workspace"
    )

    st.write(
        "The same application will host the Assignment 2 "
        "workflow here."
    )

    st.divider()

    st.subheader("Assignment 2")

    st.caption(
        "Backend and workflow components will be connected "
        "to this workspace."
    )