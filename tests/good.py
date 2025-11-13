# Good example - refactored code without duplication
class GoodUserManager:
    """Example of properly refactored code"""
    
    def __init__(self):
        self.users = []
        self.admins = []
    
    def _validate_user(self, user):
        """Shared validation logic"""
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
    
    def add_user(self, user):
        """Add a regular user"""
        self._validate_user(user)
        self.users.append(user)
        print(f"User {user.name} added successfully")
    
    def add_admin(self, admin):
        """Add an admin user"""
        self._validate_user(admin)
        self.admins.append(admin)
        print(f"Admin {admin.name} added successfully")

class GoodClass:
    """A well-designed class with single responsibility"""
    def __init__(self):
        self.name = "Good"
        self.value = 0
    
    def get_name(self):
        return self.name
    
    def set_value(self, val):
        self.value = val