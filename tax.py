def adjust_standard_deduction(year, inflation_rate):
    # Standard deduction for the year 2022
    standard_deduction_2022 = 27700
    
    # Adjust standard deduction for the specified year and inflation rate
    adjusted_deduction = int(standard_deduction_2022 * ((1 + inflation_rate) ** (year - 2022)))
    
    return adjusted_deduction


def adjust_brackets_for_inflation(year, inflation_rate):
    # Initial tax brackets for the year 2022
    brackets_2022 = [(0, 19750), (19751, 80250), (80251, 171050), (171051, 326600), (326601, 414700), (414701, 622050)]
    
    # Inflation adjustment for each bracket for the specified year
    adjusted_brackets = [(int(bracket[0] * ((1 + inflation_rate) ** (year - 2022))),
                          int(bracket[1] * ((1 + inflation_rate) ** (year - 2022)))) 
                          for bracket in brackets_2022]
    
    return adjusted_brackets


def estimate_federal_taxes(gross_income, year, inflation_rate, num_children):
    # Define federal tax rates for the year 2022
    federal_rates_2022 = [0.1, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]
    
    # Adjust standard deduction for the specified year and inflation rate
    standard_deduction = adjust_standard_deduction(year, inflation_rate)
    
    # Subtract standard deduction from gross income
    taxable_income = max(0, gross_income - standard_deduction)
    
    # Adjust federal tax brackets for the specified year and inflation rate
    adjusted_brackets = adjust_brackets_for_inflation(year, inflation_rate)
    
    remaining_income = taxable_income
    federal_tax = 0

    for i in range(len(adjusted_brackets)):
        bracket = adjusted_brackets[i]
        rate = federal_rates_2022[i]
        if remaining_income <= 0:
            break
        bracket_min, bracket_max = bracket
        bracket_range = min(remaining_income, bracket_max - bracket_min + 1)
        federal_tax += bracket_range * rate
        remaining_income -= bracket_range

    # Adjust $2000 per child federal tax deduction for inflation
    child_tax_deduction = 2000 * ((1 + inflation_rate) ** (year - 2022))
    
    # Subtract adjusted child federal tax deduction from federal taxes for each child
    federal_tax -= child_tax_deduction * num_children

    return max(0, federal_tax)  # Ensure tax is not negative


def estimate_state_taxes(gross_income, state_tax_rate):
    # Calculate state taxes
    state_tax = gross_income * state_tax_rate
    return state_tax

'''
# Example usage:
income = float(input("Enter your gross income: "))
year = int(input("Enter the year: "))
inflation_rate = float(input("Enter the annual inflation rate (as a decimal): "))
num_children = int(input("Enter the number of children: "))
state_tax_rate = 0.0495  # 4.95% state tax rate

estimated_federal_tax = estimate_federal_taxes(income, year, inflation_rate, num_children)
estimated_state_tax = estimate_state_taxes(income, state_tax_rate)

total_tax = estimated_federal_tax + estimated_state_tax
print(f"Estimated total taxes for the year {year} adjusted for inflation, standard deduction, children, and state taxes: $", round(total_tax, 2))
'''