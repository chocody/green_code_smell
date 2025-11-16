#god example

class GodClass:
    def __init__(self):
        self.users = []
        self.logs = []
        self.db = {}

    def add_user(self, username):
        self.users.append(username)
        self.logs.append(f"Added user {username}")

    def save_data(self, key, value):
        self.db[key] = value
        self.logs.append(f"Saved data: {key}={value}")

    def generate_report(self):
        report = "Report:\n"
        report += f"Users: {self.users}\n"
        report += f"DB: {self.db}\n"
        self.logs.append("Report generated")
        return report

    def print_logs(self):
        return "\n".join(self.logs)


def run_before():
    system = GodClass()
    system.add_user("alice")
    system.add_user("bob")
    system.save_data("score", 100)
    system.save_data("level", 5)
    return system.generate_report(), system.print_logs()


if __name__ == "__main__":
    rep, logs = run_before()
    print("===== NO REFACTOR =====")
    print(rep)
    print(logs)
