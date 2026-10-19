from hmi.trainui.services.log_parser import LogParser


def test_parse_metrics():
    parser = LogParser()
    records = parser.feed("Step 100: loss=0.0123, grad_norm=0.4, param_norm=12.5\n")
    assert len(records) == 1
    metrics = records[0].metrics
    assert metrics is not None
    assert metrics.step == 100
    assert metrics.values["loss"] == 0.0123
    assert metrics.values["grad_norm"] == 0.4


def test_partial_metric_line():
    parser = LogParser()
    assert parser.feed("Step 2: loss=0.") == []
    records = parser.feed("5, grad_norm=1.0\n")
    assert records[0].metrics is not None
    assert records[0].metrics.values["loss"] == 0.5


def test_parse_openpi_progress_line():
    parser = LogParser()
    records = parser.feed(
        "13:54:21.157 [I] Progress on: 3.00it/10.0it rate:22.1s/it "
        "remaining:02:34 elapsed:01:13 postfix:- (1423184:tqdm_logging.py:145)\n"
    )
    assert len(records) == 1
    progress = records[0].progress
    assert progress is not None
    assert progress.completed == 3
    assert progress.total == 10
    assert not parser.should_show(records[0].line)


def test_initial_unknown_progress_is_ignored():
    parser = LogParser()
    records = parser.feed(
        "13:53:53.004 [I] Progress on: -/10 rate:- remaining:? elapsed:00:45 postfix:-\n"
    )
    assert len(records) == 1
    assert records[0].progress is None


def test_checkpoint_dict_is_not_metric():
    parser = LogParser()
    records = parser.feed("{'step': 2, 'event_type': 'save', 'directory': '/tmp/x'}\n")
    assert len(records) == 1
    assert records[0].metrics is None
