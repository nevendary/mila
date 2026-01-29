#!/usr/bin/env python3
"""
ORGANIZER: Get movies/TV from TMDB (English & Czech), then search WebShare
With incremental updates, manual content addition, improved search, and WebShare link processing
WITH GITHUB AUTO-UPDATE (using existing git setup)
"""
import json
import requests
import xml.etree.ElementTree as ET
import hashlib
import time
import re
import sys
import traceback
import os
from datetime import datetime
import logging
import threading
import argparse
import unicodedata
from urllib.parse import urlparse, parse_qs
import subprocess  # For GitHub integration
import shutil      # For file operations
import base64
import struct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TMDB_API_KEY = "9567cc1179d493c3b22f0682dbdf2e42"
TMDB_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

# MD5Crypt implementation (replacement for md5crypt module)
def md5crypt(password, salt, magic="$1$"):
    """MD5-based password hash (replacement for md5crypt module)"""
    password = password.encode('utf-8')
    salt = salt.encode('utf-8')
    
    # Start digest 'a'
    m = hashlib.md5()
    m.update(password + magic + salt)
    
    # Start digest 'b'
    m1 = hashlib.md5()
    m1.update(password + salt + password)
    final = m1.digest()
    
    # Add as many characters of digest 'b' to digest 'a'
    for i in range(len(password), 0, -16):
        if i > 16:
            m.update(final)
        else:
            m.update(final[:i])
    
    # Clean bits
    i = len(password)
    while i:
        if i & 1:
            m.update(b'\x00')
        else:
            m.update(password[:1])
        i >>= 1
    
    final = m.digest()
    
    # Now make 1000 passes over the hash
    for i in range(1000):
        m2 = hashlib.md5()
        if i & 1:
            m2.update(password)
        else:
            m2.update(final)
        
        if i % 3:
            m2.update(salt)
        
        if i % 7:
            m2.update(password)
        
        if i & 1:
            m2.update(final)
        else:
            m2.update(password)
        
        final = m2.digest()
    
    # Rearrange the bytes and encode to base64
    rearranged = bytearray(16)
    rearranged[0] = final[0]
    rearranged[1] = final[6]
    rearranged[2] = final[12]
    rearranged[3] = final[1]
    rearranged[4] = final[7]
    rearranged[5] = final[13]
    rearranged[6] = final[2]
    rearranged[7] = final[8]
    rearranged[8] = final[14]
    rearranged[9] = final[3]
    rearranged[10] = final[9]
    rearranged[11] = final[15]
    rearranged[12] = final[4]
    rearranged[13] = final[10]
    rearranged[14] = final[5]
    rearranged[15] = final[11]
    
    # Base64 encode
    base64_chars = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    encoded = []
    for i in range(0, 16, 3):
        v = (rearranged[i] << 16) | (rearranged[i+1] << 8) | rearranged[i+2]
        for j in range(4):
            encoded.append(base64_chars[v & 0x3f])
            v >>= 6
    
    result = magic + salt.decode('utf-8') + "$" + "".join(encoded[:22])
    return result

class TMDBFirstOrganizer:
    def __init__(self, incremental=True, auto_git=True):
        self.base_url = "https://webshare.cz/api/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # Import credentials from config
        try:
            from config import WEBSHARE_USER, WEBSHARE_PASS
            self.username = WEBSHARE_USER
            self.password = WEBSHARE_PASS
        except ImportError:
            print("ERROR: Create config.py with WEBSHARE_USER and WEBSHARE_PASS")
            sys.exit(1)

        self.token = None
        self.tmdb_cache = {}
        self.request_lock = threading.Lock()
        self.last_request_time = 0
        self.min_request_interval = 1.0
        self.incremental = incremental
        self.existing_data = None
        self.output_file = 'kodi_tmdb_cz.json'
        self.auto_git = auto_git  # New: Auto update GitHub

        # New: Manual content storage
        self.manual_content_file = 'manual_content.json'

        # New: Scan progress tracking
        self.scan_status_file = 'scan_status.json'

        # New: Git commit tracking
        self.git_commit_file = 'git_commits.log'

    def load_existing_data(self):
        """Load existing data for incremental updates"""
        if not os.path.exists(self.output_file):
            return {'movies': [], 'tv_shows': [], 'stats': {}, 'last_updated': ''}

        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure proper structure
                if 'movies' not in data:
                    data['movies'] = []
                if 'tv_shows' not in data:
                    data['tv_shows'] = []
                if 'stats' not in data:
                    data['stats'] = {}
                if 'last_updated' not in data:
                    data['last_updated'] = ''

                self.existing_data = data
                return data
        except Exception as e:
            logger.error(f"Error loading existing data: {str(e)}")
            return {'movies': [], 'tv_shows': [], 'stats': {}, 'last_updated': ''}

    def save_data_immediately(self, data):
        """Save data to file immediately with proper formatting"""
        try:
            # Ensure proper structure
            if 'movies' not in data:
                data['movies'] = []
            if 'tv_shows' not in data:
                data['tv_shows'] = []
            if 'stats' not in data:
                data['stats'] = {}
            if 'last_updated' not in data:
                data['last_updated'] = datetime.now().isoformat()

            # Update stats
            data['stats'] = {
                'tv_shows_count': len(data.get('tv_shows', [])),
                'movies_count': len(data.get('movies', [])),
                'total_episodes': sum(len(eps) for show in data.get('tv_shows', []) for eps in show.get('seasons', {}).values()) if data.get('tv_shows') else 0,
                'total_movie_files': sum(len(movie['streams']) for movie in data.get('movies', [])) if data.get('movies') else 0,
                'last_updated': datetime.now().isoformat()
            }
            data['last_updated'] = datetime.now().isoformat()

            # Create backup first
            if os.path.exists(self.output_file):
                backup_file = f"{self.output_file}.backup.{int(time.time())}"
                import shutil
                shutil.copy2(self.output_file, backup_file)

            # Save the file
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            print(f"  ✓ IMMEDIATELY saved to {self.output_file}")
            print(f"    Movies: {len(data.get('movies', []))}, TV Shows: {len(data.get('tv_shows', []))}")
            
            # Auto-update GitHub if enabled
            if self.auto_git:
                self.git_commit_and_push(f"Updated database: {len(data.get('movies', []))} movies, {len(data.get('tv_shows', []))} TV shows")
                
            return True
        except Exception as e:
            logger.error(f"Error saving data immediately: {str(e)}")
            return False

    def git_commit_and_push(self, commit_message):
        """Commit changes to git and push to GitHub - SIMPLIFIED VERSION"""
        try:
            # First check if we're in a git repository
            repo_check = subprocess.run(['git', 'rev-parse', '--is-inside-work-tree'], 
                                      capture_output=True, text=True, cwd=os.getcwd())
            if repo_check.returncode != 0:
                print("  ℹ️ Not in a git repository, skipping GitHub update")
                return False
            
            print("  📦 Committing to git...")
            
            # Add the main JSON file
            add_result = subprocess.run(['git', 'add', self.output_file], 
                                      capture_output=True, text=True, cwd=os.getcwd())
            if add_result.returncode != 0:
                print(f"  ⚠️ Failed to add file to git: {add_result.stderr[:100]}")
                return False
            
            # Check if there are changes
            status_result = subprocess.run(['git', 'status', '--porcelain', self.output_file],
                                         capture_output=True, text=True, cwd=os.getcwd())
            if not status_result.stdout.strip():
                print("  ℹ️ No changes to commit")
                return False
            
            # Also add manual content and scan status files
            for extra_file in [self.manual_content_file, self.scan_status_file, self.git_commit_file]:
                if os.path.exists(extra_file):
                    subprocess.run(['git', 'add', extra_file], 
                                 capture_output=True, text=True, cwd=os.getcwd())
            
            # Commit the changes
            commit_result = subprocess.run(['git', 'commit', '-m', commit_message],
                                         capture_output=True, text=True, cwd=os.getcwd())
            if commit_result.returncode != 0:
                print(f"  ⚠️ Failed to commit: {commit_result.stderr[:100]}")
                return False
            
            print(f"  ✓ Committed: {commit_message}")
            
            # Push to GitHub
            print("  🚀 Pushing to GitHub...")
            push_result = subprocess.run(['git', 'push'],
                                       capture_output=True, text=True, cwd=os.getcwd())
            if push_result.returncode == 0:
                print(f"  ✅ Successfully pushed to GitHub")
                
                # Get the commit hash for logging
                commit_hash_result = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                                  capture_output=True, text=True, cwd=os.getcwd())
                if commit_hash_result.returncode == 0:
                    commit_hash = commit_hash_result.stdout.strip()[:8]
                    # Log the commit
                    with open(self.git_commit_file, 'a') as f:
                        f.write(f"{datetime.now().isoformat()}: {commit_hash} - {commit_message}\n")
                    print(f"  📝 Commit hash: {commit_hash}")
                
                return True
            else:
                print(f"  ❌ Failed to push to GitHub: {push_result.stderr[:100]}")
                return False
                
        except Exception as e:
            print(f"  ⚠️ GitHub update failed: {str(e)}")
            return False

    def load_scan_status(self):
        """Load scan progress status"""
        if os.path.exists(self.scan_status_file):
            try:
                with open(self.scan_status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass

        # Default status
        return {
            'scanned_movies': {},
            'scanned_tv_shows': {},
            'last_movie_scan': {},
            'last_tv_scan': {},
            'total_scanned': 0
        }

    def save_scan_status(self, status):
        """Save scan progress status"""
        with open(self.scan_status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)

    def is_movie_scanned(self, tmdb_id):
        """Check if movie has been scanned recently"""
        status = self.load_scan_status()
        if str(tmdb_id) in status['scanned_movies']:
            last_scan = status['scanned_movies'][str(tmdb_id)]
            # If scanned in last 30 days, skip
            if time.time() - last_scan < 30 * 24 * 3600:
                return True
        return False

    def is_tv_show_scanned(self, tmdb_id):
        """Check if TV show has been scanned recently"""
        status = self.load_scan_status()
        if str(tmdb_id) in status['scanned_tv_shows']:
            last_scan = status['scanned_tv_shows'][str(tmdb_id)]
            # If scanned in last 7 days, skip (TV shows need more frequent checks)
            if time.time() - last_scan < 7 * 24 * 3600:
                return True
        return False

    def mark_movie_scanned(self, tmdb_id):
        """Mark movie as scanned"""
        status = self.load_scan_status()
        status['scanned_movies'][str(tmdb_id)] = time.time()
        status['total_scanned'] = status.get('total_scanned', 0) + 1
        self.save_scan_status(status)

    def mark_tv_show_scanned(self, tmdb_id):
        """Mark TV show as scanned"""
        status = self.load_scan_status()
        status['scanned_tv_shows'][str(tmdb_id)] = time.time()
        status['total_scanned'] = status.get('total_scanned', 0) + 1
        self.save_scan_status(status)

    def load_manual_content(self):
        """Load manually added content"""
        if os.path.exists(self.manual_content_file):
            try:
                with open(self.manual_content_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'movies': [], 'tv_shows': []}
        return {'movies': [], 'tv_shows': []}

    def save_manual_content(self, data):
        """Save manually added content"""
        with open(self.manual_content_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def generate_content_id(self, title, year=""):
        """Generate consistent ID for content (SAME AS KODI ADDON)"""
        text = f"{title.lower()}{year}".strip()
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:8]

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        with self.request_lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < self.min_request_interval:
                sleep_time = self.min_request_interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()

    def login(self):
        """Login to WebShare with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"Logging in to Webshare (attempt {attempt + 1}/{max_retries})...")
                response = self.session.post(
                    f"{self.base_url}salt/",
                    data={'username_or_email': self.username},
                    timeout=30
                )
                xml = ET.fromstring(response.content)

                if xml.find('status').text != 'OK':
                    logger.error(f"Failed to get salt: {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return False

                salt = xml.find('salt').text
                encrypted_pass = hashlib.sha1(
                    md5crypt(self.password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')
                ).hexdigest()
                pass_digest = hashlib.md5(
                    self.username.encode('utf-8') +
                    b':Webshare:' +
                    encrypted_pass.encode('utf-8')
                ).hexdigest()

                response = self.session.post(
                    f"{self.base_url}login/",
                    data={
                        'username_or_email': self.username,
                        'password': encrypted_pass,
                        'digest': pass_digest,
                        'keep_logged_in': 1
                    },
                    timeout=30
                )
                xml = ET.fromstring(response.content)

                if xml.find('status').text == 'OK':
                    self.token = xml.find('token').text
                    logger.info("✓ Login successful")
                    return True
                else:
                    logger.error(f"Login failed: {response.text}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
                        continue
                    return False

            except Exception as e:
                logger.error(f"Login attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return False
        return False

    def get_file_info_from_link_fallback(self, webshare_link):
        """Alternative method to get file info using different approach - FIXED VERSION"""
        try:
            # Extract identifier from URL
            file_ident = None

            # Try multiple extraction patterns
            patterns = [
                r'webshare\.cz/[#/]*file/([a-zA-Z0-9]+)',
                r'/file/([a-zA-Z0-9]+)',
                r'ident=([a-zA-Z0-9]+)',
                r'id=([a-zA-Z0-9]+)',
            ]

            for pattern in patterns:
                match = re.search(pattern, webshare_link)
                if match:
                    file_ident = match.group(1)
                    break

            if not file_ident:
                print(f"  ERROR: Could not extract file ID from URL")
                return None

            print(f"  Extracted file ID (fallback): {file_ident}")

            # Try using search API to find the file
            if not self.token:
                if not self.login():
                    return None

            self._rate_limit()

            # Try to search for the file by its ID
            data = {
                'wst': self.token,
                'what': file_ident,  # Search by ID
                'limit': 10
            }

            response = self.session.post(
                f"{self.base_url}search/",
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                try:
                    xml = ET.fromstring(response.content)
                    if xml.find('status').text == 'OK':
                        for file_elem in xml.iter('file'):
                            file_data = {}
                            for child in file_elem:
                                file_data[child.tag] = child.text

                            # Check if this file has our ID
                            if file_data.get('ident') == file_ident:
                                print(f"  Found file via search: {file_data.get('name', 'Unknown')}")
                                return file_data
                except:
                    pass

            # Try the direct file_info endpoint
            self._rate_limit()
            data = {
                'wst': self.token,
                'ident': file_ident
            }

            response = self.session.post(
                f"{self.base_url}file_info/",
                data=data,
                timeout=30
            )

            if response.status_code == 200:
                # Parse the XML response
                try:
                    xml = ET.fromstring(response.content)
                    if xml.find('status').text == 'OK':
                        # Create file data from XML
                        file_data = {'ident': file_ident}
                        for elem in xml.iter():
                            if elem.tag not in ['response', 'status'] and elem.text:
                                file_data[elem.tag] = elem.text

                        if 'name' in file_data:
                            print(f"  Found file via file_info: {file_data['name']}")
                            return file_data
                        else:
                            # Look for name in response text
                            response_text = response.text
                            name_match = re.search(r'<name>([^<]+)</name>', response_text)
                            if name_match:
                                file_data['name'] = name_match.group(1)
                                print(f"  Found file via regex: {file_data['name']}")
                                return file_data
                except Exception as e:
                    print(f"  XML parse error: {str(e)}")
                    # Try regex parsing as fallback
                    response_text = response.text
                    name_match = re.search(r'<name>([^<]+)</name>', response_text)
                    if name_match:
                        file_data = {
                            'ident': file_ident,
                            'name': name_match.group(1)
                        }
                        print(f"  Found filename via regex fallback: {file_data['name']}")
                        return file_data

            return None

        except Exception as e:
            print(f"  ERROR in fallback: {str(e)}")
            return None

    def add_content_with_tmdb_and_webshare(self, tmdb_id, webshare_link, content_type=None, force_type=None):
        """Add content using specified TMDB ID and WebShare link - FIXED TO PREVENT DUPLICATES"""
        print(f"\nAdding content with TMDB ID {tmdb_id} and WebShare link...")

        if not self.login():
            print("✗ Login failed!")
            return None

        # Get TMDB content by ID
        print(f"  Fetching TMDB data for ID {tmdb_id}...")
        tmdb_content = self.get_tmdb_content_by_id(tmdb_id, content_type, force_type)

        if not tmdb_content:
            print(f"✗ Could not find TMDB content with ID {tmdb_id}")
            return None

        print(f"✓ Found on TMDB: {tmdb_content['title_en']} ({tmdb_content.get('year', '')})")

        # Get file information from the WebShare link
        print(f"  Getting file info from WebShare link...")
        file_info = self.get_file_info_from_link_fallback(webshare_link)

        if not file_info:
            print("✗ Could not get file information from WebShare link")
            print(f"  Link: {webshare_link}")
            return None

        filename = file_info.get('name', '')
        print(f"✓ File from WebShare: {filename}")

        # Process based on content type
        result = None
        content_type_final = content_type

        # If content type not specified, try to detect from TMDB
        if not content_type_final:
            content_type_final = self.detect_content_type_from_tmdb(tmdb_id, force_type)
            if content_type_final:
                print(f"  Detected content type from TMDB: {content_type_final}")
            else:
                # Guess from filename
                if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}|Season\s*\d+', filename):
                    content_type_final = 'tv'
                    print(f"  Guessed content type from filename: TV show")
                else:
                    content_type_final = 'movie'
                    print(f"  Guessed content type from filename: Movie")

        # Process the content
        if content_type_final == 'movie':
            result = self.process_movie_with_specific_file_fixed(tmdb_content, file_info)
        elif content_type_final == 'tv':
            result = self.process_tv_show_with_specific_file_fixed(tmdb_content, file_info)
        else:
            print(f"✗ Unknown content type: {content_type_final}")
            return None

        if result:
            # Save to manual content file
            manual_content = self.load_manual_content()
            if content_type_final == 'movie':
                # Check if already exists by tmdb_id
                existing_index = -1
                for i, m in enumerate(manual_content['movies']):
                    if m.get('tmdb_id') == tmdb_id:
                        existing_index = i
                        break

                if existing_index >= 0:
                    # Update existing
                    manual_content['movies'][existing_index] = result
                    print(f"  Updated existing movie in manual content")
                else:
                    # Add new
                    manual_content['movies'].append(result)
                    print(f"  Added new movie to manual content")
            elif content_type_final == 'tv':
                # Check if already exists by tmdb_id
                existing_index = -1
                for i, s in enumerate(manual_content['tv_shows']):
                    if s.get('tmdb_id') == tmdb_id:
                        existing_index = i
                        break

                if existing_index >= 0:
                    # Update existing
                    manual_content['tv_shows'][existing_index] = result
                    print(f"  Updated existing TV show in manual content")
                else:
                    # Add new
                    manual_content['tv_shows'].append(result)
                    print(f"  Added new TV show to manual content")

            self.save_manual_content(manual_content)

            # Update main database - THIS IS THE FIXED PART
            self.update_main_database_with_manual_content_fixed(result, content_type_final)

            print(f"\n✓ Successfully added/updated:")
            print(f"  Title: {result.get('title', 'Unknown')}")
            print(f"  TMDB ID: {tmdb_id}")
            print(f"  WebShare file: {filename}")
            if content_type_final == 'movie':
                print(f"  Total versions: {len(result.get('streams', []))}")
            else:
                episodes = sum(len(eps) for eps in result.get('seasons', {}).values())
                print(f"  Episodes: {episodes} episodes")

            return result

        return None

    def process_movie_with_specific_file_fixed(self, movie_data, specific_file):
        """Process a movie with a specific file from WebShare link - FIXED VERSION"""
        print(f"  Processing movie with specific file...")

        # Check if movie already exists
        existing_movie = None
        movie_index = -1
        if self.existing_data:
            for i, m in enumerate(self.existing_data.get('movies', [])):
                if m.get('tmdb_id') == movie_data.get('tmdb_id'):
                    existing_movie = m
                    movie_index = i
                    break

        # Start with existing files or empty list
        if existing_movie and self.incremental:
            files = existing_movie.get('streams', [])
            existing_file_ids = {f['ident'] for f in files}
            print(f"    Updating existing movie...")
        else:
            files = []
            existing_file_ids = set()
            print(f"    Creating new movie entry...")

        # Get file ID - handle missing 'ident' key
        specific_file_id = specific_file.get('ident')
        if not specific_file_id:
            # Try to extract from filename or generate one
            filename = specific_file.get('name', '')
            specific_file_id = hashlib.md5(filename.encode()).hexdigest()[:16]
            specific_file['ident'] = specific_file_id
            print(f"    Generated file ID: {specific_file_id}")

        # Add the specific file if not already present
        if specific_file_id not in existing_file_ids:
            file_entry = {
                'ident': specific_file_id,
                'name': specific_file.get('name', 'Unknown'),  # FIX: Use 'name' instead of 'filename'
                'size': specific_file.get('size', '0')
            }
            files.append(file_entry)
            print(f"    Added file from link: {specific_file.get('name', 'Unknown')}")

        # Also search for other versions
        print(f"    Searching for other versions...")
        other_files = self.find_movie_files(movie_data)

        for file in other_files:
            file_id = file.get('ident')
            if file_id and file_id not in existing_file_ids and file_id != specific_file_id:
                files.append({
                    'ident': file_id,
                    'name': file.get('name', 'Unknown'),  # FIX: Use 'name' instead of 'filename'
                    'size': file.get('size', '0')
                })

        # Create result object with detailed TMDB info
        display_title = movie_data.get('title_cz') or movie_data['title_en']

        # Use generate_content_id for consistent IDs
        content_id = self.generate_content_id(movie_data['title_en'], movie_data.get('year', ''))

        result = {
            'id': content_id,
            'tmdb_id': movie_data.get('tmdb_id', ''),
            'title': display_title,
            'title_en': movie_data['title_en'],
            'title_cz': movie_data.get('title_cz'),
            'year': movie_data.get('year', ''),
            'description': movie_data.get('description', ''),
            'description_cz': movie_data.get('description_cz', ''),
            'genres': movie_data.get('genres', []),
            'rating': movie_data.get('rating', 0),
            'vote_count': movie_data.get('vote_count', 0),
            'runtime': movie_data.get('runtime', 0),
            'poster': movie_data.get('poster', ''),
            'backdrop': movie_data.get('backdrop', ''),
            'cast': movie_data.get('cast', []),
            'crew': movie_data.get('crew', []),
            'streams': files
        }

        new_files = len(files) - (len(existing_movie.get('streams', [])) if existing_movie else 0)
        print(f"    Total: {len(files)} versions (+{new_files if new_files > 0 else 0} new)")

        # Mark as scanned
        if movie_data.get('tmdb_id'):
            self.mark_movie_scanned(movie_data['tmdb_id'])

        return result

    def update_main_database_with_manual_content_fixed(self, new_content, content_type):
        """Update the main database file with manually added content - FIXED TO PREVENT DUPLICATES"""
        # Load current database
        current_data = self.load_existing_data()

        updated = False

        if content_type == 'movie':
            # Check if movie already exists by tmdb_id
            existing_index = -1
            for i, movie in enumerate(current_data['movies']):
                if movie.get('tmdb_id') == new_content.get('tmdb_id'):
                    existing_index = i
                    break

            if existing_index >= 0:
                # Update existing movie
                current_data['movies'][existing_index] = new_content
                print(f"  Updated existing movie in database: {new_content.get('title_en')}")
                updated = True
            else:
                # Add new movie
                current_data['movies'].append(new_content)
                print(f"  Added new movie to database: {new_content.get('title_en')}")
                updated = True

        elif content_type == 'tv':
            # Check if TV show already exists by tmdb_id
            existing_index = -1
            for i, show in enumerate(current_data['tv_shows']):
                if show.get('tmdb_id') == new_content.get('tmdb_id'):
                    existing_index = i
                    break

            if existing_index >= 0:
                # Update existing TV show
                current_data['tv_shows'][existing_index] = new_content
                print(f"  Updated existing TV show in database: {new_content.get('title_en')}")
                updated = True
            else:
                # Add new TV show
                current_data['tv_shows'].append(new_content)
                print(f"  Added new TV show to database: {new_content.get('title_en')}")
                updated = True

        if updated:
            # Save immediately
            return self.save_data_immediately(current_data)

        return False

    def search_webshare_paginated(self, query, max_results=500):
        """Search WebShare with pagination to get more results"""
        if not self.token:
            logger.warning("No token available, skipping search")
            return []

        files = []
        seen_files = set()
        offset = 0
        max_offset = 1000  # Safety limit

        while len(files) < max_results and offset < max_offset:
            try:
                self._rate_limit()
                data = {
                    'wst': self.token,
                    'what': query,
                    'limit': 100,  # Max per request
                    'offset': offset,
                    'sort': 'recent'
                }

                response = self.session.post(
                    f"{self.base_url}search/",
                    data=data,
                    timeout=45
                )

                if response.status_code != 200:
                    break

                try:
                    xml = ET.fromstring(response.content)
                    if xml.find('status').text != 'OK':
                        break

                    found_in_batch = 0
                    for file in xml.iter('file'):
                        file_data = {}
                        for child in file:
                            file_data[child.tag] = child.text

                        ident = file_data.get('ident')
                        if ident in seen_files:
                            continue

                        # Only video files
                        name = file_data.get('name', '').lower()
                        if any(ext in name for ext in ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v']):
                            files.append(file_data)
                            seen_files.add(ident)
                            found_in_batch += 1

                            if len(files) >= max_results:
                                return files

                    # If we got fewer than 10 results in this batch, probably no more
                    if found_in_batch < 10:
                        break

                    offset += 100
                    time.sleep(0.5)

                except ET.ParseError:
                    break

            except Exception as e:
                logger.warning(f"Error in paginated search for '{query}': {str(e)}")
                break

        return files

    def clean_title_for_matching(self, title):
        """Clean title for matching in filenames - more aggressive cleaning"""
        if not title:
            return ""

        # Remove special characters, keep only alphanumeric and spaces
        cleaned = re.sub(r'[^\w\s\-]', ' ', title.lower())
        # Replace multiple spaces with single space
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Remove common articles and conjunctions
        words_to_remove = ['the', 'a', 'an', 'and', '&', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = cleaned.split()
        filtered_words = [w for w in words if w not in words_to_remove and len(w) > 2]

        return ' '.join(filtered_words)

    def filename_contains_title(self, filename, title, year=None, strict=False):
        """Check if filename contains the title with spaces, dots, dashes, or underscores"""
        if not title or not filename:
            return False

        # Clean filename
        clean_filename = filename.lower()

        # Convert title to lowercase
        title_lower = title.lower()

        # Create match patterns with different separators
        # Replace spaces with different possible separators
        base_patterns = [
            title_lower,  # "the unholy trinity"
            title_lower.replace(' ', '.'),  # "the.unholy.trinity"
            title_lower.replace(' ', '-'),  # "the-unholy-trinity"
            title_lower.replace(' ', '_'),  # "the_unholy_trinity"
        ]

        # For strict matching only: check word boundaries
        if strict:
            for pattern in base_patterns:
                # Check if pattern is in filename with proper separators
                pattern_with_separators = [
                    f" {pattern} ",      # space before and after
                    f".{pattern}.",      # dot before and after
                    f"-{pattern}-",      # dash before and after
                    f"_{pattern}_",      # underscore before and after
                    f" {pattern}.",      # space before, dot after
                    f".{pattern} ",      # dot before, space after
                    f" {pattern}-",      # space before, dash after
                    f"-{pattern} ",      # dash before, space after
                    f" {pattern}_",      # space before, underscore after
                    f"_{pattern} ",      # underscore before, space after
                    f"^{pattern}",       # at start of string
                    f"{pattern}$",       # at end of string
                    f"^{pattern}.",      # at start, dot after
                    f"^{pattern}-",      # at start, dash after
                    f"^{pattern}_",      # at start, underscore after
                    f".{pattern}$",      # dot before, at end
                    f"-{pattern}$",      # dash before, at end
                    f"_{pattern}$",      # underscore before, at end
                ]

                for sep_pattern in pattern_with_separators:
                    if re.search(sep_pattern, clean_filename):
                        # Found exact match with proper separators
                        if year and str(year):
                            if str(year) in clean_filename:
                                return True
                        else:
                            return True
        else:
            # Less strict: just check if any pattern is in the filename
            for pattern in base_patterns:
                if pattern in clean_filename:
                    # For less strict matching, also check it's not part of a much longer phrase
                    # Count how many words from the pattern appear
                    pattern_words = pattern.replace('.', ' ').replace('-', ' ').replace('_', ' ').split()
                    filename_words = re.split(r'[\.\-\_\s]+', clean_filename)

                    # Count matches
                    matches = sum(1 for word in pattern_words if word in filename_words)

                    # Require at least 70% of words to match
                    if matches / len(pattern_words) >= 0.7:
                        if year and str(year):
                            if str(year) in clean_filename:
                                return True
                        else:
                            return True

        # Also try without "The" prefix
        if title_lower.startswith('the '):
            title_without_the = title_lower[4:]  # Remove "the "
            patterns_without_the = [
                title_without_the,
                title_without_the.replace(' ', '.'),
                title_without_the.replace(' ', '-'),
                title_without_the.replace(' ', '_')
            ]

            for pattern in patterns_without_the:
                if pattern in clean_filename:
                    # For less strict matching
                    if not strict:
                        pattern_words = pattern.replace('.', ' ').replace('-', ' ').replace('_', ' ').split()
                        filename_words = re.split(r'[\.\-\_\s]+', clean_filename)

                        matches = sum(1 for word in pattern_words if word in filename_words)

                        if matches / len(pattern_words) >= 0.7:
                            if year and str(year):
                                if str(year) in clean_filename:
                                    return True
                            else:
                                return True

        return False

    def search_webshare_comprehensive(self, query, content_type=None, year=None, max_results=300, strict_matching=False):
        """Comprehensive search for all available streams with pagination"""
        if not self.token:
            logger.warning("No token available, skipping search")
            return []

        files = []
        seen_files = set()

        # Clean query for title matching
        clean_query = self.clean_title_for_matching(query)

        # Generate multiple search queries for better coverage
        search_variations = self.generate_search_variations(query, content_type, year)

        for search_query in search_variations:
            try:
                # Use paginated search for each variation
                batch_max = 100 if content_type == 'movie' else 200  # More for TV shows
                batch_files = self.search_webshare_paginated(search_query, max_results=batch_max)

                for file in batch_files:
                    ident = file['ident']

                    if ident in seen_files:
                        continue

                    filename = file.get('name', '').lower()

                    # FILTERING: Check if filename contains enough of the actual title
                    # Use strict matching for movies, less strict for new/rare content
                    title_match = self.filename_contains_title(filename, query, year, strict=strict_matching)

                    # For movies: must NOT contain TV episode patterns
                    if content_type == 'movie' and title_match:
                        # Skip TV episodes for movies
                        if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}|\d{1,2}[Xx]\d{1,2}|season\s*\d|episode\s*\d|ep\.\d', filename):
                            # But allow if it's still clearly our movie (has year and title)
                            if year and str(year) in filename and title_match:
                                pass  # Keep it
                            else:
                                continue

                    # For TV shows: should contain episode markers but not required for all results
                    elif content_type == 'tv':
                        # If it doesn't have episode marker, make sure title match is strong
                        if not re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}|\d{1,2}[Xx]\d{1-2}|season\s*\d|episode\s*\d|ep\.\d|s[0-9]{1,2}e[0-9]{1,2}', filename):
                            # For TV shows without episode markers, require strong title match AND year
                            if not (title_match and year and str(year) in filename):
                                continue

                    # Only add if title matches
                    if title_match:
                        files.append(file)
                        seen_files.add(ident)

                    if len(files) >= max_results:
                        return files

                time.sleep(0.3)

            except Exception as e:
                continue

        return files

    def generate_search_variations(self, query, content_type=None, year=None):
        """Generate multiple search queries for better coverage"""
        variations = []

        # Clean the query
        clean_query = re.sub(r'[^\w\s\-]', ' ', query).strip()
        clean_query = re.sub(r'\s+', ' ', clean_query)

        if not clean_query or len(clean_query) < 2:
            return []

        # Basic variations
        variations.append(clean_query)
        variations.append(clean_query.lower())

        # With year if available
        if year:
            variations.append(f"{clean_query} {year}")
            variations.append(f'{clean_query} ({year})')

        # For movies, try without "The" prefix
        if content_type == 'movie' and clean_query.lower().startswith('the '):
            variations.append(clean_query[4:])  # Remove "The "
            variations.append(clean_query[4:].lower())

        # For TV shows, add season-specific variations
        if content_type == 'tv':
            # Add variations without year first (for general search)
            variations.append(f"{clean_query} season")
            variations.append(f"{clean_query} s01")
            variations.append(f"{clean_query} s1")

            # Add with year if available
            if year:
                variations.append(f"{clean_query} {year} season")
                variations.append(f"{clean_query} {year} s01")

        # Common alternative names
        if '&' in clean_query:
            variations.append(clean_query.replace('&', 'and'))
        if 'and' in clean_query.lower():
            variations.append(clean_query.replace('and', '&'))

        # Add Czech variations if content might have Czech versions
        variations.append(f"{clean_query} cz")
        variations.append(f"{clean_query} czech")
        variations.append(f"{clean_query} dabing")

        # Remove duplicates and limit
        seen = set()
        unique_variations = []
        for v in variations:
            if v and v not in seen and len(v) >= 3:
                seen.add(v)
                unique_variations.append(v)

        return unique_variations[:20]  # Increased limit for better coverage

    def detect_content_type_from_tmdb(self, tmdb_id, force_type=None):
        """Detect content type from TMDB by trying both movie and TV"""
        # If force_type is specified, use it
        if force_type in ['movie', 'tv']:
            return force_type

        # Try movie first
        try:
            endpoint = f"{TMDB_URL}/movie/{tmdb_id}"
            params = {'api_key': TMDB_API_KEY}
            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                return 'movie'
        except:
            pass

        # Try TV if movie failed
        try:
            endpoint = f"{TMDB_URL}/tv/{tmdb_id}"
            params = {'api_key': TMDB_API_KEY}
            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                return 'tv'
        except:
            pass

        return None

    def get_tmdb_tv_show_details(self, tmdb_id):
        """Get detailed TV show information including number of seasons and episodes"""
        try:
            endpoint = f"{TMDB_URL}/tv/{tmdb_id}"
            params = {
                'api_key': TMDB_API_KEY,
                'language': 'en-US',
                'append_to_response': 'credits,images,content_ratings'
            }

            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()

                title_en = data.get('name', '')
                original_title = data.get('original_name', '')
                year = data.get('first_air_date', '')[:4]
                seasons = data.get('number_of_seasons', 0)
                episodes = data.get('number_of_episodes', 0)

                # Use generate_content_id for consistent IDs
                content_id = self.generate_content_id(title_en, year)

                # Get Czech translation
                czech_title = self.get_czech_translation(tmdb_id, 'tv')

                # Get detailed Czech info
                czech_info = self.get_czech_details(tmdb_id, 'tv')

                # Get genres
                genres = [{'id': g['id'], 'name': g['name']} for g in data.get('genres', [])]

                # Get rating
                rating = data.get('vote_average', 0)
                vote_count = data.get('vote_count', 0)

                # Get images
                images = data.get('images', {})
                poster_path = data.get('poster_path', '')
                backdrop_path = data.get('backdrop_path', '')

                # Get cast (limit to top 10)
                cast = []
                credits = data.get('credits', {})
                if credits:
                    cast_members = credits.get('cast', [])[:10]
                    for person in cast_members:
                        cast.append({
                            'id': person.get('id'),
                            'name': person.get('name'),
                            'character': person.get('character'),
                            'profile_path': person.get('profile_path'),
                            'order': person.get('order')
                        })

                # Get crew
                crew = []
                if credits:
                    crew_members = credits.get('crew', [])[:10]
                    for person in crew_members:
                        crew.append({
                            'id': person.get('id'),
                            'name': person.get('name'),
                            'job': person.get('job'),
                            'department': person.get('department')
                        })

                # Get seasons with basic info
                tmdb_seasons = data.get('seasons', [])
                seasons_info = []
                for season in tmdb_seasons:
                    seasons_info.append({
                        'season_number': season.get('season_number', 0),
                        'name': season.get('name', ''),
                        'overview': season.get('overview', ''),
                        'episode_count': season.get('episode_count', 0),
                        'poster_path': season.get('poster_path', ''),
                        'air_date': season.get('air_date', '')
                    })

                result = {
                    'id': content_id,
                    'tmdb_id': tmdb_id,
                    'title_en': title_en,
                    'title_cz': czech_title,
                    'year': year,
                    'original_title': original_title,
                    'total_seasons': seasons,
                    'total_episodes': episodes,
                    'description': data.get('overview', ''),
                    'description_cz': czech_info.get('overview', '') if czech_info else '',
                    'genres': genres,
                    'rating': rating,
                    'vote_count': vote_count,
                    'poster': f"{TMDB_IMAGE_BASE_URL}original{poster_path}" if poster_path else '',
                    'backdrop': f"{TMDB_IMAGE_BASE_URL}original{backdrop_path}" if backdrop_path else '',
                    'cast': cast,
                    'crew': crew,
                    'seasons_info': seasons_info,
                    'networks': [{'id': n['id'], 'name': n['name']} for n in data.get('networks', [])],
                    'status': data.get('status', ''),
                    'type': data.get('type', '')
                }

                return result
        except Exception as e:
            logger.error(f"Error fetching TMDB TV show details {tmdb_id}: {str(e)}")

        return None

    def get_czech_details(self, item_id, content_type):
        """Get Czech language details from TMDB"""
        try:
            endpoint = f"{TMDB_URL}/movie/{item_id}/translations" if content_type == 'movie' else f"{TMDB_URL}/tv/{item_id}/translations"
            params = {'api_key': TMDB_API_KEY}
            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                translations = data.get('translations', [])

                for translation in translations:
                    if translation.get('iso_639_1') == 'cs':
                        data = translation.get('data', {})
                        return {
                            'title': data.get('title') if content_type == 'movie' else data.get('name'),
                            'overview': data.get('overview', '')
                        }
        except Exception as e:
            logger.error(f"Error fetching Czech details for {content_type} {item_id}: {str(e)}")

        return None

    def get_tmdb_content_by_id(self, tmdb_id, content_type=None, force_type=None):
        """Get content from TMDB by ID with content type detection - ENHANCED WITH DETAILS"""
        try:
            # If content_type is not specified or wrong, detect it
            if not content_type or content_type not in ['movie', 'tv']:
                detected_type = self.detect_content_type_from_tmdb(tmdb_id, force_type)
                if detected_type:
                    content_type = detected_type
                else:
                    logger.error(f"Could not determine content type for TMDB ID {tmdb_id}")
                    return None

            if content_type == 'tv':
                # Use detailed TV show info
                return self.get_tmdb_tv_show_details(tmdb_id)

            # For movies, use the enhanced endpoint
            endpoint = f"{TMDB_URL}/movie/{tmdb_id}"
            params = {
                'api_key': TMDB_API_KEY,
                'language': 'en-US',
                'append_to_response': 'credits,images,translations'
            }

            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()

                title_en = data.get('title', '')
                original_title = data.get('original_title', '')
                year = data.get('release_date', '')[:4]

                # Use generate_content_id for consistent IDs
                content_id = self.generate_content_id(title_en, year)

                # Get Czech translation
                czech_title = self.get_czech_translation(tmdb_id, content_type)

                # Get Czech details
                czech_info = self.get_czech_details(tmdb_id, content_type)

                # Get genres
                genres = [{'id': g['id'], 'name': g['name']} for g in data.get('genres', [])]

                # Get rating
                rating = data.get('vote_average', 0)
                vote_count = data.get('vote_count', 0)

                # Get runtime
                runtime = data.get('runtime', 0)

                # Get images
                poster_path = data.get('poster_path', '')
                backdrop_path = data.get('backdrop_path', '')

                # Get cast (limit to top 10)
                cast = []
                credits = data.get('credits', {})
                if credits:
                    cast_members = credits.get('cast', [])[:10]
                    for person in cast_members:
                        cast.append({
                            'id': person.get('id'),
                            'name': person.get('name'),
                            'character': person.get('character'),
                            'profile_path': person.get('profile_path'),
                            'order': person.get('order')
                        })

                # Get crew (director, writers)
                crew = []
                if credits:
                    crew_members = credits.get('crew', [])
                    # Get director(s)
                    directors = [p for p in crew_members if p.get('job') == 'Director']
                    for director in directors[:3]:  # Limit to 3 directors
                        crew.append({
                            'id': director.get('id'),
                            'name': director.get('name'),
                            'job': 'Director'
                        })

                    # Get writers
                    writers = [p for p in crew_members if p.get('department') == 'Writing']
                    for writer in writers[:5]:  # Limit to 5 writers
                        crew.append({
                            'id': writer.get('id'),
                            'name': writer.get('name'),
                            'job': writer.get('job', 'Writer')
                        })

                result = {
                    'id': content_id,
                    'tmdb_id': tmdb_id,
                    'title_en': title_en,
                    'title_cz': czech_title,
                    'year': year,
                    'original_title': original_title,
                    'description': data.get('overview', ''),
                    'description_cz': czech_info.get('overview', '') if czech_info else '',
                    'genres': genres,
                    'rating': rating,
                    'vote_count': vote_count,
                    'runtime': runtime,
                    'poster': f"{TMDB_IMAGE_BASE_URL}original{poster_path}" if poster_path else '',
                    'backdrop': f"{TMDB_IMAGE_BASE_URL}original{backdrop_path}" if backdrop_path else '',
                    'cast': cast,
                    'crew': crew,
                    'release_date': data.get('release_date', ''),
                    'production_companies': [{'id': c['id'], 'name': c['name']} for c in data.get('production_companies', [])],
                    'production_countries': [{'iso_3166_1': c['iso_3166_1'], 'name': c['name']} for c in data.get('production_countries', [])],
                    'spoken_languages': [{'iso_639_1': l['iso_639_1'], 'name': l['name']} for l in data.get('spoken_languages', [])]
                }

                return result
        except Exception as e:
            logger.error(f"Error fetching TMDB content {tmdb_id}: {str(e)}")

        return None

    def get_tmdb_content_by_search(self, query, content_type=None, force_type=None):
        """Search for content on TMDB by name"""
        try:
            # If content_type is not specified, search both
            if not content_type or content_type not in ['movie', 'tv']:
                # Try movie first
                movie_result = self._search_tmdb_single_type(query, 'movie')
                if movie_result:
                    return movie_result

                # Try TV if movie not found
                tv_result = self._search_tmdb_single_type(query, 'tv')
                if tv_result:
                    return tv_result

                return None
            else:
                # Search specific type
                return self._search_tmdb_single_type(query, content_type)
        except Exception as e:
            logger.error(f"Error searching TMDB for {query}: {str(e)}")
            return None

    def _search_tmdb_single_type(self, query, content_type):
        """Search TMDB for a specific content type"""
        try:
            endpoint = f"{TMDB_URL}/search/{content_type}"
            params = {
                'api_key': TMDB_API_KEY,
                'language': 'en-US',
                'query': query,
                'page': 1
            }

            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])

                if results:
                    item = results[0]

                    # Get full details for the first result
                    full_details = self.get_tmdb_content_by_id(item['id'], content_type)
                    if full_details:
                        return full_details

                    # Fallback to basic info
                    if content_type == 'movie':
                        title_en = item.get('title', '')
                        original_title = item.get('original_title', '')
                        year = item.get('release_date', '')[:4]
                    else:
                        title_en = item.get('name', '')
                        original_title = item.get('original_name', '')
                        year = item.get('first_air_date', '')[:4]

                    czech_title = self.get_czech_translation(item['id'], content_type)
                    content_id = self.generate_content_id(title_en, year)

                    result = {
                        'id': content_id,
                        'tmdb_id': item['id'],
                        'title_en': title_en,
                        'title_cz': czech_title,
                        'year': year,
                        'original_title': original_title,
                        'description': item.get('overview', ''),
                        'rating': item.get('vote_average', 0),
                        'vote_count': item.get('vote_count', 0),
                        'poster': f"{TMDB_IMAGE_BASE_URL}original{item.get('poster_path', '')}" if item.get('poster_path') else '',
                        'backdrop': f"{TMDB_IMAGE_BASE_URL}original{item.get('backdrop_path', '')}" if item.get('backdrop_path') else ''
                    }

                    return result
        except Exception as e:
            logger.error(f"Error searching TMDB for {query} ({content_type}): {str(e)}")

        return None

    def get_czech_translation(self, item_id, content_type):
        """Get Czech translation for TMDB item with caching"""
        cache_key = f"{content_type}_{item_id}_cz"

        if cache_key in self.tmdb_cache:
            return self.tmdb_cache[cache_key]

        try:
            endpoint = f"{TMDB_URL}/movie/{item_id}/translations" if content_type == 'movie' else f"{TMDB_URL}/tv/{item_id}/translations"
            params = {'api_key': TMDB_API_KEY}
            response = requests.get(endpoint, params=params, timeout=15)

            if response.status_code == 200:
                data = response.json()
                translations = data.get('translations', [])

                for translation in translations:
                    if translation.get('iso_639_1') == 'cs':
                        data = translation.get('data', {})
                        if content_type == 'movie':
                            cz_title = data.get('title')
                        else:
                            cz_title = data.get('name')

                        if cz_title:
                            self.tmdb_cache[cache_key] = cz_title
                            return cz_title
        except Exception as e:
            logger.error(f"Error getting Czech translation for {content_type} {item_id}: {str(e)}")

        return None

    def get_tv_show_season_details(self, tmdb_id, season_number):
        """Get detailed season information including episodes"""
        try:
            endpoint = f"{TMDB_URL}/tv/{tmdb_id}/season/{season_number}"
            params = {
                'api_key': TMDB_API_KEY,
                'language': 'en-US',
                'append_to_response': 'credits,images'
            }

            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()

                # Get Czech translation for season
                czech_info = self.get_season_czech_details(tmdb_id, season_number)

                # Process episodes
                episodes = []
                for ep in data.get('episodes', []):
                    # Get Czech episode info
                    ep_cz_info = self.get_episode_czech_details(tmdb_id, season_number, ep.get('episode_number'))

                    episode_info = {
                        'episode_number': ep.get('episode_number', 0),
                        'name': ep.get('name', ''),
                        'name_cz': ep_cz_info.get('name', '') if ep_cz_info else '',
                        'overview': ep.get('overview', ''),
                        'overview_cz': ep_cz_info.get('overview', '') if ep_cz_info else '',
                        'air_date': ep.get('air_date', ''),
                        'vote_average': ep.get('vote_average', 0),
                        'vote_count': ep.get('vote_count', 0),
                        'runtime': ep.get('runtime', 0),
                        'still_path': f"{TMDB_IMAGE_BASE_URL}original{ep.get('still_path', '')}" if ep.get('still_path') else '',
                        'crew': [{'id': p['id'], 'name': p['name'], 'job': p['job']} for p in ep.get('crew', [])],
                        'guest_stars': [{'id': p['id'], 'name': p['name'], 'character': p['character']} for p in ep.get('guest_stars', [])[:5]]
                    }
                    episodes.append(episode_info)

                season_info = {
                    'season_number': data.get('season_number', 0),
                    'name': data.get('name', ''),
                    'name_cz': czech_info.get('name', '') if czech_info else '',
                    'overview': data.get('overview', ''),
                    'overview_cz': czech_info.get('overview', '') if czech_info else '',
                    'air_date': data.get('air_date', ''),
                    'poster_path': f"{TMDB_IMAGE_BASE_URL}original{data.get('poster_path', '')}" if data.get('poster_path') else '',
                    'episode_count': data.get('episode_count', 0),
                    'episodes': episodes
                }

                return season_info
        except Exception as e:
            logger.error(f"Error fetching season details for TV {tmdb_id} S{season_number}: {str(e)}")

        return None

    def get_season_czech_details(self, tmdb_id, season_number):
        """Get Czech details for a specific season"""
        try:
            endpoint = f"{TMDB_URL}/tv/{tmdb_id}/season/{season_number}/translations"
            params = {'api_key': TMDB_API_KEY}
            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                translations = data.get('translations', [])

                for translation in translations:
                    if translation.get('iso_639_1') == 'cs':
                        return translation.get('data', {})
        except Exception as e:
            logger.error(f"Error getting Czech season details for {tmdb_id} S{season_number}: {str(e)}")

        return None

    def get_episode_czech_details(self, tmdb_id, season_number, episode_number):
        """Get Czech details for a specific episode"""
        try:
            endpoint = f"{TMDB_URL}/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}/translations"
            params = {'api_key': TMDB_API_KEY}
            response = requests.get(endpoint, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                translations = data.get('translations', [])

                for translation in translations:
                    if translation.get('iso_639_1') == 'cs':
                        return translation.get('data', {})
        except Exception as e:
            logger.error(f"Error getting Czech episode details for {tmdb_id} S{season_number}E{episode_number}: {str(e)}")

        return None

    def get_tmdb_with_translations(self, content_type, count=50, year=None):
        """Get content from TMDB with Czech translations, optionally filtered by year - ENHANCED"""
        print(f"Getting {count} popular {content_type} from TMDB" + (f" for year {year}" if year else "") + "...")

        results = []
        page = 1
        max_pages = 5

        while len(results) < count and page <= max_pages:
            try:
                params_en = {
                    'api_key': TMDB_API_KEY,
                    'language': 'en-US',
                    'page': page,
                    'sort_by': 'popularity.desc'
                }

                if year:
                    if content_type == 'movie':
                        params_en['primary_release_year'] = year
                        endpoint = f"{TMDB_URL}/discover/movie"
                    else:
                        params_en['first_air_date_year'] = year
                        endpoint = f"{TMDB_URL}/discover/tv"
                else:
                    endpoint = f"{TMDB_URL}/movie/popular" if content_type == 'movie' else f"{TMDB_URL}/tv/popular"

                response = requests.get(endpoint, params=params_en, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get('results', []):
                        try:
                            item_id = item['id']

                            # Generate content ID
                            title = item.get('title') if content_type == 'movie' else item.get('name')
                            item_year = item.get('release_date', '')[:4] if content_type == 'movie' else item.get('first_air_date', '')[:4]

                            # Skip if year doesn't match (when filtering by year)
                            if year and item_year != str(year):
                                continue

                            # Use generate_content_id for consistent IDs
                            content_id = self.generate_content_id(title, item_year)

                            # Skip if already scanned recently
                            if content_type == 'movie' and self.is_movie_scanned(item_id):
                                continue
                            elif content_type == 'tv' and self.is_tv_show_scanned(item_id):
                                continue

                            # Check if already exists in database
                            if self.existing_data:
                                existing_items = self.existing_data.get('movies', []) if content_type == 'movie' else self.existing_data.get('tv_shows', [])
                                for existing in existing_items:
                                    if existing.get('tmdb_id') == item_id:
                                        continue

                            # Get full details for each item
                            full_details = self.get_tmdb_content_by_id(item_id, content_type)

                            if full_details:
                                # Ensure ID is correct
                                full_details['id'] = content_id
                                results.append(full_details)
                            else:
                                # Fallback to basic info
                                czech_title = self.get_czech_translation(item_id, content_type)

                                basic_info = {
                                    'id': content_id,
                                    'tmdb_id': item_id,
                                    'title_en': title,
                                    'title_cz': czech_title,
                                    'year': item_year,
                                    'original_title': item.get('original_title', '') if content_type == 'movie' else item.get('original_name', ''),
                                    'description': item.get('overview', ''),
                                    'rating': item.get('vote_average', 0),
                                    'vote_count': item.get('vote_count', 0),
                                    'poster': f"{TMDB_IMAGE_BASE_URL}original{item.get('poster_path', '')}" if item.get('poster_path') else '',
                                    'backdrop': f"{TMDB_IMAGE_BASE_URL}original{item.get('backdrop_path', '')}" if item.get('backdrop_path') else ''
                                }
                                results.append(basic_info)

                            if len(results) >= count:
                                break

                        except KeyError:
                            continue
                else:
                    logger.warning(f"TMDB request failed with status {response.status_code}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"TMDB request error: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected TMDB error: {str(e)}")

            page += 1
            time.sleep(0.5)

        print(f"✓ Got {len(results)} {content_type} from TMDB")
        return results

    def find_movie_files(self, movie):
        """Search for movie files with improved search"""
        title_en = movie['title_en']
        title_cz = movie.get('title_cz')
        year = movie.get('year', '')

        print(f"  Searching for movie: {title_en}" + (f" / {title_cz}" if title_cz else ""))

        # Try strict matching first
        files = self.search_webshare_comprehensive(
            title_en,
            'movie',
            year,
            max_results=50,
            strict_matching=True  # Strict matching first
        )

        # If no results with strict matching, try less strict
        if len(files) == 0:
            print(f"    No results with strict matching, trying less strict...")
            files = self.search_webshare_comprehensive(
                title_en,
                'movie',
                year,
                max_results=50,
                strict_matching=False  # Less strict matching
            )

        # Also search with Czech title if available and different
        if title_cz and title_cz != title_en:
            cz_files = self.search_webshare_comprehensive(
                title_cz,
                'movie',
                year,
                max_results=30,
                strict_matching=False  # Less strict for Czech titles
            )

            # Merge files, avoiding duplicates
            for file in cz_files:
                ident = file['ident']
                if not any(f['ident'] == ident for f in files):
                    files.append(file)

        # STRICT FILTERING: Remove bullshit files
        filtered_files = []
        for file in files:
            filename = file.get('name', '').lower()

            # Check if filename contains the title
            title_match = self.filename_contains_title(filename, title_en, year, strict=False)
            if not title_match and title_cz:
                title_match = self.filename_contains_title(filename, title_cz, year, strict=False)

            if not title_match:
                continue

            # Check if it contains the year (if year is available)
            # For single-word Czech titles, year is MANDATORY
            if self.is_single_word_title(title_cz or title_en):
                if year and str(year) not in filename:
                    continue

            # Must NOT be TV episodes
            if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}|\d{1,2}[Xx]\d{1,2}|season\s*\d|episode\s*\d|ep\.\d', filename):
                # Allow if it's still clearly our movie (has year and title)
                if not (year and str(year) in filename and title_match):
                    continue

            # NEW: Extra check for conflicting years
            if year and str(year):
                # Extract all years from filename
                year_pattern = r'\b(19[0-9]{2}|20[0-9]{2})\b'
                all_years = re.findall(year_pattern, filename)
                content_year = str(year)

                # If there are years in filename, they must all match our content year
                if all_years:
                    if any(y != content_year for y in all_years):
                        # Different year found - skip this file
                        continue

            # Filter out common bullshit patterns
            bullshit_patterns = [
                r'rolling stones',  # Music band
                r'bang tango',      # Music band
                r'chris isaak',     # Singer
                r'billy joel',      # Singer
                r'jennifer rush',   # Singer
                r'unus annus',      # YouTube series
                r'youtube',         # YouTube
                r'ep\.\s*\d{1,3}',  # Episode numbering
                r'\d{1,3}\s*-\s*',  # Episode numbering
                r'#\d{1,3}',        # Episode numbering
                r'c\.c\.',          # C.C.Catch (singer)
            ]

            is_bullshit = False
            for pattern in bullshit_patterns:
                if re.search(pattern, filename, re.IGNORECASE):
                    is_bullshit = True
                    break

            if is_bullshit:
                continue

            filtered_files.append(file)

        print(f"    Found {len(filtered_files)} valid movie versions")
        return filtered_files

    def is_single_word_title(self, title):
        """Check if title is essentially a single word after cleaning"""
        if not title:
            return False

        # Clean the title
        cleaned = re.sub(r'[^\w\s\-]', ' ', title.lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        # Remove common articles
        words_to_remove = ['the', 'a', 'an', 'and', '&', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by']
        words = [w for w in cleaned.split() if w not in words_to_remove and len(w) > 1]

        return len(words) == 1

    def add_content_manually(self, input_method, identifier, content_type=None, force_type=None):
        """Add content manually via TMDB link, name, or WebShare link with auto-detection - FIXED TO FIND ALL EPISODES"""
        print(f"\nAdding content manually...")

        # Handle combined format: "tmdb:ID,webshare:URL"
        if ',' in identifier:
            parts = identifier.split(',')
            tmdb_part = None
            webshare_part = None

            for part in parts:
                if part.strip().startswith('tmdb:'):
                    tmdb_part = part.strip()[5:]  # Remove "tmdb:"
                elif part.strip().startswith('webshare:'):
                    webshare_part = part.strip()[9:]  # Remove "webshare:"

            if tmdb_part and webshare_part:
                # Use the new method that accepts both
                return self.add_content_with_tmdb_and_webshare(tmdb_part, webshare_part, content_type, force_type)

        # Original logic for single inputs
        content = None
        final_content_type = content_type

        if input_method == 'tmdb':
            # Extract TMDB ID from URL
            tmdb_match = re.search(r'tmdb\.org/(movie|tv)/(\d+)', identifier)
            if tmdb_match:
                detected_type = tmdb_match.group(1)
                tmdb_id = tmdb_match.group(2)
                print(f"Detected content type from URL: {detected_type}")
                final_content_type = detected_type
                content = self.get_tmdb_content_by_id(tmdb_id, final_content_type, force_type)
            else:
                # Try to parse as direct ID
                try:
                    tmdb_id = int(identifier)
                    print(f"Looking up TMDB ID: {tmdb_id}")
                    content = self.get_tmdb_content_by_id(tmdb_id, final_content_type, force_type)
                except ValueError:
                    print(f"Invalid TMDB identifier: {identifier}")
                    return None
        elif input_method == 'name':
            # Search TMDB by name
            print(f"Searching TMDB for: {identifier}")
            content = self.get_tmdb_content_by_search(identifier, final_content_type, force_type)
        elif input_method == 'webshare':
            # Process WebShare link (will try to extract title and search TMDB)
            print(f"Processing WebShare link: {identifier}")
            # This would need a separate method to extract title from filename and search TMDB
            print("Feature not implemented yet - use 'tmdb:ID,webshare:URL' format instead")
            return None

        if not content:
            print(f"Could not find content with identifier: {identifier}")
            return None

        print(f"Found: {content['title_en']} ({content.get('year', '')})")

        # Determine final content type if not already known
        if not final_content_type:
            # Try to determine from TMDB ID lookup
            if 'tmdb_id' in content:
                detected_type = self.detect_content_type_from_tmdb(content['tmdb_id'], force_type)
                if detected_type:
                    final_content_type = detected_type
                    print(f"Auto-detected content type: {final_content_type}")

        # Process the content
        if final_content_type == 'movie':
            result = self.process_movie(content, 0, 1)
        elif final_content_type == 'tv':
            # Use the comprehensive TV show processing
            result = self.process_tv_show(content, 0, 1)
        else:
            print(f"Unknown content type: {final_content_type}")
            return None

        if result:
            # Save to manual content file
            manual_content = self.load_manual_content()
            if final_content_type == 'movie':
                # Check if already exists by tmdb_id
                existing_index = -1
                for i, m in enumerate(manual_content['movies']):
                    if m.get('tmdb_id') == result.get('tmdb_id'):
                        existing_index = i
                        break

                if existing_index >= 0:
                    # Update existing
                    manual_content['movies'][existing_index] = result
                    print(f"  Updated existing movie in manual content")
                else:
                    # Add new
                    manual_content['movies'].append(result)
                    print(f"  Added new movie to manual content")
            elif final_content_type == 'tv':
                # Check if already exists by tmdb_id
                existing_index = -1
                for i, s in enumerate(manual_content['tv_shows']):
                    if s.get('tmdb_id') == result.get('tmdb_id'):
                        existing_index = i
                        break

                if existing_index >= 0:
                    # Update existing
                    manual_content['tv_shows'][existing_index] = result
                    print(f"  Updated existing TV show in manual content")
                else:
                    # Add new
                    manual_content['tv_shows'].append(result)
                    print(f"  Added new TV show to manual content")

            self.save_manual_content(manual_content)

            # Also update the main database immediately
            self.update_main_database_with_manual_content_fixed(result, final_content_type)

        return result

    def process_movie(self, movie, index, total):
        """Process a single movie with comprehensive search - ENHANCED WITH DETAILS"""
        try:
            print(f"[{index+1}/{total}] ", end='', flush=True)

            # Check if movie already exists for incremental update
            existing_movie = None
            movie_id = movie.get('tmdb_id')

            if self.existing_data:
                for m in self.existing_data.get('movies', []):
                    if m.get('tmdb_id') == movie_id:
                        existing_movie = m
                        break

            # If movie exists and we're in incremental mode, use existing files as base
            if existing_movie and self.incremental:
                existing_files = existing_movie.get('streams', [])
                existing_file_ids = {f['ident'] for f in existing_files}
                print(f"Updating existing movie...")
            else:
                existing_files = []
                existing_file_ids = set()

            # Search for all available files
            files = self.find_movie_files(movie)

            # Combine with existing files
            combined_files = existing_files.copy()
            for file in files:
                if file['ident'] not in existing_file_ids:
                    combined_files.append({
                        'ident': file['ident'],
                        'name': file['name'],  # Use 'name' instead of 'filename'
                        'size': file.get('size', '0')
                    })

            if combined_files:
                display_title = movie.get('title_cz') or movie['title_en']

                # Use generate_content_id for consistent IDs
                content_id = self.generate_content_id(movie['title_en'], movie.get('year', ''))

                result = {
                    'id': content_id,
                    'tmdb_id': movie.get('tmdb_id', ''),
                    'title': display_title,
                    'title_en': movie['title_en'],
                    'title_cz': movie.get('title_cz'),
                    'year': movie.get('year', ''),
                    'description': movie.get('description', ''),
                    'description_cz': movie.get('description_cz', ''),
                    'genres': movie.get('genres', []),
                    'rating': movie.get('rating', 0),
                    'vote_count': movie.get('vote_count', 0),
                    'runtime': movie.get('runtime', 0),
                    'poster': movie.get('poster', ''),
                    'backdrop': movie.get('backdrop', ''),
                    'cast': movie.get('cast', []),
                    'crew': movie.get('crew', []),
                    'release_date': movie.get('release_date', ''),
                    'streams': combined_files
                }

                new_files = len(combined_files) - len(existing_files)
                if new_files > 0:
                    print(f"✓ Found {len(combined_files)} versions (+{new_files} new)")
                else:
                    print(f"✓ No new versions ({len(combined_files)} total)")

                # Mark as scanned
                if movie_id:
                    self.mark_movie_scanned(movie_id)
                return result
            else:
                print(f"✗ Not found")
                return None
        except Exception as e:
            logger.error(f"Error processing movie {movie.get('title_en', 'Unknown')}: {str(e)}")
            return None

    def process_tv_show(self, tv_show, index, total, check_new_only=False):
        """Process a single TV show with comprehensive search - FIXED COUNTING & ENHANCED"""
        try:
            print(f"[{index+1}/{total}] ", end='', flush=True)

            # Check if show already exists for incremental update
            existing_show = None
            show_id = tv_show.get('tmdb_id')

            if self.existing_data:
                for show in self.existing_data.get('tv_shows', []):
                    if show.get('tmdb_id') == show_id:
                        existing_show = show
                        break

            # Get existing seasons if available
            existing_seasons = existing_show.get('seasons', {}) if existing_show else None

            # Search for all available files
            if check_new_only and existing_show:
                files = self.find_tv_show_files_comprehensive(tv_show, check_new_only=True)
            else:
                files = self.find_tv_show_files_comprehensive(tv_show)

            # Organize episodes
            seasons = self.organize_tv_episodes(
                files,
                tv_show['title_en'],
                tv_show.get('title_cz'),
                existing_seasons
            )

            # Get season details if we have seasons
            seasons_info = tv_show.get('seasons_info', [])
            detailed_seasons = {}

            for season_info in seasons_info:
                season_num = season_info.get('season_number', 0)
                if season_num > 0:  # Skip season 0 (specials)
                    # Get detailed season info including episodes
                    detailed_season = self.get_tv_show_season_details(show_id, season_num)
                    if detailed_season:
                        detailed_seasons[season_num] = detailed_season

            if seasons:
                display_title = tv_show.get('title_cz') or tv_show['title_en']

                # Use generate_content_id for consistent IDs
                content_id = self.generate_content_id(tv_show['title_en'], tv_show.get('year', ''))

                result = {
                    'id': content_id,
                    'tmdb_id': tv_show.get('tmdb_id', ''),
                    'title': display_title,
                    'title_en': tv_show['title_en'],
                    'title_cz': tv_show.get('title_cz'),
                    'year': tv_show.get('year', ''),
                    'description': tv_show.get('description', ''),
                    'description_cz': tv_show.get('description_cz', ''),
                    'genres': tv_show.get('genres', []),
                    'rating': tv_show.get('rating', 0),
                    'vote_count': tv_show.get('vote_count', 0),
                    'poster': tv_show.get('poster', ''),
                    'backdrop': tv_show.get('backdrop', ''),
                    'cast': tv_show.get('cast', []),
                    'crew': tv_show.get('crew', []),
                    'networks': tv_show.get('networks', []),
                    'status': tv_show.get('status', ''),
                    'type': tv_show.get('type', ''),
                    'seasons': seasons,
                    'seasons_info': seasons_info,
                    'detailed_seasons': detailed_seasons,
                    'total_seasons': tv_show.get('total_seasons', len(seasons)),
                    'total_episodes': tv_show.get('total_episodes', 0)
                }

                # Count total episodes (counting each episode number once, not each file)
                episodes = sum(len(season_eps) for season_eps in seasons.values())

                # Count total files (all versions of all episodes)
                total_files = sum(len(files) for season_eps in seasons.values() for files in season_eps.values())

                if existing_show and self.incremental:
                    existing_episodes = sum(len(season_eps) for season_eps in existing_seasons.values()) if existing_seasons else 0
                    existing_files = sum(len(files) for season_eps in existing_seasons.values() for files in season_eps.values()) if existing_seasons else 0
                    new_episodes = episodes - existing_episodes
                    new_files = total_files - existing_files

                    if new_episodes > 0 or new_files > 0:
                        print(f"✓ Updated: {episodes} episodes ({new_episodes}+ new), {total_files} files ({new_files}+ new)")
                    else:
                        print(f"✓ No new episodes ({episodes} episodes, {total_files} files)")
                else:
                    print(f"✓ Found {episodes} episodes ({total_files} files)")

                # Mark as scanned
                if show_id:
                    self.mark_tv_show_scanned(show_id)
                return result
            else:
                print(f"✗ No episodes")
                return existing_show if existing_show and self.incremental else None
        except Exception as e:
            logger.error(f"Error processing TV show {tv_show.get('title_en', 'Unknown')}: {str(e)}")
            return existing_show if existing_show and self.incremental else None

    def find_tv_show_files_comprehensive(self, tv_show, check_new_only=False):
        """Search WebShare for ALL available episodes of a TV show - IMPROVED"""
        title_en = tv_show['title_en']
        title_cz = tv_show.get('title_cz')
        total_seasons = tv_show.get('total_seasons', 12)

        if check_new_only:
            print(f"  Checking for new episodes only: {title_en}")
            all_files = []
            seen_files = set()

            # For new episode checking, search recent uploads
            search_queries = [f"{title_en} s12", f"{title_en} s11", f"{title_en} 2024"]
            if title_cz:
                search_queries.extend([f"{title_cz} s12", f"{title_cz} s11"])

            for query in search_queries:
                try:
                    files = self.search_webshare_paginated(query, max_results=50)
                    for file in files:
                        ident = file['ident']
                        if ident not in seen_files:
                            filename = file.get('name', '').lower()
                            if re.search(r'[Ss]\d{1,2}[Ee]\d{1,2}', filename):
                                all_files.append(file)
                                seen_files.add(ident)
                except:
                    continue

            print(f"    Found {len(all_files)} files in new episode check")
            return all_files
        else:
            print(f"  Searching for: {title_en}" + (f" / {title_cz}" if title_cz else ""))

            # Use the search_webshare_comprehensive method for TV shows
            all_files = self.search_webshare_comprehensive(
                title_en,
                'tv',
                tv_show.get('year', ''),
                max_results=200,
                strict_matching=False
            )

            # Search by Czech title if available
            if title_cz and title_cz != title_en:
                cz_files = self.search_webshare_comprehensive(
                    title_cz,
                    'tv',
                    tv_show.get('year', ''),
                    max_results=150,
                    strict_matching=False
                )

                seen_files = {f['ident'] for f in all_files}
                for file in cz_files:
                    if file['ident'] not in seen_files:
                        all_files.append(file)

            print(f"    Found {len(all_files)} files total")
            return all_files

    def organize_tv_episodes(self, files, show_title_en, show_title_cz, existing_seasons=None):
        """Organize TV episodes by season/episode, merging with existing"""
        seasons = existing_seasons.copy() if existing_seasons else {}

        # Track unique episodes to avoid duplicates
        seen_episodes = set()

        for file in files:
            filename = file['name']

            season = 1
            episode = 1
            found_episode = False

            patterns = [
                r'[Ss](\d{1,2})[Ee](\d{1,2})',
                r'(\d{1,2})[Xx](\d{1,2})',
                r'season[._\s]?(\d{1,2})[._\s]?episode[._\s]?(\d{1,2})',
                r's(\d{1,2})[._\s]?e(\d{1,2})'
            ]

            for pattern in patterns:
                match = re.search(pattern, filename, re.I)
                if match:
                    try:
                        season = int(match.group(1))
                        episode = int(match.group(2))
                        found_episode = True
                        break
                    except (ValueError, IndexError):
                        continue

            if not found_episode:
                # Skip files without episode markers
                continue

            # Create episode key
            episode_key = f"S{season:02d}E{episode:02d}"

            # Skip if we've already processed this episode file
            if episode_key in seen_episodes:
                continue

            # Filter: Make sure the filename contains the show title
            if not self.filename_contains_title(filename, show_title_en, strict=False):
                if show_title_cz and not self.filename_contains_title(filename, show_title_cz, strict=False):
                    # Skip files that don't contain the show title
                    continue

            if season not in seasons:
                seasons[season] = {}

            # Check if episode already exists
            file_exists = False
            if episode in seasons[season]:
                for existing_file in seasons[season][episode]:
                    if existing_file['ident'] == file['ident']:
                        file_exists = True
                        break

            if not file_exists:
                if episode not in seasons[season]:
                    seasons[season][episode] = []

                seasons[season][episode].append({
                    'ident': file['ident'],
                    'filename': file['name'],
                    'size': file.get('size', '0')
                })

                # Mark this episode as processed
                seen_episodes.add(episode_key)

        return seasons

    def process_tv_show_with_specific_file_fixed(self, tv_show_data, specific_file):
        """Process a TV show with a specific file from WebShare link - ENHANCED"""
        print(f"  Processing TV show with specific file...")

        # For TV shows with specific files, use the existing TV show processing
        # but mark it as scanned since we're adding it manually
        result = self.process_tv_show(tv_show_data, 0, 1)

        if result:
            # Mark as scanned
            if tv_show_data.get('tmdb_id'):
                self.mark_tv_show_scanned(tv_show_data['tmdb_id'])

        return result

    def run(self, max_movies=20, max_tv_shows=15, incremental=True, year=None, check_new_only=False):
        """Main organizer function with incremental updates and manual content"""
        self.incremental = incremental
        self.existing_data = self.load_existing_data()

        print("=" * 70)
        print(f"TMDB-FIRST ORGANIZER ({'INCREMENTAL UPDATE' if incremental else 'FULL SCAN'})")
        if year:
            print(f"SCANNING YEAR: {year}")
        if check_new_only:
            print("CHECKING NEW EPISODES ONLY")
        print(f"Current database: {len(self.existing_data.get('movies', []))} movies, {len(self.existing_data.get('tv_shows', []))} TV shows")
        print("=" * 70)

        if not self.login():
            print("✗ Login failed!")
            sys.exit(1)

        # Get content from TMDB
        movies = self.get_tmdb_with_translations('movie', max_movies, year)
        tv_shows = self.get_tmdb_with_translations('tv', max_tv_shows, year)

        if not movies and not tv_shows:
            print("No new content to scan")
            return None

        print("\n" + "=" * 70)
        print(f"SEARCHING WEBSHARE FOR {len(movies)} MOVIES & {len(tv_shows)} TV SHOWS")
        print("=" * 70)

        found_movies = []
        found_tv_shows = []

        # Process movies in batches and update immediately
        movie_count = len(movies)
        for i, movie in enumerate(movies):
            result = self.process_movie(movie, i, movie_count)
            if result:
                found_movies.append(result)

                # Update database after each movie for immediate feedback
                self.update_main_database_with_manual_content_fixed(result, 'movie')

            time.sleep(2.0)

        # Process TV shows in batches and update immediately
        tv_show_count = len(tv_shows)
        for i, tv_show in enumerate(tv_shows):
            result = self.process_tv_show(tv_show, i, tv_show_count, check_new_only)
            if result:
                found_tv_shows.append(result)

                # Update database after each TV show for immediate feedback
                self.update_main_database_with_manual_content_fixed(result, 'tv')

            time.sleep(3.0)

        # Integrate manual content
        manual_content = self.load_manual_content()
        if manual_content['movies'] or manual_content['tv_shows']:
            print(f"\nIntegrating manual content...")

            # Update with manual content
            if manual_content['movies']:
                for movie in manual_content['movies']:
                    self.update_main_database_with_manual_content_fixed(movie, 'movie')
            if manual_content['tv_shows']:
                for show in manual_content['tv_shows']:
                    self.update_main_database_with_manual_content_fixed(show, 'tv')

        # Final summary
        final_data = self.load_existing_data()

        print("\n" + "=" * 70)
        print("FINAL DATABASE SUMMARY")
        print("=" * 70)
        print(f"Movies: {len(final_data.get('movies', []))}")
        print(f"TV Shows: {len(final_data.get('tv_shows', []))}")
        print(f"Last Updated: {final_data.get('last_updated', 'Never')}")
        print("=" * 70)

        return final_data

    def remove_content(self, title=None, tmdb_id=None):
        """Remove content from database by title or TMDB ID"""
        if not title and not tmdb_id:
            print("ERROR: Must specify either --title or --tmdb-id")
            return False

        current_data = self.load_existing_data()
        removed = False

        # Check movies
        movies_to_keep = []
        for movie in current_data.get('movies', []):
            if (tmdb_id and str(movie.get('tmdb_id')) == str(tmdb_id)) or \
               (title and title.lower() in movie.get('title', '').lower()):
                print(f"Removing movie: {movie.get('title', 'Unknown')} (TMDB ID: {movie.get('tmdb_id')})")
                removed = True
            else:
                movies_to_keep.append(movie)

        # Check TV shows
        tv_shows_to_keep = []
        for show in current_data.get('tv_shows', []):
            if (tmdb_id and str(show.get('tmdb_id')) == str(tmdb_id)) or \
               (title and title.lower() in show.get('title', '').lower()):
                print(f"Removing TV show: {show.get('title', 'Unknown')} (TMDB ID: {show.get('tmdb_id')})")
                removed = True
            else:
                tv_shows_to_keep.append(show)

        if removed:
            current_data['movies'] = movies_to_keep
            current_data['tv_shows'] = tv_shows_to_keep
            self.save_data_immediately(current_data)
            print(f"✓ Removed content successfully")
            return True
        else:
            print(f"✗ No content found with title '{title}' or TMDB ID '{tmdb_id}'")
            return False

def main():
    parser = argparse.ArgumentParser(
        description='TMDB-First Organizer with Manual Content Addition and GitHub Auto-Update',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Quick incremental update (with auto-git)
  python organizer_complete.py

  # Scan specific year
  python organizer_complete.py --year 2024

  # Check for new episodes only
  python organizer_complete.py --new-only

  # Add by TMDB ID and WebShare link (NEW!)
  python organizer_complete.py --add "tmdb:335787,webshare:https://webshare.cz/#/file/JyQkeGpXwA/uncharted-2023-cz-dab-mkv" --type movie

  # Remove content by title
  python organizer_complete.py --remove --title "Uncharted"

  # Remove content by TMDB ID
  python organizer_complete.py --remove --tmdb-id 335787

  # Scan more content
  python organizer_complete.py --movies 30 --tv-shows 20
  
  # Disable GitHub auto-update
  python organizer_complete.py --no-git
        '''
    )
    parser.add_argument('--full', action='store_true', help='Perform full scan (not incremental)')
    parser.add_argument('--movies', type=int, default=20, help='Number of movies to fetch')
    parser.add_argument('--tv-shows', type=int, default=15, help='Number of TV shows to fetch')
    parser.add_argument('--add', help='Add content manually: "tmdb:ID_OR_URL" or "name:SEARCH_QUERY" or "tmdb:ID,webshare:URL"')
    parser.add_argument('--type', choices=['movie', 'tv'], help='Content type for manual addition (optional, will auto-detect)')
    parser.add_argument('--year', type=int, help='Specific year to scan (1980-present)')
    parser.add_argument('--new-only', action='store_true', help='Check for new episodes only (for TV shows)')
    parser.add_argument('--remove', action='store_true', help='Remove content from database')
    parser.add_argument('--title', help='Title to remove (use with --remove)')
    parser.add_argument('--tmdb-id', help='TMDB ID to remove (use with --remove)')
    parser.add_argument('--no-git', action='store_true', help='Disable GitHub auto-update')

    args = parser.parse_args()

    try:
        organizer = TMDBFirstOrganizer(auto_git=not args.no_git)

        # Handle removal of content
        if args.remove:
            organizer.remove_content(title=args.title, tmdb_id=args.tmdb_id)
            return

        # Handle manual content addition
        if args.add:
            # Check if it's the combined format
            if ',' in args.add and ('tmdb:' in args.add and 'webshare:' in args.add):
                # Use the combined format
                input_method = 'combined'
                identifier = args.add
            elif ':' not in args.add:
                print("ERROR: Use format 'tmdb:ID_OR_URL' or 'name:SEARCH_QUERY' or 'tmdb:ID,webshare:URL'")
                sys.exit(1)
            else:
                input_method, identifier = args.add.split(':', 1)

            if input_method not in ['tmdb', 'name', 'webshare', 'combined']:
                print("ERROR: Input method must be 'tmdb', 'name', 'webshare', or use combined format 'tmdb:ID,webshare:URL'")
                sys.exit(1)

            if not organizer.login():
                print("✗ Login failed!")
                sys.exit(1)

            result = organizer.add_content_manually(input_method, identifier.strip(), args.type, force_type=args.type)
            if result:
                print(f"\n✓ Successfully added: {result.get('title', 'Unknown')}")
                if 'seasons' in result:
                    episodes = sum(len(eps) for eps in result['seasons'].values())
                    total_files = sum(len(files) for season_eps in result['seasons'].values() for files in season_eps.values())
                    print(f"  Found {episodes} episodes ({total_files} files total)")
                else:
                    print(f"  Found {len(result.get('streams', []))} versions")
                print(f"  Check the database: {organizer.output_file}")
            else:
                print("\n✗ Failed to add content")
        else:
            # Run normal organizer
            organizer.run(
                max_movies=args.movies,
                max_tv_shows=args.tv_shows,
                incremental=not args.full,
                year=args.year,
                check_new_only=args.new_only
            )

    except KeyboardInterrupt:
        print("\n\n⚠️ Script interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
