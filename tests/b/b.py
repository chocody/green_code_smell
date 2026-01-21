from employee_management import Company, SalariedEmployee, HourlyEmployee

def run_report():
    company = Company()

    company.add_employee(SalariedEmployee(name="Alice", role="manager"))
    company.add_employee(HourlyEmployee(name="Bob", role="intern"))
    company.add_employee(HourlyEmployee(name="Carol", role="developer"))

    company.generate_annual_report(2026)