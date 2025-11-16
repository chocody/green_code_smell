class UserManagerAfter:
    """Refactored version with extracted validation and removal logic"""
    
    def __init__(self):
        self.users = []
        self.admins = []
    
    def _validate_user(self, user):
        """Extracted validation logic - DRY principle"""
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
    
    def _remove_from_list(self, user_list, user_id, user_type):
        """Extracted removal logic - DRY principle"""
        found = False
        for i, user in enumerate(user_list):
            if user.id == user_id:
                del user_list[i]
                found = True
                break
        
        if not found:
            raise ValueError(f"{user_type} with ID {user_id} not found")
        
        print(f"{user_type} {user_id} removed successfully")
    
    def remove_user(self, user_id):
        """Remove a user by ID"""
        self._remove_from_list(self.users, user_id, "User")
    
    def remove_admin(self, admin_id):
        """Remove an admin by ID"""
        self._remove_from_list(self.admins, admin_id, "Admin")


class DataProcessorAfter:
    """Refactored version with extracted common processing logic"""
    
    def _process_financial_data(self, data):
        """Extracted common processing logic - DRY principle"""
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
    
    def process_sales_data(self, data):
        """Process sales data using common logic"""
        return self._process_financial_data(data)
    
    def process_expense_data(self, data):
        """Process expense data using common logic"""
        return self._process_financial_data(data)
    
    def process_revenue_data(self, data):
        """Process revenue data using common logic"""
        return self._process_financial_data(data)