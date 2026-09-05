# setup 
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

#Run migrations:
python manage.py migrate

python manage.py shell

# Then:

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

then: exit()
For a fresh database, the expected IDs are:

Our System: 1
External System: 2
Default RuleSet: 1

# Start the Backend

python manage.py runserver

# Start the Frontend

cd frontend
npm install
npm run dev

# Run the Tests

pytest -q
