"""
Behavior Tracker - Adaptive learning system
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from services.data_service import DataService


class BehaviorTracker:
    """
    Tracks user behavior and adapts recommendations based on patterns
    """
    
    def __init__(self, data_service: DataService):
        self.data_service = data_service
    
    def record_action(self, action_type: str, recommendation_id: int = None,
                     accepted: bool = False, context: Dict = None) -> int:
        """
        Record a user action for learning
        """
        context_str = str(context) if context else ""
        return self.data_service.log_behavior(
            action_type=action_type,
            recommendation_id=recommendation_id,
            accepted=accepted,
            context_data=context_str
        )
    
    def get_user_preferences(self) -> Dict:
        """
        Learn user preferences from behavior history
        """
        preferences = {
            'preferred_action_types': {},
            'peak_activity_hours': {},
            'acceptance_by_priority': {},
            'response_time_average': 0
        }
        
        conn = self.data_service._get_connection()
        cursor = conn.cursor()
        
        # Get recent behavior
        thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
        cursor.execute("""
            SELECT * FROM user_behavior
            WHERE timestamp >= ?
        """, (thirty_days_ago,))
        
        behaviors = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not behaviors:
            return preferences
        
        # Analyze preferred action types
        for behavior in behaviors:
            action_type = behavior['action_type']
            if action_type not in preferences['preferred_action_types']:
                preferences['preferred_action_types'][action_type] = {
                    'total': 0,
                    'accepted': 0
                }
            preferences['preferred_action_types'][action_type]['total'] += 1
            if behavior['accepted']:
                preferences['preferred_action_types'][action_type]['accepted'] += 1
        
        # Calculate acceptance rates
        for action_type, data in preferences['preferred_action_types'].items():
            if data['total'] > 0:
                data['acceptance_rate'] = data['accepted'] / data['total']
        
        # Analyze peak activity hours
        for behavior in behaviors:
            timestamp = datetime.fromisoformat(behavior['timestamp'])
            hour = timestamp.hour
            if hour not in preferences['peak_activity_hours']:
                preferences['peak_activity_hours'][hour] = 0
            preferences['peak_activity_hours'][hour] += 1
        
        return preferences
    
    def adjust_confidence(self, action_type: str, base_confidence: float) -> float:
        """
        Adjust confidence score based on historical acceptance
        """
        acceptance_rate = self.data_service.get_acceptance_rate(action_type, days=30)
        
        # If acceptance rate is high, increase confidence
        # If acceptance rate is low, decrease confidence
        if acceptance_rate > 0.7:
            adjustment = 0.1
        elif acceptance_rate < 0.3:
            adjustment = -0.1
        else:
            adjustment = 0.0
        
        adjusted_confidence = base_confidence + adjustment
        return round(max(0.1, min(1.0, adjusted_confidence)), 2)
    
    def should_show_popup(self, action_type: str, last_popup_time: datetime = None) -> bool:
        """
        Determine if a popup should be shown based on user behavior patterns
        """
        import config
        
        # Check cooldown
        if last_popup_time:
            time_since = (datetime.now() - last_popup_time).total_seconds()
            if time_since < config.POPUP_COOLDOWN_SECONDS:
                return False
        
        # Check if user frequently ignores this type of recommendation
        acceptance_rate = self.data_service.get_acceptance_rate(action_type, days=7)
        if acceptance_rate < 0.2:  # User ignores 80%+ of these
            return False
        
        return True
    
    def get_learning_summary(self) -> Dict:
        """
        Get a summary of what the system has learned about the user
        """
        preferences = self.get_user_preferences()
        summary = {
            'total_actions': 0,
            'overall_acceptance_rate': 0.0,
            'most_accepted_action': None,
            'least_accepted_action': None,
            'peak_activity_hour': None
        }
        
        conn = self.data_service._get_connection()
        cursor = conn.cursor()
        
        # Get total actions
        cursor.execute("SELECT COUNT(*) as count FROM user_behavior")
        result = cursor.fetchone()
        summary['total_actions'] = result['count'] if result else 0
        
        # Get overall acceptance rate
        cursor.execute("""
            SELECT 
                CAST(SUM(CASE WHEN accepted = 1 THEN 1 ELSE 0 END) AS FLOAT) / 
                CAST(COUNT(*) AS FLOAT) as rate
            FROM user_behavior
        """)
        result = cursor.fetchone()
        summary['overall_acceptance_rate'] = round(result['rate'] * 100, 1) if result and result['rate'] else 0
        
        # Find most/least accepted actions
        if preferences['preferred_action_types']:
            acceptance_rates = {
                action: data['acceptance_rate']
                for action, data in preferences['preferred_action_types'].items()
                if 'acceptance_rate' in data
            }
            
            if acceptance_rates:
                summary['most_accepted_action'] = max(acceptance_rates, key=acceptance_rates.get)
                summary['least_accepted_action'] = min(acceptance_rates, key=acceptance_rates.get)
        
        # Find peak activity hour
        if preferences['peak_activity_hours']:
            summary['peak_activity_hour'] = max(
                preferences['peak_activity_hours'],
                key=preferences['peak_activity_hours'].get
            )
        
        conn.close()
        
        return summary
