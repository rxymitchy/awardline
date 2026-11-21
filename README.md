# Awardline

Awardline helps procurement officers in Kenya check whether a supplier quote is reasonable. You enter the buyer, the item, the quoted amount, and optionally the supplier. The system searches thousands of published Kenya PPIP award records, compares the quote against similar past contracts, and produces a committee note you can approve and file — all from a browser.

Each officer's notes are kept separate. Two officers can check the same quote independently and each gets their own note, approval, and filing.

---

## What it does

1. Searches published Kenya PPIP awards for contracts similar to the one you're checking
2. Calculates the median price from those comparable contracts
3. Flags the quote if it is at least twice the median
4. Lists every source contract with its OCID, buyer, supplier, amount, and date
5. Drafts a committee note you can read, approve, and file with one click

The system never awards a tender. An officer must approve every note before it can be filed.

---

## Setup

You need Python 3.11+, Node.js, and either an [Ollama](https://ollama.com) installation (free, runs locally) or a [Groq](https://console.groq.com) API key (fast, cloud-based).

**1. Install dependencies**

```
npm install
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

**2. Set your model**

For Groq (recommended for a private deployment): copy `.env.example` to `.env` and add your `GROQ_API_KEY`.

For Ollama: install Ollama, run `ollama pull qwen2.5:3b`, and leave `.env` as-is.

**3. Start the web server**

```
.\start_web.ps1
```

Then open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Using the tool

1. **Sign in** with your name
2. **New check** — enter the buyer, item description, quoted amount, and supplier (optional)
3. **Watch the agent work** — it searches PPIP, compares prices, and drafts the note automatically
4. **Review** the verdict, the comparable contracts, and the full committee note
5. **Approve & File** — one button records your approval and saves the note to the committee folder

Your filed notes appear on the **Filed Notes** page. You can view, download, or share any note from there.

---

## Keeping the data current

The PPIP award data is stored locally. To download the latest data from the PPIP portal, click the **🔄 Refresh PPIP data** button on the Filed Notes page. No command line needed.

---

## Private deployment

To run this for your organisation on a private server:

1. Set `AWARDLINE_SECRET` in your `.env` to a long random string (keeps sessions secure)
2. Set `GROQ_API_KEY` to your Groq key (or run Ollama on the same server)
3. Run behind a reverse proxy (nginx, Caddy) with HTTPS
4. The `runtime/` folder holds all notes, approvals, and filings — back this up regularly

For proper multi-user access, put the server behind your organisation's SSO (Azure AD, Google Workspace, Okta) so only authorised staff can sign in.

---

## How the data works

- Awards data comes from the [Kenya PPIP portal](https://tenders.go.ke/ocds) — public, no login required
- The system compares titles using word overlap, weighted so rare specific words count more than common ones (a fuel quote won't be matched against tyre contracts just because both mention "motor vehicles")
- A flag is only raised when at least 4 comparable contracts exist — if there isn't enough data, the note says so and no flag is raised
- All contract amounts are totals, not unit prices. The note lists this caveat and shows every source so the committee can judge for themselves

---

## Limitations

- Contract amounts are totals only — no quantities or unit prices in the PPIP data
- Title matching is approximate — two contracts can share rare words but describe different purchases
- Supplier name matching handles common variants (Ltd/Limited, case differences) but not all abbreviations
- The data snapshot only updates when you click Refresh

