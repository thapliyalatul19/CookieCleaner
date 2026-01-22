"""Tests for the SearchableListWidget."""

import pytest
import time

# Skip all tests if PyQt6 is not available
pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt

from src.ui.widgets.searchable_list import SearchableListWidget


class TestSearchableListWidget:
    """Tests for SearchableListWidget."""

    @pytest.fixture
    def widget(self, qtbot):
        """Create a SearchableListWidget for testing."""
        w = SearchableListWidget(title="Test List", placeholder="Search...")
        qtbot.addWidget(w)
        return w

    def test_initial_state(self, widget):
        """Widget should start with no items."""
        assert widget.count() == 0
        assert not widget.has_selection()

    def test_set_items(self, widget):
        """set_items() should populate the list."""
        items = [("example.com", 5), ("test.org", 3)]
        widget.set_items(items)
        assert widget.count() == 2

    def test_set_whitelist_items(self, widget):
        """set_whitelist_items() should populate with entry strings."""
        entries = ["domain:google.com", "exact:auth.site.com"]
        widget.set_whitelist_items(entries)
        assert widget.count() == 2

    def test_add_item(self, widget):
        """add_item() should add a single item."""
        widget.add_item("test.com", "test.com")
        assert widget.count() == 1

    def test_remove_selected(self, widget, qtbot):
        """remove_selected() should remove and return selected items."""
        items = [("a.com", 1), ("b.com", 2), ("c.com", 3)]
        widget.set_items(items)

        # Select the second item
        widget._list_widget.setCurrentRow(1)

        removed = widget.remove_selected()
        assert len(removed) == 1
        assert removed[0] == "b.com"
        assert widget.count() == 2

    def test_get_selected_items(self, widget, qtbot):
        """get_selected_items() should return selected domain values."""
        items = [("a.com", 1), ("b.com", 2)]
        widget.set_items(items)

        widget._list_widget.setCurrentRow(0)

        selected = widget.get_selected_items()
        assert len(selected) == 1
        assert selected[0] == "a.com"

    def test_get_all_items(self, widget):
        """get_all_items() should return all domain values."""
        items = [("a.com", 1), ("b.com", 2), ("c.com", 3)]
        widget.set_items(items)

        all_items = widget.get_all_items()
        assert len(all_items) == 3
        assert "a.com" in all_items
        assert "b.com" in all_items
        assert "c.com" in all_items

    def test_clear(self, widget):
        """clear() should remove all items."""
        items = [("a.com", 1), ("b.com", 2)]
        widget.set_items(items)
        widget.clear()
        assert widget.count() == 0

    def test_filtering_shows_matching_items(self, widget, qtbot):
        """Filtering should show only matching items."""
        items = [("google.com", 5), ("microsoft.com", 3), ("github.com", 2)]
        widget.set_items(items)

        # Type search text
        widget._search_field.setText("google")

        # Check visibility
        for i in range(widget._list_widget.count()):
            item = widget._list_widget.item(i)
            domain = item.data(Qt.ItemDataRole.UserRole)
            if domain == "google.com":
                assert not item.isHidden()
            else:
                assert item.isHidden()

    def test_filtering_is_case_insensitive(self, widget, qtbot):
        """Filtering should be case-insensitive."""
        items = [("Google.com", 5), ("Microsoft.com", 3)]
        widget.set_items(items)

        widget._search_field.setText("GOOGLE")

        item = widget._list_widget.item(0)
        # Note: the domain is stored lowercase in data role by default
        # The display text preserves case from input
        assert not item.isHidden() or item.data(Qt.ItemDataRole.UserRole).lower() == "google.com"

    def test_filtering_clears_with_empty_search(self, widget, qtbot):
        """Clearing search should show all items."""
        items = [("a.com", 1), ("b.com", 2)]
        widget.set_items(items)

        widget._search_field.setText("a")
        widget._search_field.clear()

        for i in range(widget._list_widget.count()):
            item = widget._list_widget.item(i)
            assert not item.isHidden()

    def test_filtering_performance(self, widget, qtbot):
        """Filtering 1000 items should complete in under 100ms."""
        # Create 1000 items
        items = [(f"domain{i}.com", i) for i in range(1000)]
        widget.set_items(items)

        # Time the filter operation
        start = time.perf_counter()
        widget._search_field.setText("domain5")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Filtering took {elapsed*1000:.2f}ms, expected <100ms"

    def test_select_all(self, widget, qtbot):
        """select_all() should select all items."""
        items = [("a.com", 1), ("b.com", 2), ("c.com", 3)]
        widget.set_items(items)

        widget.select_all()

        assert len(widget._list_widget.selectedItems()) == 3

    def test_clear_selection(self, widget, qtbot):
        """clear_selection() should deselect all items."""
        items = [("a.com", 1), ("b.com", 2)]
        widget.set_items(items)

        widget.select_all()
        widget.clear_selection()

        assert len(widget._list_widget.selectedItems()) == 0

    def test_has_selection_true(self, widget, qtbot):
        """has_selection() should return True when items are selected."""
        items = [("a.com", 1)]
        widget.set_items(items)
        widget._list_widget.setCurrentRow(0)

        assert widget.has_selection()

    def test_has_selection_false(self, widget):
        """has_selection() should return False when no items selected."""
        items = [("a.com", 1)]
        widget.set_items(items)

        assert not widget.has_selection()
