from guanchen_v2.evaluation.suite import verdict


def test_stage11_gate_does_not_accept_a_pass_flag_without_required_evidence():
    result = verdict([], {}, {}, {}, {}, {"passed": True})
    assert result["stage11_backend"] is False
    assert result["all_commands_completed"] is False
