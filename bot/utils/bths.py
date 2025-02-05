import contextlib
import xml.etree.ElementTree as ET
import requests
from datetime import datetime
from typing import List, Dict, Optional

class BTHSCalendar:
    """Helper class to handle BTHS calendar RSS feed"""
    
    CALENDAR_URL = "https://www.bths.edu/apps/events/events_rss.jsp?id=0"

    def __init__(self):
        self._events = []  # Changed to protected variable
        self.last_updated = None
        self.cycle_days = {}

    @property
    def events(self):
        """Property to ensure events are fetched if empty"""
        if not self._events:
            self.fetch_calendar()
        return self._events

    def fetch_calendar(self) -> bool:
        """
        Fetches and parses the BTHS calendar RSS feed
        Returns True if successful, False otherwise
        """
        try:
            response = requests.get(self.CALENDAR_URL)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            self._events = []  # Use _events instead of events
            self.cycle_days = {}
            
            channel = root.find('channel')
            if channel is None:
                raise Exception("No channel found in RSS feed")
            
            items = channel.findall('item')
            
            for item in items:
                title = item.find('title')
                description = item.find('description')
                pub_date = item.find('pubDate')
                
                title_text = title.text if title is not None else ""
                desc_text = description.text if description is not None else ""
                date_text = pub_date.text if pub_date is not None else None

                # Extract event date from description (it's in the first line)
                event_date = None
                if desc_text:
                    with contextlib.suppress(ValueError, IndexError):
                        date_str = desc_text.strip().split('\n')[0].strip()
                        event_date = datetime.strptime(date_str, "%m/%d/%Y")
                
                # Parse cycle day from title
                cycle_day = None
                if title_text:
                    with contextlib.suppress(ValueError, IndexError):
                        first_part = title_text.split('-')[0].strip()
                        if first_part.isdigit():
                            cycle_day = int(first_part)
                            if event_date:
                                self.cycle_days[event_date.date()] = cycle_day

                event = {
                    'title': title_text,
                    'description': desc_text,
                    'pubDate': date_text,
                    'link': item.find('link').text if item.find('link') is not None else None,
                    'cycle_day': cycle_day,
                    'date': event_date
                }
                self._events.append(event)
            
            # Sort events by date
            self._events.sort(key=lambda x: x['date'] if x['date'] else datetime.max)
            
            self.last_updated = datetime.now()
            return True
            
        except (requests.RequestException, ET.ParseError) as e:
            raise e

    def get_cycle_day(self, date: Optional[datetime] = None) -> Optional[int]:
        """
        Returns the cycle day for a given date
        If no date is provided, returns the cycle day for today
        """
        if not self.events:
            self.fetch_calendar()

        if date is None:
            date = datetime.now()
        
        return self.cycle_days.get(date.date())

    def get_week_schedule(self) -> List[Dict]:
        """
        Returns the schedule for the current week including cycle days
        """
        if not self._events:
            self.fetch_calendar()

        today = datetime.now()
        week_schedule = []
        
        for event in self._events:
            if event['date'] and event['date'].date() >= today.date():
                week_schedule.append({
                    'date': event['date'],
                    'day_name': event['date'].strftime('%A'),
                    'cycle_day': event['cycle_day'],
                    'title': event['title'],
                    'description': event['description']
                })
                
                if len(week_schedule) >= 5:  # Get next 5 school days
                    break

        return week_schedule

    def get_upcoming_events(self, limit: int = 5) -> List[Dict]:
        """Returns the specified number of upcoming events"""
        if not self._events:
            self.fetch_calendar()
        
        today = datetime.now()
        upcoming = [
            event for event in self._events
            if event['date'] and event['date'] >= today
        ]
        return upcoming[:limit]

    def search_events(self, query: str) -> List[Dict]:
        """Searches events for the given query string"""
        if not self._events:
            self.fetch_calendar()

        query_date = None
        with contextlib.suppress(ValueError):
            # Try to parse the query as a date
            query_date = datetime.strptime(query, '%m/%d/%Y').date()
        results = []
        for event in self._events:
            if query_date and event['date']:
                # Match by exact date
                if event['date'].date() == query_date:
                    results.append(event)
            elif query.lower() in event['title'].lower() or (
                event['description'] and query.lower() in event['description'].lower()
            ):
                results.append(event)

        return results

    def get_event_by_title(self, title: str) -> Optional[Dict]:
        """Returns a specific event by its exact title"""
        if not self.events:
            self.fetch_calendar()

        return next(
            (
                event
                for event in self.events
                if event['title'].lower() == title.lower()
            ),
            None,
        )
