import json
from pathlib import Path

from purposebench.utils import sha256_json
from purposebench.v2.condition_analysis import build_condition_pilot_report


def test_condition_pilot_report_is_reproducible() -> None:
    root = Path.cwd()
    report = build_condition_pilot_report(root)
    assert report["status"] == "COMPLETE_WITH_FAILURES"
    assert report["passedConditionCount"] == 4
    assert report["failedConditionCount"] == 1
    by_condition = {
        result["condition"]: result for result in report["conditionResults"]
    }
    assert by_condition["all_data_no_policy"][
        "prohibitedSyntheticFieldsTransmitted"
    ] is True
    assert by_condition["prompt_only_purpose_restriction"]["status"] == "FAILED"
    assert by_condition["prompt_only_purpose_restriction"]["providerDiagnostic"][
        "category"
    ] == "RATE_LIMIT"
    assert by_condition["ordinary_metadata_prefilter"][
        "prohibitedSyntheticFieldsTransmitted"
    ] is False
    assert by_condition["compex_projection_plus_native_release"][
        "releasePolicyMode"
    ] == "NATIVE_COMPEX_FULL"
    assert report["budget"]["categoryCommittedEur"] == 0.249461
    assert report["budget"]["globalCommittedEur"] == 9.01262918
    material = dict(report)
    observed = material.pop("reportHash")
    assert observed == sha256_json(material)

    stored_path = root / "results/v2/derived/openrouter-full-condition-pilot.json"
    if stored_path.exists():
        stored = json.loads(stored_path.read_text(encoding="utf-8"))
        assert stored == report
