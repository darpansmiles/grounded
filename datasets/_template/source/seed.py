"""Starter seed: reuse the documented fixture shape until you replace it."""
from datasets.fixture.source.seed import seed_database
from packlib import active_pack

seed_database(str(active_pack().destination.path))
