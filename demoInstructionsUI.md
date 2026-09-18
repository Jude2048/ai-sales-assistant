## Demo Access Instructions

Open the deployed Streamlit application using the provided demo URL.

### Assignment 1 — Lead Qualification & Booking

1. Select **`1 — Lead Qualification & Booking`** from the assignment selector.
2. Use the **Refresh** control to load the current leads.
3. Select a lead from the **Unified Inbox**.
4. Review the conversation, lead details, qualification evidence, and representative assignment.
5. Use the booking section to check calendar availability and book a meeting.
6. Review the **Action Log** to confirm the workflow actions were recorded.

### Assignment 1 → Assignment 2

1. Select a lead that has a booked meeting.
2. Use **`Send to Ops Coordinator`**.
3. The system creates an Assignment 2 run linked to the source lead and booking.
4. The meeting transcript shown in Assignment 2 is clearly labelled as:
   
   **Synthetic test transcript — fictional data for assignment demonstration**
5. The Assignment 1 qualification evidence and company rules are passed into the Assignment 2 workflow.

### Assignment 2 — AI Sales Workflow

1. Select **`2 — AI Sales Workflow`**.
2. Enter or use the provided **Session ID**.
3. Review the fictional meeting transcript and company rules.
4. Click **Run Workflow**.
5. Observe the three agent stages:
   - **Intake Agent**
   - **Planning Agent**
   - **Review Agent**
6. Review the **Workflow Trace** and agent handoffs.
7. Review the generated **Final Plan**.

### Reliability Demonstrations

Use the **Simulate Failure** control to demonstrate recovery:

- Select **Planning** and run the workflow.
- Confirm the run enters a failed state.
- Click **Resume / Recover**.
- Confirm the workflow resumes from the failed step without restarting completed work.

Use **Fact Correction** to demonstrate change propagation:

1. Select a source fact.
2. Change its value.
3. Submit the correction.
4. Confirm the previous agent outputs become **STALE**.
5. Rerun the workflow.
6. Confirm the corrected fact propagates through Intake → Planning → Review.

Each Assignment 2 run is associated with a **session ID**, allowing separate sessions to be tested independently.