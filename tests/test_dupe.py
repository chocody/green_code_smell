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