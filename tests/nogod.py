#god refactored

class UserManager:
    def __init__(self):
        self.users = []

    def add(self, username):
        self.users.append(username)


class Database:
    def __init__(self):
        self.data = {}

    def save(self, key, value):
        self.data[key] = value


class Logger:
    def __init__(self):
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)

    def dump(self):
        return "\n".join(self.logs)


class SystemFacade:
    def __init__(self):
        self.user_manager = UserManager()
        self.database = Database()
        self.logger = Logger()

    def add_user(self, username):
        self.user_manager.add(username)
        self.logger.log(f"Added user {username}")

    def save_data(self, key, value):
        self.database.save(key, value)
        self.logger.log(f"Saved data: {key}={value}")

    def generate_report(self):
        report = "Report:\n"
        report += f"Users: {self.user_manager.users}\n"
        report += f"DB: {self.database.data}\n"
        self.logger.log("Report generated")
        return report

    def print_logs(self):
        return self.logger.dump()


def run_after():
    system = SystemFacade()
    system.add_user("alice")
    system.add_user("bob")
    system.save_data("score", 100)
    system.save_data("level", 5)
    return system.generate_report(), system.print_logs()


if __name__ == "__main__":
    rep, logs = run_after()
    print("===== AFTER REFACTOR =====")
    print(rep)
    print(logs)
