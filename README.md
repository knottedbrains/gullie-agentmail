# gullie-agentmail

A Gmail agent that can send emails and summarize the latest inbox message.

## Quick Start

### Prerequisites

- Python 3.7+
- A Gmail account
- Google Cloud Project with Gmail API enabled

### Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up Google Cloud credentials:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable the Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download the credentials JSON file and save it as `credentials.json` in the project root
   - (Optional) Add your OpenAI API key inside the file under `openai_api_key` or set the `OPENAI_API_KEY` environment variable

3. **Run the agent:**
   ```bash
   python send_email.py recipient@example.com
   ```
   
   Or set the recipient email as an environment variable:
   ```bash
   export RECIPIENT_EMAIL=recipient@example.com
   python send_email.py
   ```

   On first run, you'll be prompted to authorize the application in your browser.

### Usage

- **Send email (default):**
  ```bash
  python send_email.py --action send recipient@example.com
  ```
  Sends the template email with subject "Hello from Gullie Agent" and body "hello from jolie".

- **Summarize the latest inbox email:**
  ```bash
  python send_email.py --action summarize
  ```
  Fetches the most recent email in your Gmail inbox and produces a concise summary using OpenAI.

> `credentials.json` (and the generated `token.json`) must never be committed to Git. Keep them private and distribute securely if others need to run the agent.

---

## System Overview

### Parties Involved

- **Agent** (Gullie) - The automated email agent
- **Employee** - The person requesting moving services
- **Employer** - The company providing the moving benefit
- **Vendors** - Moving service providers

## What Agents Need to Know

### Knowledge Base

The agent maintains information about:

- **Vendors Available**
  - Name
  - Area of service
  - Service providing
  - Contact info
  - Payment method
  - Price
- **What needs to be sent to employees**
- **What needs to be sent to vendors**

### Employer Information

- Budget

#### Personal Info
- First name
- Middle name
- Last name
- Phone number
- Email address

#### Moving Info
- Moving from
- Moving to
- Moving date


### Employee Information

#### Moving Details
- **Details**
  - What to be moved: survey link
  - Insurance tier
  - Do we need Box?
  - Do we need help packing?

#### Approval
- Accept/Decline

### Vendor Information

- Quotes
- Finalized dates