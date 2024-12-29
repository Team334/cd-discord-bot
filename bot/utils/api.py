import aiohttp
import json
import feedparser
from pathlib import Path
from typing import List, Dict, Optional
from io import BytesIO


CD_API_BASE = "https://www.chiefdelphi.com"
CD_LATEST_URL = f"{CD_API_BASE}/latest.rss"  # RSS feed URL
PERSIST_FILE = Path("persist.json")

class ChiefDelphiAPI:
    def __init__(self, refresh_rate: int = 15 * 1000):
        self.previous_ids = self._load_persisted_ids()
        self.refresh_rate = refresh_rate

    def _load_persisted_ids(self) -> List[str]:
        """Load previously seen post IDs from persistence file."""
        if PERSIST_FILE.exists():
            return json.loads(PERSIST_FILE.read_text())
        self._save_persisted_ids([])
        return []

    def _save_persisted_ids(self, ids: List[str]) -> None:
        """Save post IDs to persistence file."""
        PERSIST_FILE.write_text(json.dumps(ids))

    async def get_recent_posts(self) -> List[Dict]:
        """Fetch and parse new posts from Chief Delphi RSS feed."""
        async with aiohttp.ClientSession() as session:
            async with session.get(CD_LATEST_URL) as response:
                if response.status != 200:
                    print(f"Error: Status code {response.status}")
                    return []
                
                content = await response.text()
                feed = feedparser.parse(BytesIO(content.encode('utf-8')))
                
                posts = []
                new_ids = []
                
                for entry in feed.entries:
                    post_id = entry.id.split('-')[-1]  # Changed from split('/') to split('-')
                    post = {
                        'id': post_id,
                        'title': entry.title,
                        'author': entry.author,
                        'preview': entry.summary,
                        'thread_url': entry.link,
                        'created_at': entry.published
                    }
                    
                    new_ids.append(post_id)  # Now storing just the number
                    
                    if post_id not in self.previous_ids:
                        posts.append(post)
                
                self._save_persisted_ids(new_ids)
                self.previous_ids = new_ids
                
                return posts

    def check_triggers(self, post: Dict, triggers: List[Dict]) -> List[Dict]:
        """Check if a post matches any triggers."""
        matched_triggers = []
        
        for trigger in triggers:
            # Check author triggers
            if 'authors' in trigger and post['author'].lower() in [a.lower() for a in trigger['authors']]:
                matched_triggers.append({
                    'trigger': trigger,
                    'type': 'author',
                    'matches': [post['author']]
                })
                continue
            
            # Check keyword triggers
            if 'keywords' in trigger:
                matches = []
                preview_lower = post['preview'].lower()
                title_lower = post['title'].lower()
                
                for keyword in trigger['keywords']:
                    keyword_lower = keyword.lower()
                    if keyword_lower in preview_lower or keyword_lower in title_lower:
                        matches.append(keyword)
                
                if matches:
                    matched_triggers.append({
                        'trigger': trigger,
                        'type': 'keyword',
                        'matches': matches
                    })
        
        return matched_triggers

    async def get_post(self, post_id: str) -> Optional[Dict]:
        """Fetch a specific post by ID."""
        async with aiohttp.ClientSession() as session:
            # Changed URL format to match Chief Delphi's RSS structure
            url = f"{CD_API_BASE}/t/{post_id}.rss"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    print(f"Error: Status code {response.status}")
                    return None
                
                content = await response.text()
                feed = feedparser.parse(BytesIO(content.encode('utf-8')))
                
                if not feed.entries:
                    return None
                
                entry = feed.entries[0]
                return {
                    'id': post_id,
                    'title': entry.title,
                    'author': entry.author,
                    'preview': entry.summary,
                    'thread_url': entry.link,
                    'created_at': entry.published
                }

    async def search_posts(
        self, 
        query: str, 
        limit: int = 10,
        search_type: str = "all"
    ) -> List[Dict]:
        """Search posts using the RSS feed."""
        async with aiohttp.ClientSession() as session:
            async with session.get(CD_LATEST_URL) as response:
                if response.status != 200:
                    print(f"Error: Status code {response.status}")
                    return []

                content = await response.text()
                feed = feedparser.parse(BytesIO(content.encode('utf-8')))

                results = []
                query = query.lower()

                for entry in feed.entries:
                    # Check based on search type
                    match = False
                    if (
                        search_type in {"all", "title"}
                        and query in entry.title.lower()
                    ):
                        match = True
                    if search_type in {"all", "preview"} and query in entry.summary.lower():
                        match = True
                    if search_type in {"all", "author"} and query in entry.author.lower():
                        match = True

                    if match:
                        post_id = entry.id.split('-')[-1]
                        results.append({
                            'id': post_id,
                            'title': entry.title,
                            'author': entry.author,
                            'thread_url': entry.link,
                            'created_at': entry.published
                        })

                        if len(results) >= limit:
                            break

                return results
