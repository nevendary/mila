# -*- coding: utf-8 -*-
# Module: default
# Author: nevendary + cache-sk + Ultra Simple
# License: AGPL v.3

import sys
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import requests
from xml.etree import ElementTree as ET
import hashlib
from md5crypt import md5crypt
import traceback
import json
import re
import uuid

try:
    from urllib import urlencode
    from urlparse import parse_qsl
except ImportError:
    from urllib.parse import urlencode, parse_qsl

# Global variables
_url = sys.argv[0]
_handle = int(sys.argv[1])
_addon = xbmcaddon.Addon()
_session = requests.Session()
_session.headers.update({
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://webshare.cz/'
})

# API Server URL
API_SERVER_URL = _addon.getSetting('server_url') or "http://192.168.1.68:8000"

def log(msg):
    xbmc.log("[MILA] " + str(msg), xbmc.LOGINFO)

def get_url(**kwargs):
    return _url + '?' + urlencode(kwargs)

def popinfo(message):
    xbmcgui.Dialog().notification(_addon.getAddonInfo('name'), message, xbmcgui.NOTIFICATION_INFO, 3000)

def fetch_from_server(endpoint):
    try:
        url = API_SERVER_URL + endpoint
        response = _session.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        log(f"Error fetching {endpoint}: {str(e)}")
    return None

# Webshare login/playback
def login():
    username = _addon.getSetting('wsuser')
    password = _addon.getSetting('wspass')
    if not username or not password:
        popinfo("Set username/password")
        return None

    try:
        response = _session.post('https://webshare.cz/api/salt/', data={'username_or_email': username}, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text != 'OK':
            return None

        salt = xml.find('salt').text
        encrypted_pass = hashlib.sha1(md5crypt(password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')).hexdigest()
        pass_digest = hashlib.md5(username.encode('utf-8') + b':Webshare:' + encrypted_pass.encode('utf-8')).hexdigest()

        response = _session.post('https://webshare.cz/api/login/', data={
            'username_or_email': username,
            'password': encrypted_pass,
            'digest': pass_digest,
            'keep_logged_in': 1
        }, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text == 'OK':
            return xml.find('token').text
    except Exception as e:
        log(f"Login error: {str(e)}")

    return None

def get_stream_link(ident, token):
    duuid = _addon.getSetting('duuid') or str(uuid.uuid4())
    _addon.setSetting('duuid', duuid)

    try:
        response = _session.post('https://webshare.cz/api/file_link/', data={
            'ident': ident,
            'wst': token,
            'download_type': 'video_stream',
            'device_uuid': duuid
        }, timeout=10)
        xml = ET.fromstring(response.content)
        if xml.find('status').text == 'OK':
            return xml.find('link').text
    except Exception as e:
        log(f"Stream link error: {str(e)}")

    return None

def play_video(ident, title):
    token = login()
    if not token:
        popinfo("Login failed")
        return

    link = get_stream_link(ident, token)
    if not link:
        popinfo("No stream link")
        return

    # Create playable URL with auth
    play_url = link + "|Cookie=wst=" + token

    li = xbmcgui.ListItem(label=title, path=play_url)
    li.setProperty('IsPlayable', 'true')
    li.setMimeType('video/mp4')
    li.setContentLookup(False)

    xbmcplugin.setResolvedUrl(_handle, True, li)

def get_metadata_from_api(stream):
    """Get metadata from API response or extract from filename"""
    filename = stream.get('filename', '')

    # Use quality from API if available
    quality = stream.get('quality', 'Unknown')

    # Extract additional info from filename
    info = {
        'quality': quality,
        'resolution': quality,  # Same as quality for now
        'audio_channels': '',
        'audio_codec': '',
        'languages': [],
        'source': '',
        'hdr': False,
        'size_mb': int(stream.get('size', 0)) / (1024 * 1024)
    }

    # Extract audio channels from filename
    channel_patterns = [
        (r'(7\.1|7-1)', '7.1'),
        (r'(5\.1|5-1)', '5.1'),
        (r'(2\.0|2-0|stereo)', '2.0'),
    ]

    for pattern, channel in channel_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            info['audio_channels'] = channel
            break

    # Extract audio codec
    codec_patterns = [
        (r'(DTS-HD MA|DTSHDMA)', 'DTS-HD MA'),
        (r'(TrueHD|ATMOS)', 'TrueHD/ATMOS'),
        (r'(DTS-HD|DTSHD)', 'DTS-HD'),
        (r'(DTS)', 'DTS'),
        (r'(AC3|DD)', 'AC3'),
        (r'(AAC)', 'AAC'),
        (r'(MP3)', 'MP3')
    ]

    for pattern, codec in codec_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            info['audio_codec'] = codec
            break

    # Extract languages - prioritize from API if available, else parse filename
    if 'languages' in stream:
        info['languages'] = stream['languages']
    else:
        # Parse from filename
        lang_patterns = [
            (r'(CZ\.|CZSK|CZ-SK|Czech|cesky|česky)', 'Czech'),
            (r'(SK\.|Slovak|slovensky)', 'Slovak'),
            (r'(ENG\.|English|EN\.)', 'English'),
            (r'(DE\.|German|GER\.|německy)', 'German'),
            (r'(PL\.|Polish|polsky)', 'Polish'),
            (r'(HU\.|Hungarian|maďarsky)', 'Hungarian'),
            (r'(FR\.|French|francouzsky)', 'French'),
            (r'(ES\.|Spanish|španělsky)', 'Spanish'),
            (r'(multi|MULTI|vícejazyčný)', 'Multi'),
            (r'(dabing|dabingem|DAB)', 'Dubbed')
        ]

        for pattern, lang in lang_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                if lang not in info['languages']:
                    info['languages'].append(lang)

    # Extract HDR
    if re.search(r'(HDR|hdr)', filename):
        info['hdr'] = True
        info['quality'] += ' HDR'

    # Extract source
    source_patterns = [
        (r'(BluRay|BLURAY|BDrip|BD-rip)', 'BluRay'),
        (r'(WEB-DL|WEB\.DL|WEBRip|WEBRIP)', 'WEB'),
        (r'(HDTV|HDTVRip|TVrip)', 'HDTV'),
        (r'(DVDrip|DVD|DVD-Rip)', 'DVD'),
        (r'(CAM|TS|TELESYNC|TC)', 'CAM')
    ]

    for pattern, source in source_patterns:
        if re.search(pattern, filename, re.IGNORECASE):
            info['source'] = source
            break

    return info

def rank_streams(streams):
    """Rank streams based on user preferences"""
    preferred_lang = _addon.getSetting('preferred_language') or 'English'
    max_quality = _addon.getSetting('max_quality') or '4K'
    prefer_hdr = _addon.getSetting('prefer_hdr') == 'true'
    min_audio_channels = _addon.getSetting('min_audio_channels') or '2.0'
    autoplay_resolution = _addon.getSetting('autoplay_resolution') or '1080p'

    # Map quality to numeric value for comparison
    quality_values = {
        'Unknown': 1,
        '480p': 2,
        '720p': 3,
        '1080p': 4,
        '4K': 5,
        '4K HDR': 6
    }

    max_quality_value = quality_values.get(max_quality, 5)
    target_quality_value = quality_values.get(autoplay_resolution, 4)

    ranked_streams = []
    for i, stream in enumerate(streams):
        score = 0
        filename = stream.get('filename', '')

        info = get_metadata_from_api(stream)

        # Quality scoring - target quality gets highest score
        quality_value = quality_values.get(info['quality'].split()[0] if ' ' in info['quality'] else info['quality'], 1)

        if quality_value <= max_quality_value:
            # Score based on proximity to target quality
            diff = abs(quality_value - target_quality_value)
            if diff == 0:  # Exact match
                score += 100
            elif diff == 1:  # Close match
                score += 80
            elif diff == 2:  # Somewhat close
                score += 60
            else:  # Further away
                score += 40 - (diff * 5)
        else:
            # Penalty for exceeding max quality
            score -= 30

        # Language scoring
        if preferred_lang != 'Any':
            if preferred_lang in info['languages']:
                score += 150  # High priority for preferred language
            elif info['languages']:
                # Some language present but not preferred
                if 'Czech' in info['languages'] or 'Slovak' in info['languages']:
                    score += 50  # Local languages get medium priority
                else:
                    score += 20  # Other languages
        else:
            # Any language - just give points for having some language info
            if info['languages']:
                score += 30

        # HDR scoring
        if info['hdr'] and prefer_hdr:
            score += 25
        elif info['hdr'] and not prefer_hdr:
            score -= 10

        # Audio scoring
        if info['audio_channels']:
            if info['audio_channels'] in ['7.1', '5.1']:
                score += 30
            elif info['audio_channels'] == min_audio_channels:
                score += 15
            elif info['audio_codec'] in ['DTS-HD MA', 'TrueHD/ATMOS']:
                score += 20  # Bonus for high-quality audio codecs

        # Source scoring
        if info['source'] == 'BluRay':
            score += 20
        elif info['source'] == 'WEB':
            score += 15
        elif info['source'] == 'HDTV':
            score += 10

        # File size scoring (larger usually means better quality)
        if info['size_mb'] > 100:
            # Max 20 points for size, scaled logarithmically
            size_score = min(20, info['size_mb'] / 50)
            score += size_score

        ranked_streams.append({
            'stream': stream,
            'score': score,
            'info': info,
            'size_mb': info['size_mb'],
            'index': i
        })

    # Sort by score descending
    ranked_streams.sort(key=lambda x: x['score'], reverse=True)

    return ranked_streams

def get_autoplay_stream(streams):
    """Select the best stream based on preferences"""
    if not streams:
        return None

    ranked = rank_streams(streams)

    # Get the top-ranked stream if it has a decent score
    if ranked and ranked[0]['score'] >= 50:  # Minimum score threshold
        return ranked[0]['stream']

    # Fallback: try to find any stream with preferred language
    preferred_lang = _addon.getSetting('preferred_language') or 'English'
    if preferred_lang != 'Any':
        for ranked_stream in ranked:
            info = ranked_stream['info']
            if preferred_lang in info['languages']:
                return ranked_stream['stream']

    # Final fallback to first stream
    return streams[0] if streams else None

def format_stream_label(stream, info, index, size_mb):
    """Create a detailed label for stream selection"""
    label_parts = []

    # Index
    label_parts.append(f"{index+1}.")

    # Quality (from API)
    if info['quality'] != 'Unknown':
        quality_display = info['quality']
        # Add HDR indicator if present
        if info['hdr'] and 'HDR' not in quality_display:
            quality_display += ' HDR'
        label_parts.append(f"[B]{quality_display}[/B]")

    # Source
    if info['source']:
        label_parts.append(f"[{info['source']}]")

    # Languages
    if info['languages']:
        langs = '/'.join(info['languages'][:2])  # Show max 2 languages
        if len(info['languages']) > 2:
            langs += '+'
        label_parts.append(f"({langs})")

    # Audio
    audio_parts = []
    if info['audio_channels']:
        audio_parts.append(info['audio_channels'])
    if info['audio_codec']:
        audio_parts.append(info['audio_codec'])
    if audio_parts:
        label_parts.append(f"[I]{' '.join(audio_parts)}[/I]")

    # Size
    if size_mb > 0:
        if size_mb > 1024:
            label_parts.append(f"({size_mb/1024:.1f} GB)")
        else:
            label_parts.append(f"({size_mb:.0f} MB)")

    # Format the full label
    full_label = " ".join(label_parts)

    # Add color coding for quality
    if '4K' in info['quality']:
        full_label = f"[COLOR gold]{full_label}[/COLOR]"
    elif '1080p' in info['quality']:
        full_label = f"[COLOR lime]{full_label}[/COLOR]"
    elif '720p' in info['quality']:
        full_label = f"[COLOR cyan]{full_label}[/COLOR]"

    return full_label

def select_stream_popup(streams, title):
    """Show enhanced popup dialog for stream selection"""
    if not streams:
        popinfo("No streams available")
        return None

    # Rank streams for display order
    ranked_streams = rank_streams(streams)

    # Check if autoplay is enabled
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'
    skip_popup = _addon.getSetting('skip_popup') == 'true'

    # Auto-select if enabled and should skip popup
    if autoplay_enabled and skip_popup and ranked_streams:
        best_stream = ranked_streams[0]['stream']
        play_video(best_stream['ident'], title)
        return best_stream['ident']

    # Prepare items for selection dialog
    items = []
    for ranked in ranked_streams:
        stream = ranked['stream']
        info = ranked['info']
        size_mb = ranked['size_mb']
        index = ranked['index']

        label = format_stream_label(stream, info, index, size_mb)

        # Add star and highlight to the best stream
        if ranked['score'] == ranked_streams[0]['score']:
            label = f"[B][COLOR yellow]★ {label}[/COLOR][/B]"

        items.append((label, stream['ident'], info))

    # Auto-select if enabled but still show popup for brief moment
    if autoplay_enabled and ranked_streams:
        # Show brief notification
        best_info = ranked_streams[0]['info']
        notification_msg = f"Auto-selected: {best_info['quality']}"
        if best_info['languages']:
            notification_msg += f" ({'/'.join(best_info['languages'][:1])})"
        popinfo(notification_msg)

        # Auto-play after short delay
        best_stream = ranked_streams[0]['stream']
        play_video(best_stream['ident'], title)
        return best_stream['ident']

    # Show selection dialog if no autoplay or autoplay failed
    dialog = xbmcgui.Dialog()
    selected = dialog.select(f"Select stream - {title}", [item[0] for item in items])

    if selected >= 0:
        stream_id = items[selected][1]
        stream_info = items[selected][2]

        # Show detailed stream info
        info_text = f"[B]Stream Details:[/B]\n"
        info_text += f"Quality: [B]{stream_info['quality']}[/B]\n"

        if stream_info['languages']:
            info_text += f"Languages: [COLOR yellow]{', '.join(stream_info['languages'])}[/COLOR]\n"

        if stream_info['audio_channels'] or stream_info['audio_codec']:
            audio_info = []
            if stream_info['audio_channels']:
                audio_info.append(stream_info['audio_channels'])
            if stream_info['audio_codec']:
                audio_info.append(stream_info['audio_codec'])
            info_text += f"Audio: [COLOR cyan]{' '.join(audio_info)}[/COLOR]\n"

        if stream_info['source']:
            info_text += f"Source: [COLOR lime]{stream_info['source']}[/COLOR]\n"

        if stream_info['hdr']:
            info_text += f"HDR: [COLOR gold]Yes[/COLOR]\n"

        if stream_info['size_mb'] > 0:
            if stream_info['size_mb'] > 1024:
                info_text += f"Size: {stream_info['size_mb']/1024:.1f} GB\n"
            else:
                info_text += f"Size: {stream_info['size_mb']:.0f} MB\n"

        # Optional: Show info dialog
        show_info = _addon.getSetting('show_stream_info') == 'true'
        if show_info:
            xbmcgui.Dialog().ok("Stream Information", info_text)

        play_video(stream_id, f"{title}")
        return stream_id

    return None

# MAIN MENU
def main_menu():
    xbmcplugin.setPluginCategory(_handle, "MILA")
    xbmcplugin.setContent(_handle, 'files')

    # TV Shows
    li = xbmcgui.ListItem(label="TV Shows")
    li.setArt({'icon': 'DefaultTVShows.png'})
    li.setInfo('video', {'title': "TV Shows"})
    url = get_url(action='tv_shows')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # Movies
    li = xbmcgui.ListItem(label="Movies")
    li.setArt({'icon': 'DefaultMovies.png'})
    li.setInfo('video', {'title': "Movies"})
    url = get_url(action='movies')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # All Content
    li = xbmcgui.ListItem(label="All Content")
    li.setArt({'icon': 'DefaultFolder.png'})
    li.setInfo('video', {'title': "All Content"})
    url = get_url(action='all_content')
    xbmcplugin.addDirectoryItem(_handle, url, li, True)

    # Settings
    li = xbmcgui.ListItem(label="Settings")
    li.setArt({'icon': 'DefaultSettings.png'})
    xbmcplugin.addDirectoryItem(_handle, 'plugin://plugin.video.mila/?action=settings', li, False)

    xbmcplugin.endOfDirectory(_handle)

# TV SHOWS - MINIMAL CHANGES TO MATCH API
def show_tv_shows():
    data = fetch_from_server("/tv_shows")
    if not data or not data.get('tv_shows'):
        popinfo("No TV shows")
        main_menu()
        return

    xbmcplugin.setPluginCategory(_handle, "TV Shows")
    xbmcplugin.setContent(_handle, 'tvshows')

    for show in data['tv_shows']:
        label = show['title']
        if show.get('year'):
            label += f" ({show['year']})"

        # Set basic info with optional extended fields
        info = {
            'title': show['title'],
            'year': int(show.get('year', 0)) if show.get('year') else 0,
            'mediatype': 'tvshow'
        }

        # Add extended info if available (from your API)
        if show.get('description'):
            info['plot'] = show['description']
        elif show.get('description_cz'):
            info['plot'] = show['description_cz']

        if show.get('rating'):
            info['rating'] = float(show['rating'])

        if show.get('vote_count'):
            info['votes'] = str(show['vote_count'])

        if show.get('genres'):
            genres = [g.get('name', '') for g in show.get('genres', []) if g.get('name')]
            if genres:
                info['genre'] = ' / '.join(genres)

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultTVShows.png'})

        # Add poster/backdrop if available
        if show.get('poster'):
            li.setArt({'poster': show['poster']})
        if show.get('backdrop'):
            li.setArt({'fanart': show['backdrop']})

        li.setInfo('video', info)

        url = get_url(action='tv_show', show_id=show['id'])
        xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

def show_tv_seasons(params):
    show_id = params.get('show_id')

    if not show_id:
        popinfo("No show ID")
        return

    data = fetch_from_server(f"/tv_shows/{show_id}")
    if not data or not data.get('seasons'):
        popinfo("No seasons")
        return

    title = data.get('title', 'TV Show')
    xbmcplugin.setPluginCategory(_handle, title)
    xbmcplugin.setContent(_handle, 'seasons')

    for season in sorted(data['seasons'], key=lambda x: x['season']):
        label = f"Season {season['season']}"

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultFolder.png'})

        # Add season info if available
        info = {
            'title': f"Season {season['season']}",
            'mediatype': 'season',
            'season': season['season']
        }

        # Try to get season details
        if data.get('seasons_info'):
            for season_info in data['seasons_info']:
                if season_info.get('season_number') == season['season']:
                    if season_info.get('name'):
                        info['title'] = season_info['name']
                    if season_info.get('overview'):
                        info['plot'] = season_info['overview']
                    elif season_info.get('overview_cz'):
                        info['plot'] = season_info['overview_cz']
                    if season_info.get('air_date'):
                        info['year'] = int(season_info['air_date'][:4]) if season_info['air_date'] else 0
                    if season_info.get('poster_path'):
                        li.setArt({'poster': season_info['poster_path']})
                    break

        li.setInfo('video', info)

        url = get_url(action='season', show_id=show_id, season=season['season'])
        xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

def show_episodes(params):
    show_id = params.get('show_id')
    season = params.get('season')

    if not show_id or not season:
        popinfo("Missing parameters")
        return

    # Get the season data
    data = fetch_from_server(f"/tv_shows/{show_id}/seasons/{season}")
    if not data or not data.get('episodes'):
        popinfo(f"No episodes for season {season}")
        return

    show_title = data.get('show_title', 'TV Show')
    xbmcplugin.setPluginCategory(_handle, f"{show_title} - Season {season}")
    xbmcplugin.setContent(_handle, 'episodes')

    # Get show data for episode details
    show_data = fetch_from_server(f"/tv_shows/{show_id}")
    season_details = None
    if show_data and show_data.get('detailed_seasons') and str(season) in show_data['detailed_seasons']:
        season_details = show_data['detailed_seasons'][str(season)]

    for episode in sorted(data['episodes'], key=lambda x: x['episode']):
        ep_num = episode['episode']

        # Default label
        label = f"Episode {ep_num}"

        # Try to get episode details
        episode_details = None
        if season_details and season_details.get('episodes'):
            for ep in season_details['episodes']:
                if ep.get('episode_number') == ep_num:
                    episode_details = ep
                    if ep.get('name'):
                        label = f"Episode {ep_num}: {ep['name']}"
                    break

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultVideo.png'})

        # Set episode info
        info = {
            'title': f"Episode {ep_num}",
            'season': int(season),
            'episode': ep_num,
            'mediatype': 'episode'
        }

        # Add episode details if available
        if episode_details:
            if episode_details.get('name'):
                info['title'] = episode_details['name']
            if episode_details.get('overview'):
                info['plot'] = episode_details['overview']
            elif episode_details.get('overview_cz'):
                info['plot'] = episode_details['overview_cz']
            if episode_details.get('air_date'):
                info['aired'] = episode_details['air_date']
            if episode_details.get('runtime'):
                info['duration'] = episode_details['runtime'] * 60
            if episode_details.get('vote_average'):
                info['rating'] = episode_details['vote_average']
            if episode_details.get('still_path'):
                li.setArt({'thumb': episode_details['still_path']})

        li.setInfo('video', info)

        # Create a playable item
        li.setProperty('IsPlayable', 'true')
        url = get_url(
            action='play_episode',
            show_id=show_id,
            season=season,
            episode=ep_num,
            show_title=show_title
        )

        xbmcplugin.addDirectoryItem(_handle, url, li, False)

    xbmcplugin.endOfDirectory(_handle)

def handle_episode_play(params):
    """Handle episode playback with enhanced stream selection"""
    show_id = params.get('show_id')
    season = params.get('season')
    episode = params.get('episode')
    show_title = params.get('show_title', 'Episode')

    # Get episode streams
    data = fetch_from_server(f"/tv_shows/{show_id}/seasons/{season}/episodes/{episode}")
    if not data or not data.get('streams'):
        popinfo("No streams available")
        return

    streams = data['streams']
    title = f"{show_title} S{season}E{episode}"

    # Check if we should autoplay
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'

    if len(streams) == 1:
        # Direct play if only one stream
        stream = streams[0]
        play_video(stream['ident'], title)
    elif autoplay_enabled:
        # Try to autoplay
        best_stream = get_autoplay_stream(streams)
        if best_stream:
            play_video(best_stream['ident'], title)
        else:
            select_stream_popup(streams, title)
    else:
        # Show popup selection
        select_stream_popup(streams, title)

# MOVIES - MINIMAL CHANGES TO MATCH API
def show_movies():
    data = fetch_from_server("/movies")
    if not data or not data.get('movies'):
        popinfo("No movies")
        main_menu()
        return

    xbmcplugin.setPluginCategory(_handle, "Movies")
    xbmcplugin.setContent(_handle, 'movies')

    for movie in data['movies']:
        label = movie['title']
        if movie.get('year'):
            label += f" ({movie['year']})"

        # Set basic info with optional extended fields
        info = {
            'title': movie['title'],
            'year': int(movie.get('year', 0)) if movie.get('year') else 0,
            'mediatype': 'movie'
        }

        # Add extended info if available (from your API)
        if movie.get('description'):
            info['plot'] = movie['description']
        elif movie.get('description_cz'):
            info['plot'] = movie['description_cz']

        if movie.get('rating'):
            info['rating'] = float(movie['rating'])

        if movie.get('vote_count'):
            info['votes'] = str(movie['vote_count'])

        if movie.get('runtime'):
            info['duration'] = movie['runtime'] * 60

        if movie.get('release_date'):
            info['premiered'] = movie['release_date']

        if movie.get('genres'):
            genres = [g.get('name', '') for g in movie.get('genres', []) if g.get('name')]
            if genres:
                info['genre'] = ' / '.join(genres)

        if movie.get('cast'):
            cast = []
            for actor in movie.get('cast', [])[:10]:
                if actor.get('name'):
                    cast.append(actor['name'])
            if cast:
                info['cast'] = cast

        if movie.get('crew'):
            directors = []
            for crew in movie.get('crew', []):
                if crew.get('job') == 'Director' and crew.get('name'):
                    directors.append(crew['name'])
            if directors:
                info['director'] = ' / '.join(directors)

        li = xbmcgui.ListItem(label=label)
        li.setArt({'icon': 'DefaultMovies.png'})

        # Add poster/backdrop if available
        if movie.get('poster'):
            li.setArt({'poster': movie['poster']})
        if movie.get('backdrop'):
            li.setArt({'fanart': movie['backdrop']})

        li.setInfo('video', info)

        # Create a playable item
        li.setProperty('IsPlayable', 'true')
        url = get_url(
            action='play_movie',
            movie_id=movie['id'],
            movie_title=movie['title'],
            movie_year=movie.get('year', '')
        )

        xbmcplugin.addDirectoryItem(_handle, url, li, False)

    xbmcplugin.endOfDirectory(_handle)

def handle_movie_play(params):
    """Handle movie playback with enhanced stream selection"""
    movie_id = params.get('movie_id')
    movie_title = params.get('movie_title', 'Movie')
    movie_year = params.get('movie_year', '')

    if not movie_id:
        popinfo("No movie ID")
        return

    # Get movie streams
    data = fetch_from_server(f"/movies/{movie_id}")
    if not data or not data.get('streams'):
        popinfo("No streams available")
        return

    streams = data['streams']
    title = f"{movie_title} ({movie_year})" if movie_year else movie_title

    # Check if we should autoplay
    autoplay_enabled = _addon.getSetting('autoplay') == 'true'

    if len(streams) == 1:
        # Direct play if only one stream
        stream = streams[0]
        play_video(stream['ident'], title)
    elif autoplay_enabled:
        # Try to autoplay
        best_stream = get_autoplay_stream(streams)
        if best_stream:
            play_video(best_stream['ident'], title)
        else:
            select_stream_popup(streams, title)
    else:
        # Show popup selection
        select_stream_popup(streams, title)

# ALL CONTENT - BROWSABLE VIEW (NO KEYBOARD NEEDED)
def show_all_content():
    """Show all content that can be browsed - no keyboard"""
    xbmcplugin.setPluginCategory(_handle, "All Content")
    xbmcplugin.setContent(_handle, 'files')

    # Get all data
    movies_data = fetch_from_server("/movies")
    tv_shows_data = fetch_from_server("/tv_shows")

    movies = movies_data.get('movies', []) if movies_data else []
    tv_shows = tv_shows_data.get('tv_shows', []) if tv_shows_data else []

    # Show Movies section
    if movies:
        li = xbmcgui.ListItem(label="[COLOR yellow]--- MOVIES ---[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)

        for movie in movies[:50]:  # Limit to 50 movies
            label = movie['title']
            if movie.get('year'):
                label += f" ({movie['year']})"

            li = xbmcgui.ListItem(label=label)
            li.setArt({'icon': 'DefaultMovies.png'})

            # Add basic info
            info = {
                'title': movie['title'],
                'year': int(movie.get('year', 0)) if movie.get('year') else 0,
                'mediatype': 'movie'
            }

            if movie.get('poster'):
                li.setArt({'poster': movie['poster']})
            if movie.get('backdrop'):
                li.setArt({'fanart': movie['backdrop']})

            li.setInfo('video', info)

            li.setProperty('IsPlayable', 'true')
            url = get_url(
                action='play_movie',
                movie_id=movie['id'],
                movie_title=movie['title'],
                movie_year=movie.get('year', '')
            )

            xbmcplugin.addDirectoryItem(_handle, url, li, False)

    # Show TV Shows section
    if tv_shows:
        li = xbmcgui.ListItem(label="[COLOR yellow]--- TV SHOWS ---[/COLOR]")
        li.setArt({'icon': 'DefaultFolder.png'})
        xbmcplugin.addDirectoryItem(_handle, '', li, False)

        for show in tv_shows[:30]:  # Limit to 30 TV shows
            label = show['title']
            if show.get('year'):
                label += f" ({show['year']})"

            li = xbmcgui.ListItem(label=label)
            li.setArt({'icon': 'DefaultTVShows.png'})

            # Add basic info
            info = {
                'title': show['title'],
                'year': int(show.get('year', 0)) if show.get('year') else 0,
                'mediatype': 'tvshow'
            }

            if show.get('poster'):
                li.setArt({'poster': show['poster']})
            if show.get('backdrop'):
                li.setArt({'fanart': show['backdrop']})

            li.setInfo('video', info)

            url = get_url(action='tv_show', show_id=show['id'])
            xbmcplugin.addDirectoryItem(_handle, url, li, True)

    xbmcplugin.endOfDirectory(_handle)

# ROUTER
def router(paramstring):
    params = dict(parse_qsl(paramstring))

    try:
        action = params.get('action', '')

        if action == 'tv_shows':
            show_tv_shows()
        elif action == 'tv_show':
            show_tv_seasons(params)
        elif action == 'season':
            show_episodes(params)
        elif action == 'play_episode':
            handle_episode_play(params)
        elif action == 'movies':
            show_movies()
        elif action == 'play_movie':
            handle_movie_play(params)
        elif action == 'all_content':
            show_all_content()
        elif action == 'settings':
            _addon.openSettings()
        else:
            main_menu()

    except Exception as e:
        log(f"Router error: {str(e)}")
        traceback.print_exc()
        popinfo("Error occurred")

if __name__ == '__main__':
    router(sys.argv[2][1:] if len(sys.argv) > 2 else '')
