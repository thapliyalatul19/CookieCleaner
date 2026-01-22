"""Searchable list widget for Cookie Cleaner.

Provides a QLineEdit + QListWidget combination with real-time filtering.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
)
from PyQt6.QtCore import pyqtSignal, Qt


class SearchableListWidget(QWidget):
    """
    A widget combining a search field with a filterable list.

    Supports real-time filtering with <100ms performance for 1000+ items.
    Stores domain data in item's data role for easy retrieval.
    """

    item_selected = pyqtSignal(str)  # Emits domain when item is selected
    item_double_clicked = pyqtSignal(str)  # Emits domain on double-click
    selection_changed = pyqtSignal()  # Emits when selection changes

    def __init__(
        self,
        title: str = "",
        placeholder: str = "Search...",
        parent: QWidget | None = None,
    ) -> None:
        """
        Initialize the SearchableListWidget.

        Args:
            title: Optional title label above the list
            placeholder: Placeholder text for search field
            parent: Parent widget
        """
        super().__init__(parent)

        self._items: list[tuple[str, int, str]] = []  # (display_text, count, domain)
        self._setup_ui(title, placeholder)
        self._connect_signals()

    def _setup_ui(self, title: str, placeholder: str) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Optional title
        if title:
            self._title_label = QLabel(title)
            self._title_label.setStyleSheet("font-weight: bold;")
            layout.addWidget(self._title_label)
        else:
            self._title_label = None

        # Search field
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText(placeholder)
        self._search_field.setClearButtonEnabled(True)
        layout.addWidget(self._search_field)

        # List widget
        self._list_widget = QListWidget()
        self._list_widget.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._list_widget)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self._search_field.textChanged.connect(self._filter_items)
        self._list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self._list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

    def _filter_items(self, text: str) -> None:
        """
        Filter list items based on search text.

        Uses case-insensitive substring matching.
        """
        search_lower = text.lower()

        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item:
                domain = item.data(Qt.ItemDataRole.UserRole)
                if domain:
                    visible = search_lower in domain.lower()
                    item.setHidden(not visible)

    def _on_selection_changed(self) -> None:
        """Handle selection change."""
        selected = self._list_widget.selectedItems()
        if selected:
            domain = selected[0].data(Qt.ItemDataRole.UserRole)
            if domain:
                self.item_selected.emit(domain)
        self.selection_changed.emit()

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle double-click on item."""
        domain = item.data(Qt.ItemDataRole.UserRole)
        if domain:
            self.item_double_clicked.emit(domain)

    def set_items(self, items: list[tuple[str, int]]) -> None:
        """
        Set list items from domain/count tuples.

        Args:
            items: List of (domain, cookie_count) tuples
        """
        self._list_widget.clear()
        self._items = []

        for domain, count in items:
            display_text = f"{domain} ({count})"
            self._items.append((display_text, count, domain))

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, domain)
            self._list_widget.addItem(item)

        # Re-apply filter if search field has text
        if self._search_field.text():
            self._filter_items(self._search_field.text())

    def set_whitelist_items(self, entries: list[str]) -> None:
        """
        Set list items from whitelist entries.

        Args:
            entries: List of whitelist entry strings (e.g., "domain:google.com")
        """
        self._list_widget.clear()
        self._items = []

        for entry in entries:
            display_text = entry
            self._items.append((display_text, 0, entry))

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._list_widget.addItem(item)

        if self._search_field.text():
            self._filter_items(self._search_field.text())

    def add_item(self, text: str, data: str | None = None) -> None:
        """
        Add a single item to the list.

        Args:
            text: Display text
            data: Data to store (defaults to text)
        """
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, data or text)
        self._list_widget.addItem(item)
        self._items.append((text, 0, data or text))

    def remove_selected(self) -> list[str]:
        """
        Remove and return selected items.

        Returns:
            List of removed item data values
        """
        removed = []
        for item in self._list_widget.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                removed.append(data)
            row = self._list_widget.row(item)
            self._list_widget.takeItem(row)
        return removed

    def get_selected_items(self) -> list[str]:
        """
        Get data values of selected items.

        Returns:
            List of selected item data values
        """
        selected = []
        for item in self._list_widget.selectedItems():
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                selected.append(data)
        return selected

    def get_all_items(self) -> list[str]:
        """
        Get data values of all items.

        Returns:
            List of all item data values
        """
        items = []
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    items.append(data)
        return items

    def clear(self) -> None:
        """Clear all items from the list."""
        self._list_widget.clear()
        self._items = []
        self._search_field.clear()

    def count(self) -> int:
        """Return the number of items in the list."""
        return self._list_widget.count()

    def has_selection(self) -> bool:
        """Return True if any items are selected."""
        return len(self._list_widget.selectedItems()) > 0

    def select_all(self) -> None:
        """Select all visible items."""
        self._list_widget.selectAll()

    def clear_selection(self) -> None:
        """Clear the current selection."""
        self._list_widget.clearSelection()
