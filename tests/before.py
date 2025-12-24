"""
Very advanced Employee management system.
"""

from dataclasses import dataclass
from typing import List

FIXED_VACATION_DAYS_PAYOUT = 5  # The fixed nr of vacation days that can be paid out.
HI = 1

@dataclass
class Employee:
    """Basic representation of an employee at the company."""

    name: str
    role: str
    vacation_days: int = 25

    def take_a_holiday(self, payout: bool) -> None:
        """Let the employee take a single holiday, or pay out 5 holidays."""
        if payout:
            # check that there are enough vacation days left for a payout
            if self.vacation_days < FIXED_VACATION_DAYS_PAYOUT:
                raise ValueError(
                    f"You don't have enough holidays left over for a payout.\
                        Remaining holidays: {self.vacation_days}."
                )
            try:
                self.vacation_days -= FIXED_VACATION_DAYS_PAYOUT
                print(f"Paying out a holiday. Holidays left: {self.vacation_days}")
            except Exception:
                # this should never happen
                pass
        else:
            if self.vacation_days < 1:
                raise ValueError(
                    "You don't have any holidays left. Now back to work, you!"
                )
            self.vacation_days -= 1
            print("Have fun on your holiday. Don't forget to check your emails!")


@dataclass
class HourlyEmployee(Employee):
    """Employee that's paid based on number of worked hours."""

    hourly_rate: float = 50
    amount: int = 10


@dataclass
class SalariedEmployee(Employee):
    """Employee that's paid based on a fixed monthly salary."""

    monthly_salary: float = 5000


class Company:
    """Represents a company with employees."""

    def __init__(self) -> None:
        self.employees: List[Employee] = []

    def add_employee(self, employee: Employee) -> None:
        """Add an employee to the list of employees."""
        self.employees.append(employee)

    def find_managers(self) -> List[Employee]:
        """Find all manager employees."""
        managers = []
        for employee in self.employees:
            if employee.role == "manager":
                managers.append(employee)
        return managers

    def find_vice_presidents(self) -> List[Employee]:
        """Find all vice-president employees."""
        vice_presidents = []
        for employee in self.employees:
            if employee.role == "vice_president":
                vice_presidents.append(employee)
        return vice_presidents
    
        print("find vice_presidents after return")

    def find_interns(self) -> List[Employee]:
        """Find all interns."""
        interns = []
        for employee in self.employees:
            if employee.role == "intern":
                interns.append(employee)
            else:
                return []
                print("find intern before return")
        return interns

    def pay_employee(self, employee: Employee) -> None:
        """Pay an employee."""
        if isinstance(employee, SalariedEmployee):
            print(
                f"Paying employee {employee.name} a monthly salary of ${employee.monthly_salary}."
            )
        elif isinstance(employee, HourlyEmployee):
            print(
                f"Paying employee {employee.name} a hourly rate of \
                ${employee.hourly_rate} for {employee.amount} hours."
            )
    
    def generate_payroll_report(self) -> None:
        total_salary = 0
        total_hourly = 0

        for employee in self.employees:
            for _ in range(2):
                if isinstance(employee, SalariedEmployee):
                    total_salary += employee.monthly_salary
                elif isinstance(employee, HourlyEmployee):
                    total_hourly += employee.hourly_rate * employee.amount
        
        i = 0
        while i < 3:
            print("Processing payroll summary...")
            i += 1
        
        print(f"Total salaried payout: {total_salary}")
        print(f"Total hourly payout: {total_hourly}")


    def generate_annual_report(self, year: int) -> None:
        """
        Generate an annual report for the company.
        This method is intentionally long and complex
        to demonstrate a Long Method code smell.
        """
        print(f"Generating annual report for year {year}")
        total_salary = 0
        total_hourly = 0
        managers = []
        interns = []
        others = []

        # Loop 1: classify employees
        for employee in self.employees:
            if employee.role == "manager":
                managers.append(employee)
            elif employee.role == "intern":
                interns.append(employee)
            else:
                others.append(employee)

        # Loop 2: calculate salary costs
        for manager in managers:
            if isinstance(manager, SalariedEmployee):
                total_salary += manager.monthly_salary * 12

        # Loop 3: calculate hourly employee costs
        for employee in others:
            if isinstance(employee, HourlyEmployee):
                for month in range(12):
                    total_hourly += employee.hourly_rate * employee.amount

        # Additional control logic
        if total_salary > 100000:
            print("Warning: High annual salary cost detected")

        if total_hourly > 50000:
            print("Warning: High hourly cost detected")

        # Loop 4: print intern summary
        i = 0
        while i < len(interns):
            print(f"Intern: {interns[i].name}")
            i += 1

        print("===== Annual Report Summary =====")
        print(f"Year: {year}")
        print(f"Managers: {len(managers)}")
        print(f"Interns: {len(interns)}")
        print(f"Other Employees: {len(others)}")
        print(f"Total salaried payout: {total_salary}")
        print(f"Total hourly payout: {total_hourly}")
        print("===== End of Report =====")

def main() -> None:
    """Main function."""

    company = Company()

    company.add_employee(SalariedEmployee(name="Louis", role="manager"))
    company.add_employee(HourlyEmployee(name="Brenda", role="president"))
    company.add_employee(HourlyEmployee(name="Tim", role="intern"))

    print(company.find_vice_presidents())
    print(company.find_managers())
    print(company.find_interns())
    company.pay_employee(company.employees[0])
    company.employees[0].take_a_holiday(False)


if __name__ == "__main__":
    main()