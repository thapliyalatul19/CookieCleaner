"""Tests for the MainToolbar widget."""

import pytest

# Skip all tests if PyQt6 is not available
pytest.importorskip("PyQt6")

from src.ui.widgets.toolbar import MainToolbar


class TestMainToolbar:
    """Tests for MainToolbar widget."""

    @pytest.fixture
    def toolbar(self, qtbot):
        """Create a MainToolbar for testing."""
        t = MainToolbar()
        qtbot.addWidget(t)
        return t

    def test_initial_state(self, toolbar):
        """Toolbar should start with clean disabled."""
        assert toolbar._scan_action.isEnabled()
        assert not toolbar._clean_action.isEnabled()
        assert toolbar._settings_action.isEnabled()
        assert toolbar._restore_action.isEnabled()

    def test_set_scan_enabled(self, toolbar):
        """set_scan_enabled() should control scan action state."""
        toolbar.set_scan_enabled(False)
        assert not toolbar._scan_action.isEnabled()

        toolbar.set_scan_enabled(True)
        assert toolbar._scan_action.isEnabled()

    def test_set_clean_enabled(self, toolbar):
        """set_clean_enabled() should control clean action state."""
        toolbar.set_clean_enabled(True)
        assert toolbar._clean_action.isEnabled()

        toolbar.set_clean_enabled(False)
        assert not toolbar._clean_action.isEnabled()

    def test_set_all_enabled(self, toolbar):
        """set_all_enabled() should control all actions."""
        toolbar.set_all_enabled(False)
        assert not toolbar._scan_action.isEnabled()
        assert not toolbar._clean_action.isEnabled()
        assert not toolbar._settings_action.isEnabled()
        assert not toolbar._restore_action.isEnabled()
        assert not toolbar._dry_run_checkbox.isEnabled()

        toolbar.set_all_enabled(True)
        assert toolbar._scan_action.isEnabled()
        assert toolbar._clean_action.isEnabled()
        assert toolbar._settings_action.isEnabled()
        assert toolbar._restore_action.isEnabled()
        assert toolbar._dry_run_checkbox.isEnabled()

    def test_dry_run_checkbox(self, toolbar):
        """Dry run checkbox should toggle correctly."""
        assert not toolbar.is_dry_run()

        toolbar.set_dry_run(True)
        assert toolbar.is_dry_run()

        toolbar.set_dry_run(False)
        assert not toolbar.is_dry_run()

    def test_scan_triggered_signal(self, toolbar, qtbot):
        """scan_triggered signal should emit when scan action triggered."""
        with qtbot.waitSignal(toolbar.scan_triggered, timeout=1000):
            toolbar._scan_action.trigger()

    def test_clean_triggered_signal(self, toolbar, qtbot):
        """clean_triggered signal should emit when clean action triggered."""
        toolbar.set_clean_enabled(True)
        with qtbot.waitSignal(toolbar.clean_triggered, timeout=1000):
            toolbar._clean_action.trigger()

    def test_settings_triggered_signal(self, toolbar, qtbot):
        """settings_triggered signal should emit when settings action triggered."""
        with qtbot.waitSignal(toolbar.settings_triggered, timeout=1000):
            toolbar._settings_action.trigger()

    def test_restore_triggered_signal(self, toolbar, qtbot):
        """restore_triggered signal should emit when restore action triggered."""
        with qtbot.waitSignal(toolbar.restore_triggered, timeout=1000):
            toolbar._restore_action.trigger()

    def test_dry_run_changed_signal(self, toolbar, qtbot):
        """dry_run_changed signal should emit when checkbox toggled."""
        signals = []

        def capture_signal(value):
            signals.append(value)

        toolbar.dry_run_changed.connect(capture_signal)

        toolbar._dry_run_checkbox.setChecked(True)
        toolbar._dry_run_checkbox.setChecked(False)

        assert len(signals) == 2
        assert signals[0] is True
        assert signals[1] is False
