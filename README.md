# gullie-agentmail

A Gmail agent that sends emails automatically.

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

The agent will send an email with the subject "Hello from Gullie Agent" and the body "hello from jolie" to the specified recipient.

---

## Parties Involved

- **Agent** (Gullie)
- **Employee**
- **Employer**
- **Vendors**

## What Agents Need to Know

### Knowledge Base

- **Vendors Available**
  - Name
  - Area of service
  - Service providing
  - Contact info
  - Payment method
- **What needs to be sent to employees**
- **What needs to be sent to vendors**

### Employer

- Budget

### Employee

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
- **Details**
  - What to be moved: survey link
  - Insurance
  - Box?
  - Need help packing?

#### Approval
- Accept/Decline

### Vendor

- Quotes
- Finalized dates
