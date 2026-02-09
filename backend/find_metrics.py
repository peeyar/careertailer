import deepeval.metrics
print("--- CONTENTS OF deepeval.metrics ---")
print(dir(deepeval.metrics))

try:
    from deepeval.metrics import AnswerCorrectnessMetric
    print("\n✅ Found AnswerCorrectnessMetric in root!")
except ImportError:
    print("\n❌ Not in root.")

try:
    from deepeval.metrics.answer_correctness import AnswerCorrectnessMetric
    print("\n✅ Found AnswerCorrectnessMetric in .answer_correctness submodule!")
except ImportError:
    print("\n❌ Not in submodule.")