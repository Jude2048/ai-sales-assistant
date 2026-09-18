## Demo Access Instructions

Open the deployed Streamlit application using the provided demo URL.

## Demo Access — Instagram

The Instagram integration is connected to the following test business account:

**Instagram:** `@client.ai.test`

To test the Instagram workflow:

1. Open the Instagram account above.
2. Send a direct message to the account using the provided demo/test account.
3. The message is received through the Meta webhook.
4. The FastAPI backend processes the inquiry and stores it as a lead.
5. Open the Streamlit UI and select **`1 — Lead Qualification & Booking`**.
6. Refresh the lead list and select the newly received lead.
7. Continue through qualification, representative assignment, and meeting booking.

> **Note:** The Instagram account is a test/demo business account used for the assignment. Availability of the messaging workflow depends on Meta test-account permissions and configuration.

### Email Demo

The email integration is connected to the following test/demo inbox:

**Email:** `YOUR_DEMO_EMAIL@example.com`

To test the email workflow:

1. Send an email inquiry to the address above.
2. The Gmail integration retrieves the incoming message.
3. The FastAPI backend processes the inquiry and stores it as a lead.
4. Open the Streamlit UI and select **`1 — Lead Qualification & Booking`**.
5. Refresh the lead list and select the newly received lead.
6. Continue through qualification, representative assignment, and meeting booking.

> **Note:** This is a test/demo inbox configured for the assignment. The email workflow depends on the configured Gmail API credentials and permissions.

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