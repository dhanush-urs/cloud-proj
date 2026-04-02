import sys
import os

# Add apps/api to path
sys.path.append(os.path.join(os.getcwd(), "apps/api"))

from app.services.rag_service import QueryClassifier, QueryIntent

def test_classifier():
    test_cases = [
        {
            "q": "what'll happen if I change JLabel heading = new JLabel('ADD CUSTOMER DETAILS'); heading to h",
            "expected_intent": QueryIntent.LINE_CHANGE_IMPACT,
            "expected_op": "rename",
            "expected_sym": "heading",
            "expected_new": "h"
        },
        {
            "q": "delete import java.util.Random;",
            "expected_intent": QueryIntent.LINE_IMPACT,
            "expected_op": "delete",
            "expected_snippet": "import java.util.Random;"
        },
        {
            "q": "what happens if I change line 45 in app/main.py",
            "expected_intent": QueryIntent.LINE_IMPACT,
            "expected_line": 45,
            "expected_file": "app/main.py"
        }
    ]

    for i, tc in enumerate(test_cases):
        res = QueryClassifier.classify(tc["q"])
        print(f"Test Case {i+1}: {tc['q']}")
        print(f"Result: {res}")
        
        assert res["intent"] == tc["expected_intent"]
        if "expected_op" in tc:
            assert res.get("operation") == tc["expected_op"]
        if "expected_sym" in tc:
            assert res.get("symbol") == tc["expected_sym"]
        if "expected_new" in tc:
            assert res.get("new_text") == tc["expected_new"]
        print("MATCHED!\n")

if __name__ == "__main__":
    try:
        test_classifier()
        print("\nALL CLASSIFIER TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
