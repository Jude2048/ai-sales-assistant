# AI Sales Assistant & Operations Coordinator

A focused AI prototype combining two connected workflows:

1. **Assignment 1 — Sales Assistant:** turns incoming inquiries from Instagram, WhatsApp and email into qualified, assigned leads and confirmed calendar meetings.
2. **Assignment 2 — Operations Coordinator:** turns a fictional meeting transcript and company rules into a reviewed action plan using three distinct LLM-powered agents.

## Tech Stack

- **Frontend:** Streamlit
- **Backend:** FastAPI
- **Database:** MongoDB Atlas
- **LLM:** Google Gemini (`gemini-3.1-flash-lite`)
- **Integrations:** Meta Graph API, Twilio, Gmail API, Google Calendar API
- **Deployment:** Railway

## Architecture

The project uses a FastAPI backend, Streamlit frontend, MongoDB Atlas for persistence, and Google Gemini for LLM-powered functionality.

### High-Level Architecture

The Streamlit UI communicates with the FastAPI backend through REST API endpoints.

Assignment 1 receives inquiries from three channels:

- Instagram through Meta webhooks
- WhatsApp through Twilio
- Email through Gmail API

Incoming messages are processed by FastAPI and persisted in MongoDB. Gemini is used to understand the conversation and extract structured information. Qualification and representative routing are handled through deterministic business-policy logic.

Confirmed meetings use Google Calendar for availability checks and booking.

Once a meeting is confirmed, the Assignment 1 workflow can pass the lead and booking information to Assignment 2 through the shared bridge.

Assignment 2 creates a persistent agent run using the meeting information, company rules and a clearly labelled synthetic meeting transcript.

The Assignment 2 workflow consists of three distinct LLM-powered agents:

1. **Intake Agent** — extracts decisions, requirements, constraints, missing information and conflicts from the transcript.
2. **Planning Agent** — converts the structured intake information and company rules into tasks, owners, deadlines and dependencies.
3. **Review Agent** — checks the proposed plan against the transcript and company rules and sends corrections back to the Planning Agent when required.

MongoDB stores Assignment 2 runs, source facts, agent steps and agent handoffs so that workflows can be inspected, resumed and versioned.

### Application Flow

### Assignment 1

Instagram / WhatsApp / Gmail  
→ FastAPI  
→ MongoDB  
→ Gemini conversation understanding  
→ Qualification  
→ Deterministic routing  
→ Google Calendar availability  
→ Explicit confirmation  
→ Calendar booking


The synthetic transcript is clearly labelled:

**Synthetic test transcript — fictional data for assignment demonstration**

### Assignment 2

Meeting transcript + company rules  
→ Intake Agent  
→ Structured Intake Output  
→ Planning Agent  
→ Proposed Action Plan  
→ Review Agent  
→ PASS or Corrections  
→ Planning revision when required  
→ Final Action Plan

### Persistence and Context Management

Assignment 2 maintains persistent workflow state using:

- `run_id` — identifies an individual workflow run.
- `session_id` — isolates one user/session from another.
- `source_version` — identifies the current version of the source facts.
- `source_facts` — stores extracted and corrected facts.
- `agent_steps` — stores each agent execution, attempt, input version, output version and status.
- `agent_handoffs` — stores the information passed between agents and its validation status.

When a source fact is corrected, the source version is incremented and previous outputs based on the older version are marked as stale. The affected workflow can then be rerun using the corrected source context.

### Reliability

The system includes:

- Structured Pydantic schemas for agent inputs and outputs.
- Handoff validation between agents.
- Bounded Review → Planning correction loops.
- Persistent workflow state.
- Failed-step recovery.
- Source-fact versioning.
- Stale-output detection.
- Session isolation.
- Calendar availability rechecks.
- Duplicate booking protection.
- Human takeover for Assignment 1 automation.

The implementation intentionally avoids additional distributed orchestration infrastructure because the assignment requires a focused prototype rather than a production system.
Assignment 2 Persistence


agent_runs
agent_steps
agent_handoffs
source_facts

A run contains:

- `run_id`
- `session_id`
- `source_version`
- `transcript`
- `company_rules`
- `source_facts`
- `steps`
- `handoffs`
- `status`
- `final_plan`

Each agent step contains:

- `step_id`
- `run_id`
- `agent`
- `attempt`
- `input_version`
- `output_version`
- `status`
- `input_data`
- `output_data`
- `error`

Each handoff contains:

- `handoff_id`
- `run_id`
- `from_agent`
- `to_agent`
- `input_version`
- `output_version`
- `payload`
- `validation_status`

### Session Isolation

Every Assignment 2 run contains a `session_id`.

- **Session A** → Run A → Client A Context
- **Session B** → Run B → Client B Context

Runs are retrieved using both `run_id` and `session_id`.



## Project Structure

```text
/api
  /assignment1
  /assignment2
  /webhooks
  main.py

/ui
  ui.py

/shared
  shared models and utilities

README.md
```

## Setup

### Prerequisites

- Python 3.10+
- Git
- MongoDB Atlas account
- Google Gemini API key
- Railway account (for deployment)

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <PROJECT_DIRECTORY>
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r api/requirements.txt
```

If the UI has a separate requirements file:

```bash
pip install -r ui/requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file. Do not commit it to Git.

```env
GEMINI_API_KEY=<your_gemini_api_key>
MONGODB_URI=<your_mongodb_atlas_connection_string>

GOOGLE_CLIENT_ID=<your_google_client_id>
GOOGLE_CLIENT_SECRET=<your_google_client_secret>
GOOGLE_REFRESH_TOKEN=<your_google_refresh_token>

META_ACCESS_TOKEN=<your_meta_access_token>
META_VERIFY_TOKEN=<your_meta_verify_token>

TWILIO_ACCOUNT_SID=<your_twilio_account_sid>
TWILIO_AUTH_TOKEN=<your_twilio_auth_token>
TWILIO_WHATSAPP_NUMBER=<your_twilio_whatsapp_number>
```


### 5. MongoDB Atlas

Create a MongoDB Atlas database and provide its connection string through `MONGODB_URI`.

MongoDB is used for lead data, conversations, bookings, actions, and Assignment 2 workflow persistence.

### 6. Gemini

Create a Google Gemini API key and configure `GEMINI_API_KEY`.

Assignment 2 uses Gemini for the Intake, Planning, and Review agents.

### 7. Run the FastAPI backend

From the project root:

```bash
uvicorn api.main:app --reload
```

The API will normally be available at `http://localhost:8000`.

FastAPI documentation is available at `http://localhost:8000/docs`.

### 8. Run the Streamlit frontend

In a second terminal:

```bash
streamlit run ui/ui.py
```

The Streamlit interface will normally be available at `http://localhost:8501`.

### 9. External integrations

The production/demo workflow can use:

- **Instagram:** Meta Graph API and webhooks
- **WhatsApp:** Twilio WhatsApp Sandbox
- **Email:** Gmail API
- **Calendar:** Google Calendar API
- **Database:** MongoDB Atlas
- **LLM:** Google Gemini

Webhook URLs must point to the deployed FastAPI application rather than the local development server.

### 10. Railway deployment

The production application is deployed using Railway.

Configure the required environment variables in Railway service settings rather than committing them to the repository.

For the deployed application, verify:

1. The FastAPI health endpoint responds successfully.
2. `/docs` is accessible.
3. The Streamlit UI loads successfully.
4. MongoDB connectivity works.
5. Assignment 1 lead qualification and booking work.
6. The Assignment 1 → Assignment 2 bridge creates a run.
7. Assignment 2 completes the Intake → Planning → Review workflow.


## Testing

The main demonstration scenarios are:

1. **Normal end-to-end run** — Intake → Planning → Review → final plan.
2. **Rule violation and correction** — Review identifies an issue and the plan is revised.
3. **Fact correction and propagation** — corrected source facts invalidate stale outputs and propagate through the workflow.
4. **Simulated failure and recovery** — a selected agent fails and the run resumes from the failed step.
5. **Session isolation** — separate sessions maintain independent workflow state.

## Demo Access Instructions

Open the deployed Streamlit application using the provided demo URL.

### Assignment 1 — Lead Qualification & Booking

1. Select **`1 — Lead Qualification & Booking`**.
2. Refresh the lead list and select a lead from the Unified Inbox.
3. Review the conversation, qualification evidence, representative assignment, and action log.
4. Use the booking section to check calendar availability and book a meeting.

### Assignment 1 → Assignment 2

1. Select a lead with a booked meeting.
2. Use **`Send to Ops Coordinator`**.
3. The system creates an Assignment 2 run linked to the source lead and booking.
4. The meeting information is passed into Assignment 2 with the clearly labelled:
   **Synthetic test transcript — fictional data for assignment demonstration**.

### Assignment 2 — AI Sales Workflow

1. Select **`2 — AI Sales Workflow`**.
2. Enter or use the provided session ID.
3. Review the transcript and company rules.
4. Click **Run Workflow**.
5. Inspect the Intake, Planning, and Review stages, workflow trace, handoffs, and final plan.

### Reliability Demonstrations

- **Simulated failure:** select Intake, Planning, or Review, run the workflow, then use **Resume / Recover**.
- **Fact correction:** edit a source fact, submit the correction, and rerun the workflow to observe stale outputs and propagation of the corrected context.
- **Session isolation:** use different session IDs to verify that runs remain isolated.

## Approximate Model Cost

Assignment 2 uses Google's `gemini-3.1-flash-lite` model through the Gemini API.

The project is currently configured to use the Gemini API Free Tier, where Gemini 3.1 Flash-Lite has no charge for input or output tokens. Therefore, the estimated LLM cost for a typical Assignment 2 workflow is approximately **$0 per run**, subject to Google's current Free Tier quotas and limits.

A normal workflow typically makes approximately 3 model calls:

- Intake Agent: 1 call
- Planning Agent: 1 call
- Review Agent: 1 call

If the Review Agent identifies corrections, the workflow may perform additional Planning and Review calls, resulting in approximately 5 model calls for that run.


## Known Limitations

This project is intentionally a focused prototype rather than a production system.

- External messaging integrations depend on provider test-account configuration and permissions.
- WhatsApp uses the Twilio Sandbox/test environment.
- Instagram requires the appropriate Meta test configuration and permissions.
- Gmail uses a configured test account.
- Assignment 2 uses a synthetic fictional meeting transcript for demonstration.
- Simulated failures are demonstration controls rather than real infrastructure failures.
- The agent orchestration is intentionally lightweight and does not use a distributed task queue.
- The application is designed for the assignment demonstration scope rather than production-scale concurrency.
- Calendar reliability is implemented around the test-calendar workflow rather than a full production scheduling platform.

## AI Usage Disclosure

AI coding tools were used during development to assist with implementation, debugging, architecture review, and documentation.

The application itself uses Google Gemini for LLM-powered functionality.

Assignment 2 contains three distinct agent stages:

1. **Intake Agent**
   - Extracts decisions, requirements, constraints, missing information, conflicts, and source references.

2. **Planning Agent**
   - Converts validated intake information and company rules into a structured operational plan.

3. **Review Agent**
   - Checks the proposed plan against the source transcript and company rules and identifies required corrections.

Each agent has a separate responsibility, structured input/output schema, and persisted workflow state.

The project does not rely on an agent framework to simulate collaboration. The orchestration and state management are implemented directly in the application.


