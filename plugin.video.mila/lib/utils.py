# -*- coding: utf-8 -*-
# Utility functions
import xbmc
import xbmcvfs
import xbmcgui
import xbmcaddon
import json
import os
import time
import hashlib

_addon = xbmcaddon.Addon()
_addon_id = _addon.getAddonInfo('id')

# Simple in-memory cache
_memory_cache = {}
_cache_dir = None

def log(msg):
    """Log message to Kodi log"""
    xbmc.log(f"[{_addon_id}] " + str(msg), xbmc.LOGINFO)

def popinfo(message):
    """Show notification"""
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_INFO, 3000)

def poperror(message):
    """Show error notification"""
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_ERROR, 5000)

def get_cache_dir():
    """Get cache directory"""
    global _cache_dir
    if _cache_dir is None:
        profile = xbmcvfs.translatePath(_addon.getAddonInfo('profile'))
        _cache_dir = os.path.join(profile, 'cache')
        if not os.path.exists(_cache_dir):
            os.makedirs(_cache_dir)
    return _cache_dir

def cache_get(key, ttl=3600):
    """Get item from cache"""
    # Check memory cache first
    if key in _memory_cache:
        item = _memory_cache[key]
        if time.time() - item['time'] < ttl:
            return item['data']
    
    # Check disk cache
    cache_file = os.path.join(get_cache_dir(), hashlib.md5(key.encode()).hexdigest() + '.json')
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if time.time() - data.get('time', 0) < ttl:
                # Store in memory
                _memory_cache[key] = {'time': data['time'], 'data': data['data']}
                return data['data']
        except:
            pass
    
    return None

def cache_set(key, data):
    """Save item to cache"""
    # Memory cache
    _memory_cache[key] = {'time': time.time(), 'data': data}
    
    # Disk cache
    try:
        cache_file = os.path.join(get_cache_dir(), hashlib.md5(key.encode()).hexdigest() + '.json')
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({'time': time.time(), 'data': data}, f)
    except:
        pass

def clear_cache():
    """Clear all cache"""
    global _memory_cache
    _memory_cache = {}
    
    cache_dir = get_cache_dir()
    if os.path.exists(cache_dir):
        import shutil
        shutil.rmtree(cache_dir)
        os.makedirs(cache_dir)
    
    popinfo("Cache cleared")
