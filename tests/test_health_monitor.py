import time
from unittest.mock import MagicMock
from health_monitor import run_health_check, check_db_health

def test_health_monitor_basic():
    # Database check
    db_ok = check_db_health()
    assert isinstance(db_ok, bool)

    # Watchdog run
    mock_app = MagicMock()
    report = run_health_check(context=mock_app)
    assert "timestamp" in report
    assert "db_ok" in report
    assert "scheduler_running" in report
    assert "repaired_jobs" in report
    assert "user_statuses" in report
