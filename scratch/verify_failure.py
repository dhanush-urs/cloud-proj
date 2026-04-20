import sys
import os
import re

# Add apps/api to path
sys.path.append("/Users/dhanushursmk/Desktop/cloud/repobrain/apps/api")

from app.services.rag_service import QueryClassifier, LineResolver
from app.schemas.search import AskRepoResponse
from pydantic import ValidationError

def test_classifier(q):
    print(f"Testing Query: {q}")
    res = QueryClassifier.classify(q)
    print(f"  Classification: {res}")
    print("-" * 20)

def test_pydantic():
    print("Testing AskRepoResponse Pydantic Model")
    bad_data = {
        "question": "q",
        "answer": "a",
        "mode": "refusal",
        # missing citations
    }
    try:
        AskRepoResponse(**bad_data)
        print("  FAILED: Missing citations should have errored.")
    except ValidationError:
        print("  SUCCESS: Caught missing citations.")

    good_data = {
        "question": "q",
        "answer": "a",
        "citations": [], # required list
        "mode": "refusal",
        "confidence": "low",
        "query_type": "line_impact"
    }
    try:
        AskRepoResponse(**good_data)
        print("  SUCCESS: Valid response accepted.")
    except ValidationError as e:
        print(f"  FAILED: {e}")

test_classifier("what will happen if I delete <head> line")
test_classifier("what will happen if I delete .contact-btn { line")
test_pydantic()
