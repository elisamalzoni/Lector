#!usr/bin/env python3

# This file is a part of Lector, a Qt based ebook reader
# Copyright (C) 2017 BasioMeusPuga

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# TODO
# Reading modes
# Double page, Continuous etc
# Especially for comics


import os
import uuid
from PyQt5 import QtWidgets, QtGui, QtCore

from resources import pie_chart
from models import BookmarkProxyModel


class Tab(QtWidgets.QWidget):
    def __init__(self, metadata, parent=None):
        super(Tab, self).__init__(parent)
        self.parent = parent
        self.metadata = metadata  # Save progress data into this dictionary

        self.masterLayout = QtWidgets.QHBoxLayout(self)
        self.horzLayout = QtWidgets.QSplitter(self)
        self.horzLayout.setOrientation(QtCore.Qt.Horizontal)
        self.masterLayout.addWidget(self.horzLayout)

        self.metadata['last_accessed'] = QtCore.QDateTime().currentDateTime()

        position = self.metadata['position']
        if position:
            current_chapter = position['current_chapter']
        else:
            self.generate_position()
            current_chapter = 1

        chapter_name = list(self.metadata['content'])[current_chapter - 1]
        chapter_content = self.metadata['content'][chapter_name]

        # The content display widget is, by default a QTextBrowser
        # In case the incoming data is only images
        # such as in the case of comic book files,
        # we want a QGraphicsView widget doing all the heavy lifting
        # instead of a QTextBrowser
        self.are_we_doing_images_only = self.metadata['images_only']

        if self.are_we_doing_images_only:  # Boolean
            self.contentView = PliantQGraphicsView(self.window(), self)
            self.contentView.loadImage(chapter_content)
        else:
            self.contentView = PliantQTextBrowser(self.window(), self)

            relative_path_root = os.path.join(
                self.window().temp_dir.path(), self.metadata['hash'])
            relative_paths = []
            for i in os.walk(relative_path_root):
                relative_paths.append(os.path.join(relative_path_root, i[0]))
            self.contentView.setSearchPaths(relative_paths)

            self.contentView.setOpenLinks(False)  # TODO Change this when HTML navigation works
            self.contentView.setHtml(chapter_content)
            self.contentView.setReadOnly(True)

            tempHiddenButton = QtWidgets.QToolButton(self)
            tempHiddenButton.setVisible(False)
            tempHiddenButton.clicked.connect(self.set_scroll_value)
            tempHiddenButton.animateClick(100)

        # The following are common to both the text browser and
        # the graphics view
        self.contentView.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.contentView.setObjectName('contentView')
        self.contentView.verticalScrollBar().setSingleStep(7)
        self.contentView.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)

        # See bookmark availability
        if not self.metadata['bookmarks']:
            self.metadata['bookmarks'] = {}

        # Create the dock widget for context specific display
        self.dockWidget = PliantDockWidget(self)
        self.dockWidget.setWindowTitle('Bookmarks')
        self.dockWidget.setFeatures(QtWidgets.QDockWidget.DockWidgetClosable)
        self.dockWidget.setFloating(False)
        self.dockWidget.hide()

        self.dockListView = QtWidgets.QListView(self.dockWidget)
        self.dockListView.setResizeMode(QtWidgets.QListWidget.Adjust)
        self.dockListView.setMaximumWidth(350)
        self.dockListView.setItemDelegate(BookmarkDelegate(self.dockListView))
        self.dockListView.setUniformItemSizes(True)
        self.dockListView.clicked.connect(self.navigate_to_bookmark)
        self.dockWidget.setWidget(self.dockListView)

        self.bookmark_model = QtGui.QStandardItemModel(self)
        self.proxy_model = BookmarkProxyModel(self)
        self.generate_bookmark_model()

        self.generate_keyboard_shortcuts()

        self.horzLayout.addWidget(self.contentView)
        self.horzLayout.addWidget(self.dockWidget)
        title = self.metadata['title']
        self.parent.addTab(self, title)

        # Hide mouse cursor timer
        self.mouse_hide_timer = QtCore.QTimer()
        self.mouse_hide_timer.setSingleShot(True)
        self.mouse_hide_timer.timeout.connect(self.hide_mouse)

        self.contentView.setFocus()

    def update_last_accessed_time(self):
        self.metadata['last_accessed'] = QtCore.QDateTime().currentDateTime()

        start_index = self.window().lib_ref.view_model.index(0, 0)
        matching_item = self.window().lib_ref.view_model.match(
            start_index,
            QtCore.Qt.UserRole + 6,
            self.metadata['hash'],
            1, QtCore.Qt.MatchExactly)

        self.window().lib_ref.view_model.setData(
            matching_item[0], self.metadata['last_accessed'], QtCore.Qt.UserRole + 12)

    def set_scroll_value(self, switch_widgets=True, search_data=None):
        # TODO
        # Bookmark navigation does not work in case 2 entries in the same
        # chapter are clicked successively

        if self.sender().objectName() == 'tabWidget':
            return

        if switch_widgets:
            previous_widget = self.window().tabWidget.currentWidget()
            self.window().tabWidget.setCurrentWidget(self)

        scroll_value = self.metadata['position']['scroll_value']
        if search_data:
            scroll_value = search_data[0]

        # Scroll a little ahead
        # This avoids confusion with potentially duplicate phrases
        # And the found result is at the top of the window
        scroll_position = scroll_value * self.contentView.verticalScrollBar().maximum()
        self.contentView.verticalScrollBar().setValue(scroll_position * 1.1)

        search_text = self.metadata['position']['last_visible_text']
        if search_data:
            search_text = search_data[1]

        if search_text:
            self.contentView.find(search_text)

        text_cursor = self.contentView.textCursor()
        text_cursor.clearSelection()
        self.contentView.setTextCursor(text_cursor)

        if switch_widgets:
            self.window().tabWidget.setCurrentWidget(previous_widget)

    def generate_position(self):
        total_chapters = len(self.metadata['content'].keys())
        # TODO
        # Calculate lines to incorporate into progress

        self.metadata['position'] = {
            'current_chapter': 1,
            'total_chapters': total_chapters,
            'scroll_value': 0,
            'last_visible_text': None}

    def generate_keyboard_shortcuts(self):
        self.next_chapter = QtWidgets.QShortcut(
            QtGui.QKeySequence('Right'), self.contentView)
        self.next_chapter.setObjectName('nextChapter')
        self.next_chapter.activated.connect(self.sneaky_change)

        self.prev_chapter = QtWidgets.QShortcut(
            QtGui.QKeySequence('Left'), self.contentView)
        self.prev_chapter.setObjectName('prevChapter')
        self.prev_chapter.activated.connect(self.sneaky_change)

        self.go_fs = QtWidgets.QShortcut(
            QtGui.QKeySequence('F11'), self.contentView)
        self.go_fs.activated.connect(self.go_fullscreen)

        self.exit_fs = QtWidgets.QShortcut(
            QtGui.QKeySequence('Escape'), self.contentView)
        self.exit_fs.setContext(QtCore.Qt.ApplicationShortcut)
        self.exit_fs.activated.connect(self.exit_fullscreen)

        # self.exit_all = QtWidgets.QShortcut(
        #     QtGui.QKeySequence('Ctrl+Q'), self.contentView)
        # self.exit_all.activated.connect(self.sneaky_exit)

    def go_fullscreen(self):
        if self.contentView.windowState() == QtCore.Qt.WindowFullScreen:
            self.exit_fullscreen()
            return

        self.contentView.setWindowFlags(QtCore.Qt.Window)
        self.contentView.setWindowState(QtCore.Qt.WindowFullScreen)
        self.contentView.show()
        self.window().hide()

    def exit_fullscreen(self):
        self.window().show()
        self.contentView.setWindowFlags(QtCore.Qt.Widget)
        self.contentView.setWindowState(QtCore.Qt.WindowNoState)
        self.contentView.show()

    def change_chapter_tocBox(self):
        chapter_name = self.window().bookToolBar.tocBox.currentText()
        required_content = self.metadata['content'][chapter_name]

        if self.are_we_doing_images_only:
            self.contentView.loadImage(required_content)
        else:
            self.contentView.clear()
            self.contentView.setHtml(required_content)

    def format_view(self, font, font_size, foreground,
                    background, padding, line_spacing,
                    text_alignment):

        if self.are_we_doing_images_only:
            # Tab color does not need to be set separately in case
            # no padding is set for the viewport of a QGraphicsView
            # and image resizing in done in the pixmap
            my_qbrush = QtGui.QBrush(QtCore.Qt.SolidPattern)
            my_qbrush.setColor(background)
            self.contentView.setBackgroundBrush(my_qbrush)
            self.contentView.resizeEvent()

        else:
            self.contentView.setStyleSheet(
                "QTextEdit {{font-family: {0}; font-size: {1}px; color: {2}; background-color: {3}}}".format(
                    font, font_size, foreground.name(), background.name()))

            # Line spacing
            # Set line spacing per a block format
            # This is proportional line spacing so assume a divisor of 100
            block_format = QtGui.QTextBlockFormat()
            block_format.setLineHeight(
                line_spacing, QtGui.QTextBlockFormat.ProportionalHeight)

            # Give options for alignment
            alignment_dict = {
                'left': QtCore.Qt.AlignLeft,
                'right': QtCore.Qt.AlignRight,
                'center': QtCore.Qt.AlignCenter,
                'justify': QtCore.Qt.AlignJustify}
            block_format.setAlignment(alignment_dict[text_alignment])

            # Also for padding
            # Using setViewPortMargins for this disables scrolling in the margins
            block_format.setLeftMargin(padding)
            block_format.setRightMargin(padding)

            this_cursor = self.contentView.textCursor()
            this_cursor.movePosition(QtGui.QTextCursor.Start, 0, 1)

            # Iterate over the entire document block by block
            # The document ends when the cursor position can no longer be incremented
            while True:
                old_position = this_cursor.position()
                this_cursor.mergeBlockFormat(block_format)
                this_cursor.movePosition(QtGui.QTextCursor.NextBlock, 0, 1)
                new_position = this_cursor.position()
                if old_position == new_position:
                    break

    def toggle_bookmarks(self):
        if self.dockWidget.isVisible():
            self.dockWidget.hide()
        else:
            self.dockWidget.show()

    def add_bookmark(self):
        identifier = uuid.uuid4().hex[:10]
        description = 'New bookmark'

        if self.are_we_doing_images_only:
            chapter = self.metadata['position']['current_chapter']
            search_data = (0, None)
        else:
            chapter, scroll_position, visible_text = self.contentView.record_scroll_position(True)
            search_data = (scroll_position, visible_text)

        self.metadata['bookmarks'][identifier] = {
            'chapter': chapter,
            'search_data': search_data,
            'description': description}

        self.add_bookmark_to_model(
            description, chapter, search_data, identifier)
        self.dockWidget.setVisible(True)

    def add_bookmark_to_model(self, description, chapter, search_data, identifier):
        bookmark = QtGui.QStandardItem()
        bookmark.setData(description, QtCore.Qt.DisplayRole)

        bookmark.setData(chapter, QtCore.Qt.UserRole)
        bookmark.setData(search_data, QtCore.Qt.UserRole + 1)
        bookmark.setData(identifier, QtCore.Qt.UserRole + 2)

        self.bookmark_model.appendRow(bookmark)
        self.update_bookmark_proxy_model()

    def navigate_to_bookmark(self, index):
        if not index.isValid():
            return

        chapter = self.proxy_model.data(index, QtCore.Qt.UserRole)
        search_data = self.proxy_model.data(index, QtCore.Qt.UserRole + 1)

        self.window().bookToolBar.tocBox.setCurrentIndex(chapter - 1)
        if not self.are_we_doing_images_only:
            self.set_scroll_value(False, search_data)

    def generate_bookmark_model(self):
        # TODO
        # Sorting is not working correctly

        for i in self.metadata['bookmarks'].items():
            self.add_bookmark_to_model(
                i[1]['description'],
                i[1]['chapter'],
                i[1]['search_data'],
                i[0])

        self.generate_bookmark_proxy_model()

    def generate_bookmark_proxy_model(self):
        self.proxy_model.setSourceModel(self.bookmark_model)
        self.proxy_model.setSortCaseSensitivity(False)
        self.proxy_model.setSortRole(QtCore.Qt.UserRole)
        self.dockListView.setModel(self.proxy_model)

    def update_bookmark_proxy_model(self):
        self.proxy_model.invalidateFilter()
        self.proxy_model.setFilterParams(
            self.window().bookToolBar.searchBar.text())
        self.proxy_model.setFilterFixedString(
            self.window().bookToolBar.searchBar.text())

    def hide_mouse(self):
        self.contentView.setCursor(QtCore.Qt.BlankCursor)

    def sneaky_change(self):
        direction = -1
        if self.sender().objectName() == 'nextChapter':
            direction = 1

        self.contentView.common_functions.change_chapter(
            direction, True)

    def sneaky_exit(self):
        self.contentView.hide()
        self.window().closeEvent()


class PliantQGraphicsView(QtWidgets.QGraphicsView):
    def __init__(self, main_window, parent=None):
        super(PliantQGraphicsView, self).__init__(parent)
        self.main_window = main_window
        self.parent = parent
        self.image_pixmap = None
        self.ignore_wheel_event = False
        self.ignore_wheel_event_number = 0
        self.setDragMode(QtWidgets.QGraphicsView.ScrollHandDrag)
        self.common_functions = PliantWidgetsCommonFunctions(
            self, self.main_window)
        self.setMouseTracking(True)

    def loadImage(self, image_path):
        # TODO
        # Cache 4 images
        # For single page view: 1 before, 2 after
        # For double page view: 1 before, 1 after
        # Image panning with mouse

        self.image_pixmap = QtGui.QPixmap()
        self.image_pixmap.load(image_path)
        self.resizeEvent()

    def resizeEvent(self, event=None):
        if not self.image_pixmap:
            return

        zoom_mode = self.main_window.comic_profile['zoom_mode']
        padding = self.main_window.comic_profile['padding']

        if zoom_mode == 'fitWidth':
            available_width = self.viewport().width()
            image_pixmap = self.image_pixmap.scaledToWidth(
                available_width, QtCore.Qt.SmoothTransformation)

        elif zoom_mode == 'originalSize':
            image_pixmap = self.image_pixmap

            new_padding = (self.viewport().width() - image_pixmap.width()) // 2
            if new_padding < 0:  # The image is larger than the viewport
                self.main_window.comic_profile['padding'] = 0
            else:
                self.main_window.comic_profile['padding'] = new_padding

        elif zoom_mode == 'bestFit':
            available_width = self.viewport().width()
            available_height = self.viewport().height()

            image_pixmap = self.image_pixmap.scaled(
                available_width, available_height,
                QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

            self.main_window.comic_profile['padding'] = (
                self.viewport().width() - image_pixmap.width()) // 2

        elif zoom_mode == 'manualZoom':
            available_width = self.viewport().width() - 2 * padding
            image_pixmap = self.image_pixmap.scaledToWidth(
                available_width, QtCore.Qt.SmoothTransformation)

        graphics_scene = QtWidgets.QGraphicsScene()
        graphics_scene.addPixmap(image_pixmap)

        self.setScene(graphics_scene)
        self.show()

    def wheelEvent(self, event):
        self.common_functions.wheelEvent(event, True)

    def keyPressEvent(self, event):
        # This function is sufficiently different to warrant
        # exclusion from the common functions class
        if event.key() == 32:  # Spacebar press
            vertical = self.verticalScrollBar().value()
            maximum = self.verticalScrollBar().maximum()

            if vertical == maximum:
                self.common_functions.change_chapter(1, True)
            else:
                # Increment by following value
                scroll_increment = int((maximum - 0) / 2)
                self.verticalScrollBar().setValue(vertical + scroll_increment)

    def mouseMoveEvent(self, event):
        self.setCursor(QtCore.Qt.ArrowCursor)
        self.parent.mouse_hide_timer.start(3000)


class PliantQTextBrowser(QtWidgets.QTextBrowser):
    def __init__(self, main_window, parent=None):
        super(PliantQTextBrowser, self).__init__(parent)
        self.main_window = main_window
        self.parent = parent
        self.ignore_wheel_event = False
        self.ignore_wheel_event_number = 0
        self.common_functions = PliantWidgetsCommonFunctions(
            self, self.main_window)
        self.verticalScrollBar().sliderMoved.connect(self.record_scroll_position)
        self.setMouseTracking(True)

    def wheelEvent(self, event):
        self.record_scroll_position()
        self.common_functions.wheelEvent(event, False)

    def keyPressEvent(self, event):
        if event.key() == 32:
            self.record_scroll_position()

            if self.verticalScrollBar().value() == self.verticalScrollBar().maximum():
                self.common_functions.change_chapter(1, True)
            else:
                QtWidgets.QTextEdit.keyPressEvent(self, event)

        else:
            QtWidgets.QTextEdit.keyPressEvent(self, event)

    def record_scroll_position(self, return_as_bookmark=False):
        vertical = self.verticalScrollBar().value()
        maximum = self.verticalScrollBar().maximum()

        self.parent.metadata['position']['scroll_value'] = 1
        if maximum != 0:
            self.parent.metadata['position']['scroll_value'] = (vertical / maximum)

        cursor = self.cursorForPosition(QtCore.QPoint(0, 0))
        bottom_right = QtCore.QPoint(self.viewport().width() - 1, self.viewport().height())
        bottom_right_cursor = self.cursorForPosition(bottom_right).position()
        cursor.setPosition(bottom_right_cursor, QtGui.QTextCursor.KeepAnchor)
        visible_text = cursor.selectedText()

        if len(visible_text) > 50:
            visible_text = visible_text[:51]

        if return_as_bookmark:
            return (self.parent.metadata['position']['current_chapter'],
                    self.parent.metadata['position']['scroll_value'],
                    visible_text)
        else:
            self.parent.metadata['position']['last_visible_text'] = visible_text

    # def mouseMoveEvent(self, event):
        # TODO
        # This does not work as expected
        # event.accept()
        # self.setCursor(QtCore.Qt.ArrowCursor)
        # self.parent.mouse_hide_timer.start(3000)


class PliantWidgetsCommonFunctions():
    def __init__(self, parent_widget, main_window):
        self.pw = parent_widget
        self.main_window = main_window

    def wheelEvent(self, event, are_we_doing_images_only):
        ignore_events = 20
        if are_we_doing_images_only:
            ignore_events = 10

        if self.pw.ignore_wheel_event:
            self.pw.ignore_wheel_event_number += 1
            if self.pw.ignore_wheel_event_number > ignore_events:
                self.pw.ignore_wheel_event = False
                self.pw.ignore_wheel_event_number = 0
            return

        if are_we_doing_images_only:
            QtWidgets.QGraphicsView.wheelEvent(self.pw, event)
        else:
            QtWidgets.QTextBrowser.wheelEvent(self.pw, event)

        # Since this is a delta on a mouse move event, it cannot ever be 0
        vertical_pdelta = event.pixelDelta().y()
        if vertical_pdelta > 0:
            moving_up = True
        elif vertical_pdelta < 0:
            moving_up = False

        if abs(vertical_pdelta) > 80:  # Adjust sensitivity here
            # Implies that no scrollbar movement is possible
            if self.pw.verticalScrollBar().value() == self.pw.verticalScrollBar().maximum() == 0:
                if moving_up:
                    self.change_chapter(-1)
                else:
                    self.change_chapter(1)

            # Implies that the scrollbar is at the bottom
            elif self.pw.verticalScrollBar().value() == self.pw.verticalScrollBar().maximum():
                if not moving_up:
                    self.change_chapter(1)

            # Implies scrollbar is at the top
            elif self.pw.verticalScrollBar().value() == 0:
                if moving_up:
                    self.change_chapter(-1)

    def change_chapter(self, direction, was_button_pressed=None):
        current_toc_index = self.main_window.bookToolBar.tocBox.currentIndex()
        max_toc_index = self.main_window.bookToolBar.tocBox.count() - 1

        if (current_toc_index < max_toc_index and direction == 1) or (
                current_toc_index > 0 and direction == -1):
            self.main_window.bookToolBar.tocBox.setCurrentIndex(current_toc_index + direction)

            # Set page position depending on if the chapter number is increasing or decreasing
            if direction == 1 or was_button_pressed:
                self.pw.verticalScrollBar().setValue(0)
            else:
                self.pw.verticalScrollBar().setValue(
                    self.pw.verticalScrollBar().maximum())

            if not was_button_pressed:
                self.pw.ignore_wheel_event = True


class LibraryDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, temp_dir, parent=None):
        super(LibraryDelegate, self).__init__(parent)
        self.temp_dir = temp_dir
        self.parent = parent

    def paint(self, painter, option, index):
        # This is a hint for the future
        # Color icon slightly red
        # if option.state & QtWidgets.QStyle.State_Selected:
            # painter.fillRect(option.rect, QtGui.QColor().fromRgb(255, 0, 0, 20))

        option = option.__class__(option)
        file_exists = index.data(QtCore.Qt.UserRole + 5)
        position = index.data(QtCore.Qt.UserRole + 7)

        # The shadow pixmap currently is set to 420 x 600
        # Only draw the cover shadow in case the setting is enabled
        if self.parent.settings['cover_shadows']:
            shadow_pixmap = QtGui.QPixmap()
            shadow_pixmap.load(':/images/gray-shadow.png')
            shadow_pixmap = shadow_pixmap.scaled(160, 230, QtCore.Qt.IgnoreAspectRatio)
            shadow_x = option.rect.topLeft().x() + 10
            shadow_y = option.rect.topLeft().y() - 5
            painter.setOpacity(.7)
            painter.drawPixmap(shadow_x, shadow_y, shadow_pixmap)
            painter.setOpacity(1)

        if not file_exists:
            painter.setOpacity(.7)
            QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)
            read_icon = pie_chart.pixmapper(-1, None, None, 36)
            x_draw = option.rect.bottomRight().x() - 30
            y_draw = option.rect.bottomRight().y() - 35
            painter.drawPixmap(x_draw, y_draw, read_icon)
            painter.setOpacity(1)
            return

        QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)
        if position:
            current_chapter = position['current_chapter']
            total_chapters = position['total_chapters']

            read_icon = pie_chart.pixmapper(
                current_chapter, total_chapters, self.temp_dir, 36)

            x_draw = option.rect.bottomRight().x() - 30
            y_draw = option.rect.bottomRight().y() - 35
            if current_chapter != 1:
                painter.drawPixmap(x_draw, y_draw, read_icon)


class BookmarkDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(BookmarkDelegate, self).__init__(parent)
        self.parent = parent

    def sizeHint(self, *args):
        dockwidget_width = self.parent.width() - 20
        return QtCore.QSize(dockwidget_width, 50)

    def paint(self, painter, option, index):
        # TODO
        # Alignment of the painted item

        option = option.__class__(option)

        chapter_index = index.data(QtCore.Qt.UserRole)
        chapter_name = self.parent.window().bookToolBar.tocBox.itemText(chapter_index - 1)

        QtWidgets.QStyledItemDelegate.paint(self, painter, option, index)
        painter.drawText(
            option.rect,
            QtCore.Qt.AlignBottom | QtCore.Qt.AlignRight | QtCore.Qt.TextWordWrap,
            '   ' + chapter_name)


class TableViewProgressBarDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, item_model, parent=None):
        super(TableViewProgressBarDelegate, self).__init__(parent)
        self.parent = parent
        self.item_model = item_model

    def paint(self, painter, option, index):
        item = self.item_model.item(index.row())
        position = item.data(QtCore.Qt.UserRole + 7)

        if position:
            current_chapter = position['current_chapter']
            total_chapters = position['total_chapters']

            progress = (current_chapter * 100) // total_chapters

            progressBarOption = QtWidgets.QStyleOptionProgressBar()
            progressBarOption.rect = option.rect
            progressBarOption.minimum = 0
            progressBarOption.maximum = 100
            progressBarOption.progress = progress
            progressBarOption.textVisible = False

            QtWidgets.QApplication.style().drawControl(
                QtWidgets.QStyle.CE_ProgressBar, progressBarOption, painter)


class PliantDockWidget(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super(PliantDockWidget, self).__init__(parent)
        self.parent = parent

    def showEvent(self, event):
        self.parent.window().bookToolBar.bookmarkButton.setChecked(True)

    def hideEvent(self, event):
        self.parent.window().bookToolBar.bookmarkButton.setChecked(False)
