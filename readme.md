# AI Sales Assistant & Operations Coordinator

A focused AI prototype combining two connected workflows:

1. **Assignment 1 — Sales Assistant:** turns incoming inquiries from Instagram, WhatsApp and email into qualified, assigned leads and confirmed calendar meetings.
2. **Assignment 2 — Operations Coordinator:** turns a fictional meeting transcript and company rules into a reviewed action plan using three distinct LLM-powered agents.

# Architecture

The project uses a FastAPI backend, Streamlit frontend, MongoDB Atlas for persistence, and Google Gemini for LLM-powered functionality.

## High-Level Architecture

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

## Application Flow

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

## Persistence and Context Management

Assignment 2 maintains persistent workflow state using:

- `run_id` — identifies an individual workflow run.
- `session_id` — isolates one user/session from another.
- `source_version` — identifies the current version of the source facts.
- `source_facts` — stores extracted and corrected facts.
- `agent_steps` — stores each agent execution, attempt, input version, output version and status.
- `agent_handoffs` — stores the information passed between agents and its validation status.

When a source fact is corrected, the source version is incremented and previous outputs based on the older version are marked as stale. The affected workflow can then be rerun using the corrected source context.

## Reliability

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

run_id
session_id
source_version
transcript
company_rules
source_facts
steps
handoffs
status
final_plan

Each agent step contains:

step_id
run_id
agent
attempt
input_version
output_version
status
input_data
output_data
error

Each handoff contains:

handoff_id
run_id
from_agent
to_agent
input_version
output_version
payload
validation_status

Session Isolation

Every Assignment 2 run contains a session_id.

Session A
   └── Run A
       └── Client A Context


Session B
   └── Run B
       └── Client B Context

Runs are retrieved using both:

run_id
session_id

## Setup

### Prerequisites

- Python 3.10+
- MongoDB Atlas account
- Google Gemini API key
- Git
- Railway account (for deployment)

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <PROJECT_DIRECTORY>

3. Install dependencies

Install the backend dependencies:

pip install -r api/requirements.txt

Install the Streamlit/UI dependencies if they are maintained separately:

pip install -r ui/requirements.txt

4. Configure environment variables
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

5. Run the FastAPI backend

From the project root:

uvicorn api.main:app --reload

The API will normally be available at:

http://localhost:8000

FastAPI documentation:

http://localhost:8000/docs
6. Run the Streamlit frontend

In a second terminal, with the virtual environment activated:

streamlit run ui/ui.py

The Streamlit interface will normally be available at:

http://localhost:8501

7. External integrations

For production/demo deployment, the following integrations can be configured through their respective environment variables:

Instagram: Meta Graph API and webhook configuration.
WhatsApp: Twilio WhatsApp Sandbox/webhook configuration.
Email: Gmail API credentials.
Calendar: Google Calendar API credentials.
Database: MongoDB Atlas.
LLM: Google Gemini API.

8. Railway deployment

The production application is deployed using Railway.

Configure the same required environment variables in the Railway service settings rather than committing them to the repository.

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


