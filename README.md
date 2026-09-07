# Transaction Reconciliation
A small reconciliation system that compares transactions from two independent systems, identifies matches and discrepancies, and allows a human to resolve ambiguous cases.
The implementation focuses on deterministic, explainable reconciliation rather than unclear matching logic.

---

## Problem
Two independent systems record the same financial transactions, but their records may differ:

- Different column names and date formats
- Different vocabulary for values such as `BUY` / `B`
- Small differences in timestamps due to clock differences
- Small differences in prices or amounts due to rounding or fees
- Transactions appearing in only one system
- Corrections arriving in later files
- Exact duplicate files being resent
- Ambiguous matches that require human review

The goal is to determine which transactions correspond, identify meaningful differences, and preserve human decisions across future reconciliation runs.

---

## Solution
The system separates reconciliation into four steps:

1. **Ingestion**
    - Upload CSV files
    - Detect exact duplicate files using SHA-256
    - Parse and normalize source-specific fields
    - Store transaction history and file

2. **Matching**
    - Generate plausible candidates using stable transaction attributes
    - Rank candidates using deterministic scoring
    - Automatically match unambiguous records
    - Send ambiguous records to human review

3. **Comparison**
   - Compare matched transactions field by field
   - Apply configurable tolerances
   - Show the magnitude of each difference

4. **Human resolution**
   - Manually confirm an ambiguous match
   - Or mark a transaction as intentionally unmatched
   - Persist the decision against the underlying transactions
   - Reuse the decision in future reconciliation runs

---

## Architecture

                    ┌──────────────────────┐
                    │      React UI        │
                    │                      │
                    │ Upload / Run / Review│
                    └──────────┬───────────┘
                               │ REST API
                               ▼
                    ┌──────────────────────┐
                    │    Django / DRF      │
                    │                      │
                    │ API + persistence    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Reconciliation       │
                    │ Service              │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Pure Python Engine   │
                    │                      │
                    │ Normalize            │
                    │ Match                │
                    │ Compare              │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ SQLite / PostgreSQL  │
                    │                      │
                    │ Transactions         │
                    │ Versions             │
                    │ Runs                 │
                    │ Decisions            │
                    └──────────────────────┘

                    

The core recoiliation logic is intentionally independent of Django and the database.
This makes the matching and comparison logic straightforward to test.


# Technology

## Backend
- Python
- Django
- Django REST Framework
- SQLite for local development
- PostgreSQL-compatible data model via Psycopg

## Frontend
- React
- Vite

## Testing
- pytest
- pytest-django


# Project Structure

    reconciliation-engine/
    │
    ├── reconciliation/
    │   ├── domain.py
    │   ├── normalize.py
    │   ├── matching.py
    │   ├── comparison.py
    │   ├── rules.py
    │   └── engine.py
    │
    ├── config/
    │   ├── settings.py
    │   ├── urls.py
    │   └── reconciliation_app/
    │       ├── models.py
    │       ├── views.py
    │       ├── urls.py
    │       ├── services/
    │       │   ├── file_ingestion.py
    │       │   ├── parsers.py
    │       │   ├── transaction_loader.py
    │       │   └── reconciliation_service.py
    │       └── tests/
    │
    ├── frontend/
    │   └── src/
    │       ├── App.jsx
    │       ├── api.js
    │       └── styles.css
    │
    ├── sampleFiles/
    │   ├── ourSystem.csv
    │   └── externalSystem.csv
    │
    ├── tests/
    │
    ├── requirements.txt
    └── README.md


# Local Setup

## 1. Clone the repository

```bash
git clone <repository-url>
cd reconciliation-engine
```

## 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```
## 3. Install Python dependencies

```bash
pip install -r requirements.txt
```
## 4. Run migrations

```bash
python manage.py migrate
```
## 5. Create the initial sources and reconciliation rules
## Open the Django shell:
```bash
python manage.py shell
```
## Then run:

```python
from decimal import Decimal
from reconciliation_app.models import Source, RuleSet

our_source = Source.objects.create(
    name="Our System",
    source_type="OUR_LEDGER",
)

external_source = Source.objects.create(
    name="External System",
    source_type="EXTERNAL_STATEMENT",
)

ruleset = RuleSet.objects.create(
    name="Default",
    version=1,
    amount_tolerance=Decimal("10"),
    price_tolerance=Decimal("5"),
    quantity_tolerance=Decimal("0"),
    time_tolerance_seconds=60,
)

print(
    f"Our source: {our_source.id}, "
    f"External source: {external_source.id}, "
    f"Ruleset: {ruleset.id}"
)
```

## Then:

```python
exit()
```

## For a fresh SQLite database, the IDs will normally be:

```bash
Our System:      1
External System: 2
Default RuleSet: 1
```
## The application itself uses the IDs returned by the setup for the current local demo.

# Start the Application

## Backend
### From the project root:

```bash
python manage.py runserver
```
### The backend runs at:

```bash
http://localhost:8000
```

## Frontend

### In another terminal:

```bash
cd frontend
npm install
npm run dev
```

### The frontend runs at the Vite development URL, normally:

```bash
http://localhost:5173
```

# Run Tests

## From the project root:

```bash
pytest -q
```

## The test suite covers the reconciliation engine, normalization, comparison, persistence, APIs, manual decisions, corrections, and ruleset behavior.

# How to Use the Application

## The normal user flow is:

    Upload Our CSV
        │
        ▼
    Upload External CSV
        │
        ▼
    Select / use reconciliation rules
        │
        ▼
    Start reconciliation run
        │
        ▼
    Review summary
        │
        ├── Matched
        │
        ├── Matched with small differences
        │
        ├── Needs review
        │
        ├── Unmatched on our side
        │
        └── Unmatched on external side
                        │
                        ▼
                Human resolution
                        │
                        ▼
            Decision is persisted
                        │
                        ▼
            Future runs reuse it

# Reconciliation Flow

## 1. File ingestion

### Each uploaded file is hashed using SHA-256.

### The system stores:
- Source
- original filename
- File hash
- Upload timestamp

An exact duplicate file from the source is detected using:

```bash
(source, file_hash)
```

This means renaming a file does not bypass duplicate detection.

A correction file is expected to have a different hash and is therefore processed as a new file.

# 2. Normalization

## Different source schemas are converted into one canonical transaction representation.

For example:

| Our System | External system | Canonical Field |
|---|---|---|
| `trade_id` | `reference` | `source_reference` |
| `traded_at` | `executed_at` | `timestamp` |
| `instrument` | `symbol` | `instrument` |
| `side` | `direction` | `side` |
| `quantity` | `qty` | `quantity` |
| `price` | `unit_price` | `unit_price` |
| `gross_amount` | `total` | `amount` |
| `state` | `status` | `status` |

## Value normalization also converts:

```bash
B    → BUY
S    → SELL
BUY  → BUY
SELL → SELL
```

The matching engine therefore does not need to know the original column names or source-specific vocabulary.

---

# 3. Cancelled transactions

Cancelled transactions are excluded from reconciliation.

They are not treated as unmatched financial transactions.

They remain available in the stored source data for traceability.

---

# 4. Matching

Matching and comparison are deliberately separate.

**Matching asks:**

> "Which external transaction most likely represents this transaction?"

**Comparison asks:**

> "Now that we have identified the pair, do their values agree?"

The matching process first generates plausible candidates using relatively stable attributes:

- Instrument
- Side
- Quantity
- Timestamp proximity

Price and amount are not used as hard identity requirements because these are exactly the fields that may legitimately differ.

---

## Candidate ranking

**Candidates are ranked deterministically.**

An exact source reference is a strong signal, but it is not the only possible way to match a transaction.

For example:

```bash
Our:
T-1005 | SOL | BUY | 100 | 149.00

External:
C-9002 | SOL | BUY | 100 | 149.10
C-9003 | SOL | BUY | 100 | 149.00
```
Both external transactions can be plausible candidates.

Instead of silently choosing one, the system sends the case to human review.

This avoids making an irreversible financial decision based only on a ranking score.

---

# 5. Comparison

**After a pair is identified, the system compares:**

- Quantity
- Unit price
- Amount
- Timestamp

Only fields with differences are displayed.

Each difference contains:

```bash
Field
Our value
External value
Difference
Allowed tolerance
Whether it is within tolerance
```

**For example:**

```bash
Price
Our:       3400
External:  3417
Difference: +17
Tolerance:  5
Result:    Review required
```

---

## Tolerances
The inital ruleset uses:

| Field | Tolerance|
|---|---|
| `Quantity` | `0` |
| `Unit price` | `5` |
| `Amount` |  `10` |
| `Timestamp` | `60 seconds` |

These values are assumptions for the take-home demo rather than values specified by the assignment.

They are configurable through the UI.

---

# Result States

The reconciliation engine can produce the following states:

**MATCHED**

A transaction was matched and all compared values agree.

**MATCHED_WITH_DIFFERENCES**

A transaction was matched, but has small differences that are within configured tolerances.

These differences are still displayed to the user.

**NEEDS_REVIEW**

A transaction was matched or has ambiguous candidates, but requires human attention.


Examples:

- Multiple plausible candidates

- Price difference exceeds tolerance

- Amount difference exceeds tolerance


**UNMATCHED_OUR_SIDE**

A transaction exists in our system but no suitable external transaction was found.

**UNMATCHED_EXTERNAL_SIDE**

A transaction exists in the external system but no suitable transaction was found in our system.

**EXCLUDED**

The transaction is excluded from comparison, currently used for cancelled transactions.

---

# Human Review

**Ambiguous transactions are presented with their candidate matches.**

The reviewer can:

1. Select the correct external transaction
2. Confirm the match
3. Leave the transaction unmatched

The selected decision is persisted.

Manual decisions are associated with the underlying business transactions rather than a particular transaction version.

This is important because a later correction file may create a new version of the transaction.

The manual identity decision should still apply to the corrected transaction.

---

# Corrections and Transaction History

Files can arrive repeatedly.

An exact duplicate file is ignored.

A correction file with a new hash is processed as a new observation.

Transactions are modeled as:

```bash
Transaction
     │
     ├── Version 1
     │
     ├── Version 2
     │
     └── Version 3
```

The latest version is used for future reconciliation while previous versions remain stored for history and auditability.

This means a correction does not overwrite the previous observation.

---

# Reconciliation Runs

Every reconciliation run records:

- Our input file
- External input file
- RuleSet version
- Run status
- Start time
- Completion time
- Individual reconciliation results

This makes a historical run reproducible against the rules that were active when it was executed.


---

# RuleSet Versioning

Rules are versioned.

Changing a tolerance does not modify an existing ruleset.

Instead, the application creates a new version.

For example:

```bash
Default v1
price tolerance = 5

        ↓ update

Default v2
price tolerance = 20
```

An old reconciliation run continues to reference v1.

A new reconciliation run can use v2.

This prevents changing today's rules from silently rewriting yesterday's results.


---

# Data Model

The main database entities are:

```bash
Source
  │
  └── File
        │
        └── TransactionVersion
                │
                ▼
           Transaction
                │
                ▼
       ReconciliationResult
                │
                ▼
         ManualDecision


RuleSet ───────────────┐
                       ▼
              ReconciliationRun
                       │
                       ▼
             ReconciliationResult
```

Important tables:

- Source
- File
- Transaction
- TransactionVersion
- RuleSet
- ReconciliationRun
- ReconciliationResult
- ManualDecision

---


# API

The main API endpoints are:

```bash
POST /api/files/
```

Upload a CSV file.

```bash
POST /api/runs/
```

Start a reconciliation run.

```bash
GET /api/runs/<run_id>/
```

Retrieve run results.

```bash
POST /api/results/<result_id>/decision/
```

Persist a human reconciliation decision.

```bash
GET /api/rulesets/current/
```

Retrieve the current ruleset.

```bash
GET /api/rulesets/<ruleset_id>/
PATCH /api/rulesets/<ruleset_id>/
```

View or create a new version of a ruleset.

---

# Testing Philosophy

The core reconciliation logic is implemented separately from Django and the database.

This allows the important business rules to be tested directly.

Tests cover cases including:

- Schema/value normalization
- Timestamp tolerance
- Price tolerance
- Amount tolerance
- Quantity tolerance
- Exact reference matching
- Attribute-based matching
- Ambiguous candidates
- Unmatched transactions
- Cancelled transactions
- Manual matching
- Persistence of manual decisions
- Transaction corrections
- Manual decisions surviving corrections
- Duplicate manual decisions
- Failed reconciliation runs
- API behavior
- RuleSet versioning

---

# Important Design Decisions

**Deterministic matching instead of AI**

The reconciliation decision path is deterministic and explainable.

For financial reconciliation, it is more important to explain why two transactions were matched than to produce an opaque prediction.

AI could be useful later for:

- Suggesting schema mappings
- Explaining discrepancies
- Prioritizing review queues

But the core financial matching decision should remain deterministic and auditable.

## Matching is separate from comparison

A transaction can be the correct match while still containing a financial discrepancy.

For example:

```bash
Same transaction
      │
      ├── Timestamp differs by 10 sec → acceptable
      │
      ├── Price differs by 17 → review
      │
      └── Amount differs by 170 → review
```

The identity decision and the financial comparison therefore remain separate concepts.

## Human decisions override automatic matching

When the system cannot safely determine a unique match, it asks a human rather than silently guessing.

## Historical versions are retained

Correction files update the effective transaction version without destroying historical observations.

## Rules are versioned

Historical reconciliation results remain associated with the rules used to produce them.


---

# Assumptions

The following values and behaviors were chosen for the take-home implementation because the assignment does not specify exact production thresholds:

- Timestamp tolerance: 60 seconds
- Quantity tolerance: 0
- Price tolerance: 5
- Amount tolerance: 10
- Cancelled transactions are excluded
- A transaction participates in at most one active pairing per run
- Ambiguous candidates require human confirmation
- Exact duplicate files are identified using source + file hash
- Corrections create new transaction versions

These values should be configurable in a production implementation.

---

# Known Limitations / Next Steps

This implementation intentionally keeps the scope appropriate for the take-home assignment.

Potential production improvements include:

- PostgreSQL configuration for deployment
- Background processing for large files
- More scalable candidate generation/indexing
- Additional source-specific parsers
- Stronger authentication and authorization
- User accounts instead of the demo decided_by field
- More granular database tables for candidate explanations and field differences
- Better concurrency handling during ingestion
- Pagination for large reconciliation runs
- Bulk review actions
- Audit logging for every user action
- Monitoring and operational metrics
- Support for more than two systems
- More sophisticated candidate matching for large datasets


---

# Sample Data

The repository includes sample files under:

```bash
sampleFiles/
```

The sample data demonstrates:

- Exact matches
- Small timestamp differences
- Financial discrepancies
- Unmatched transactions
- Ambiguous candidates
- Different transaction references
- Different source schemas and value vocabularies

---

# Demo Scenario

A recommended demo flow is:

1. Start the backend and frontend
2. Upload ourSystem.csv
3. Upload externalSystem.csv
4. Start reconciliation
5. Review the summary
6. Inspect an exact match
7. Inspect a tolerated timestamp difference
8. Inspect a financial discrepancy
9. Inspect an unmatched transaction
10. Inspect an ambiguous transaction
11. Manually confirm the correct candidate
12. Demonstrate that the manual decision is persisted
13. Upload a correction file
14. Demonstrate transaction versioning
15. Change the ruleset
16. Run again and demonstrate that a new ruleset version affects only new runs


---

# Submission

This repository contains the backend, frontend, tests, sample data, and documentation required to run and evaluate the reconciliation system.
