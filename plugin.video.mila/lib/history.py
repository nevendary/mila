# -*- coding: utf-8 -*-
# Search and watch history manager - WITH GROUPED SHOW SUPPORT
import os
import json
import time
import xbmc
import xbmcvfs
import xbmcaddon
from lib.utils import log


class HistoryManager:
    def __init__(self):
        self.addon = xbmcaddon.Addon()
        self.addon_id = self.addon.getAddonInfo('id')
        self.profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))

        # Ensure profile directory exists
        if not xbmcvfs.exists(self.profile_path):
            xbmcvfs.mkdir(self.profile_path)

        self.search_file = os.path.join(self.profile_path, 'search_history.json')
        self.watch_file = os.path.join(self.profile_path, 'watch_history.json')

        # Get max items from settings (with defaults)
        try:
            self.max_search_items = int(self.addon.getSetting('max_search_items')) or 20
        except Exception:
            self.max_search_items = 20

        try:
            self.max_watch_items = int(self.addon.getSetting('max_watch_items')) or 50
        except Exception:
            self.max_watch_items = 50

    # ===== SEARCH HISTORY =====

    def add_search(self, query):
        """Add search query to history"""
        if not query or query.strip() == '':
            return

        query = query.strip()
        history = self._load_search_history()

        # Remove if already exists
        history = [item for item in history if item['query'].lower() != query.lower()]

        # Add to beginning
        history.insert(0, {
            'query': query,
            'timestamp': time.time()
        })

        # Keep only last max_search_items
        history = history[:self.max_search_items]

        self._save_search_history(history)
        log(f"Added search to history: {query}")

    def get_search_history(self):
        """Get search history"""
        return self._load_search_history()

    def clear_search_history(self):
        """Clear all search history"""
        self._save_search_history([])
        log("Cleared all search history")
        xbmc.executebuiltin('Container.Refresh')

    def remove_search_item(self, query):
        """Remove specific search query from history"""
        if not query:
            return

        history = self._load_search_history()
        history = [item for item in history if item['query'].lower() != query.lower()]
        self._save_search_history(history)
        log(f"Removed search from history: {query}")
        xbmc.executebuiltin('Container.Refresh')

    def _load_search_history(self):
        """Load search history from file"""
        if not xbmcvfs.exists(self.search_file):
            return []

        try:
            with open(self.search_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading search history: {str(e)}")
            return []

    def _save_search_history(self, history):
        """Save search history to file"""
        try:
            with open(self.search_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"Error saving search history: {str(e)}")

    # ===== WATCH HISTORY =====

    def add_watched(self, item):
        """Add item to watch history"""
        history = self._load_watch_history()

        # Create watch entry
        entry = {
            'id': item.get('id'),
            'type': item.get('type'),  # 'movie' or 'episode'
            'title': item.get('title'),
            'year': item.get('year', ''),
            'timestamp': time.time(),
            'tmdb_id': item.get('tmdb_id'),
            'season': item.get('season', 0),
            'episode': item.get('episode', 0),
            'show_title': item.get('show_title', ''),
            'poster': item.get('poster', '')
        }

        # Remove if already exists (based on unique ID)
        if entry['type'] == 'movie':
            history = [i for i in history if not (i.get('type') == 'movie' and i.get('tmdb_id') == entry['tmdb_id'])]
        else:
            history = [i for i in history if not (
                i.get('type') == 'episode' and
                i.get('tmdb_id') == entry['tmdb_id'] and
                i.get('season') == entry['season'] and
                i.get('episode') == entry['episode']
            )]

        # Add to beginning
        history.insert(0, entry)

        # Keep only last max_watch_items
        history = history[:self.max_watch_items]

        self._save_watch_history(history)
        log(f"Added to watch history: {item.get('title')}")

    def get_watch_history(self):
        """Get watch history"""
        return self._load_watch_history()

    def clear_watch_history(self):
        """Clear all watch history"""
        self._save_watch_history([])
        log("Cleared all watch history")
        xbmc.executebuiltin('Container.Refresh')

    def remove_from_watch_history(self, index):
        """Remove specific item from watch history by index"""
        history = self._load_watch_history()
        if 0 <= index < len(history):
            removed = history.pop(index)
            self._save_watch_history(history)
            log(f"Removed from watch history: {removed.get('title')}")
            xbmc.executebuiltin('Container.Refresh')

    def _load_watch_history(self):
        """Load watch history from file"""
        if not xbmcvfs.exists(self.watch_file):
            return []

        try:
            with open(self.watch_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log(f"Error loading watch history: {str(e)}")
            return []

    def _save_watch_history(self, history):
        """Save watch history to file"""
        try:
            with open(self.watch_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log(f"Error saving watch history: {str(e)}")