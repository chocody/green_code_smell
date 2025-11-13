class GoodClass:
    """A well-designed class with single responsibility"""
    def __init__(self):
        self.name = "Good"
        self.value = 0
    
    def get_name(self):
        return self.name
    
    def set_value(self, val):
        self.value = val

class GodClassExample:
    """
    This is a God Class - it has too many responsibilities!
    It handles user management, database operations, logging,
    email sending, file operations, and more.
    """
    
    def __init__(self):
        # Too many attributes
        self.users = []
        self.database_connection = None
        self.logger = None
        self.email_server = None
        self.file_handler = None
        self.cache = {}
        self.settings = {}
        self.session_data = {}
        self.api_keys = {}
        self.permissions = {}
        self.audit_log = []
        self.error_queue = []
    
    # User management methods
    def add_user(self, user):
        self.users.append(user)
    
    def remove_user(self, user_id):
        self.users = [u for u in self.users if u.id != user_id]
    
    def update_user(self, user_id, data):
        for user in self.users:
            if user.id == user_id:
                user.update(data)
    
    def find_user(self, user_id):
        return next((u for u in self.users if u.id == user_id), None)
    
    # Database methods
    def connect_database(self):
        pass
    
    def disconnect_database(self):
        pass
    
    def execute_query(self, query):
        pass
    
    def commit_transaction(self):
        pass
    
    def rollback_transaction(self):
        pass
    
    # Logging methods
    def log_info(self, message):
        pass
    
    def log_error(self, message):
        pass
    
    def log_warning(self, message):
        pass
    
    # Email methods
    def send_email(self, to, subject, body):
        pass
    
    def send_bulk_email(self, recipients, subject, body):
        pass
    
    def validate_email(self, email):
        pass
    
    # File operations
    def read_file(self, path):
        pass
    
    def write_file(self, path, content):
        pass
    
    def delete_file(self, path):
        pass
    
    # Cache operations
    def get_from_cache(self, key):
        return self.cache.get(key)
    
    def set_in_cache(self, key, value):
        self.cache[key] = value
    
    def clear_cache(self):
        self.cache.clear()
    
    # Settings management
    def load_settings(self):
        pass
    
    def save_settings(self):
        pass
    
    def get_setting(self, key):
        return self.settings.get(key)
    
    def set_setting(self, key, value):
        self.settings[key] = value
    
    # Permission management
    def check_permission(self, user, action):
        pass
    
    def grant_permission(self, user, action):
        pass
    
    def revoke_permission(self, user, action):
        pass
    
    # Audit logging
    def log_audit(self, action, user, details):
        self.audit_log.append({
            'action': action,
            'user': user,
            'details': details
        })
    
    def get_audit_log(self, user=None):
        if user:
            return [log for log in self.audit_log if log['user'] == user]
        return self.audit_log


# Test the detection
# if __name__ == "__main__":
#     from green_code_smell.core import analyze_file
#     from green_code_smell.rules.god_class import GodClassRule
    
#     rules = [GodClassRule(max_methods=10, max_attributes=10, max_lines=100)]
#     issues = analyze_file(__file__, rules)
    
#     for issue in issues:
#         print(f"{issue['rule']} (line {issue['lineno']}): {issue['message']}")