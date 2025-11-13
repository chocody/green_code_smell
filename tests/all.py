from green_code_smell import core

class ExampleClass:
    def sum(a, b):
        return a + b

    def multiply(a, b):
        return a * b
    
    def logging_example():
        import logging
        for i in range(20):
            logging.info(f"Logging iteration {i}")

    def logging_heavy():
        import logging
        logging.debug("Debug message")
        logging.info("Info message")
        logging.warning("Warning message")
        logging.error("Error message")
        logging.critical("Critical message")
        logging.info("Another info message")

code_info = core.code_info("tests/example.py")
print(code_info)

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

class UserManager:
    """Example with duplicated code blocks"""
    
    def __init__(self):
        self.users = []
        self.admins = []
    
    def add_user(self, user):
        """Add a regular user"""
        # Duplicated validation code
        if not user:
            raise ValueError("User cannot be None")
        if not hasattr(user, 'name'):
            raise ValueError("User must have a name")
        if not hasattr(user, 'email'):
            raise ValueError("User must have an email")
        if not user.email:
            raise ValueError("Email cannot be empty")
        if '@' not in user.email:
            raise ValueError("Invalid email format")
        
        self.users.append(user)
        print(f"User {user.name} added successfully")
    
    def add_admin(self, admin):
        """Add an admin user"""
        # Duplicated validation code (same as add_user)
        if not admin:
            raise ValueError("User cannot be None")
        if not hasattr(admin, 'name'):
            raise ValueError("User must have a name")
        if not hasattr(admin, 'email'):
            raise ValueError("User must have an email")
        if not admin.email:
            raise ValueError("Email cannot be empty")
        if '@' not in admin.email:
            raise ValueError("Invalid email format")
        
        self.admins.append(admin)
        print(f"Admin {admin.name} added successfully")
    
    def remove_user(self, user_id):
        """Remove a user by ID"""
        # Duplicated search and removal logic
        found = False
        for i, user in enumerate(self.users):
            if user.id == user_id:
                del self.users[i]
                found = True
                break
        
        if not found:
            raise ValueError(f"User with ID {user_id} not found")
        
        print(f"User {user_id} removed successfully")
    
    def remove_admin(self, admin_id):
        """Remove an admin by ID"""
        # Duplicated search and removal logic (same as remove_user)
        found = False
        for i, admin in enumerate(self.admins):
            if admin.id == admin_id:
                del self.admins[i]
                found = True
                break
        
        if not found:
            raise ValueError(f"Admin with ID {admin_id} not found")
        
        print(f"Admin {admin_id} removed successfully")


class DataProcessor:
    """Example with similar function implementations"""
    
    def process_sales_data(self, data):
        """Process sales data"""
        if not data:
            return []
        
        result = []
        total = 0
        count = 0
        
        for item in data:
            value = item.get('amount', 0)
            total += value
            count += 1
            result.append(value)
        
        average = total / count if count > 0 else 0
        return {
            'values': result,
            'total': total,
            'count': count,
            'average': average
        }
    
    def process_expense_data(self, data):
        """Process expense data - almost identical to process_sales_data"""
        if not data:
            return []
        
        result = []
        total = 0
        count = 0
        
        for item in data:
            value = item.get('amount', 0)
            total += value
            count += 1
            result.append(value)
        
        average = total / count if count > 0 else 0
        return {
            'values': result,
            'total': total,
            'count': count,
            'average': average
        }
    
    def process_revenue_data(self, data):
        """Process revenue data - almost identical to process_sales_data"""
        if not data:
            return []
        
        result = []
        total = 0
        count = 0
        
        for item in data:
            value = item.get('amount', 0)
            total += value
            count += 1
            result.append(value)
        
        average = total / count if count > 0 else 0
        return {
            'values': result,
            'total': total,
            'count': count,
            'average': average
        }
