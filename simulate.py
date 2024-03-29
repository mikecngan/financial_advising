import json
from datetime import datetime
import pandas as pd
from tax import estimate_federal_taxes, estimate_state_taxes
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Set the style of the plot
sns.set_style("whitegrid")

#tax-deferred contribution limit (aka 401k contribution limits)
tdt_contribution_limit = 23000 #this is normally 23000 but can be lowered if contributions are lower
cost_of_college = 42162

json_file = 'test_human'
# Read the JSON file
with open(json_file + '.json', 'r') as f:
    data = json.load(f)

# Get the current year
current_year = datetime.now().year

# Simulate until first family member is 99
first_member_age = data['family_members'][0]['age']
simulation_end_date = current_year + (99 - first_member_age)
#simulation_end_date = current_year + 2

# Initialize the current year to the start year
year = current_year

# Inflation rate used
inflation_rate = data['inflation_rate']
retirement = []
for i in range(len(data['income_sources'])):
    end_age = data['income_sources'][i].get('end_age')
    if end_age is not None:
        family_member_index = [j for j, member in enumerate(data['family_members']) if member['name'] == data['income_sources'][i]['family_member']][0]
        retirement.append(end_age - data['family_members'][family_member_index]['age'] + year)

# Convert the stuff to a DataFrames
df_accounts = pd.DataFrame(data['accounts'])
print(df_accounts)

df_family = pd.DataFrame(data['family_members'])
num_children = (df_family['age'] < 21).sum()
print(df_family)

df_income = pd.DataFrame(data['income_sources'])
print(df_income)

df_expenditure = pd.DataFrame(data['expenditure'])
df_expenditure['annual_cost'] = df_expenditure['monthly_cost'] * 12
print(df_expenditure)

# Create a DataFrame to store the balance of each account for each year
df_balance_history = pd.DataFrame()
df_expenditure_history = pd.DataFrame()
df_college_cost_history = pd.DataFrame()
df_taxes = pd.DataFrame()

# taxes
withdraw_penalty = 0
cap_gains = 0
interest = 0

cost_basis = []
# grab all cost_basis from investment type df_accounts
for i in range(len(df_accounts)):
    if df_accounts.loc[i, 'type'] == 'Investment':
        cost_basis.append(df_accounts.loc[i, 'basis'])

print("cost_basis", cost_basis)

income_from_retirement_accounts = 0

# Simulate the growth of the accounts year by year until simulation_end_date
while year <= simulation_end_date:
    # Calculate the gross income
    gross_income = 0
    tdt_contribution = 0
    tdt_contributions = 0
    for idx, row in df_income.iterrows():
        if row['name'] != 'Rent': #this is complicated but deprication will likely cancel out all rent income for tax purposes
            family_member_age = df_family.loc[df_family['name'] == row['family_member'], 'age'].values[0]
            if ((family_member_age >= row['start_age']) or pd.isnull(row['start_age'])) and ((family_member_age <= row['end_age']) or pd.isnull(row['end_age'])):
                gross_income += row['income']
                #if row['401-k_matching'] is not nan, then calculate the 401k contribution
                if not pd.isnull(row['401-k_matching']) and row['401-k_matching'] > 0:
                    tdt_contributions += 1 #if there's no matching is there a point?
                    tdt_contribution = tdt_contribution_limit + (row['income'] * row['401-k_matching'])
    #print('Gross Income:', gross_income)
    #print('tdt_contribution:', tdt_contribution)

    # Calculate the estimated federal and state taxes
    estimated_federal_taxes = estimate_federal_taxes(gross_income + income_from_retirement_accounts + withdraw_penalty + interest - (tdt_contribution_limit * tdt_contributions), year, inflation_rate, num_children) + (cap_gains * 0.15)
    estimated_state_taxes = estimate_state_taxes(gross_income + income_from_retirement_accounts + withdraw_penalty + interest + cap_gains - (tdt_contribution_limit * tdt_contributions), 0.0495)

    # Subtract the estimated taxes from the gross income
    net_income = gross_income - estimated_federal_taxes - estimated_state_taxes - df_expenditure.loc[df_expenditure['name'] == 'pre-tax expenses', 'annual_cost'].values[0] - tdt_contribution_limit
    #net_income = gross_income - estimated_federal_taxes - estimated_state_taxes - np.array(df_expenditure.loc[df_expenditure['name'] == 'pre-tax expenses', 'annual_cost'])[0] - tdt_contribution
    #print('Net Income:', net_income)

    #store income and taxes
    new_row = pd.DataFrame({
        'gross_income': [gross_income],
        'net_income': [net_income],
        'federal_taxes': [estimated_federal_taxes],
        'state_taxes': [estimated_state_taxes],
        'income_from_retirement_accounts': [income_from_retirement_accounts],
        'withdraw_penalty': [withdraw_penalty],
        'cap_gains': [cap_gains],
        'interest': [interest],
        #'cost_basis': [cost_basis],
        'tdt_contribution': [tdt_contribution],
        'year': [year]
    })
    
    df_taxes = pd.concat([df_taxes, new_row], ignore_index=True)

    #taxes paid, reset for next year
    withdraw_penalty = 0
    cap_gains = 0
    interest = 0
    income_from_retirement_accounts = 0


    # Add 'Rent' from df_income to net_income, generally depreciation will take care of this in terms of taxes
    rent = df_income.loc[df_income['name'] == 'Rent', 'income'].values[0]
    net_income += rent

    # Get paid
    df_accounts.loc[df_accounts['type'] == 'Cash', 'amount'] += net_income

    # Contribute to 529 and 401k
    if 'contribution_end_year' in df_accounts.columns:
        #529 contributions
        if year <= df_accounts.loc[df_accounts['type'] == '529', 'contribution_end_year'].values[0]:
            # Find the cash and 529 accounts
            cash_index = df_accounts[df_accounts['type'] == 'Cash'].index[0]
            account_529_index = df_accounts[df_accounts['type'] == '529'].index[0]

            # Get the contribution amount
            contribution_amount = df_accounts.loc[account_529_index, 'contribution']

            # Subtract the contribution amount from the cash account and add it to the 529 account
            df_accounts.loc[cash_index, 'amount'] -= contribution_amount
            df_accounts.loc[account_529_index, 'amount'] += contribution_amount

            # Increase the contribution amount by the inflation rate
            df_accounts.loc[account_529_index, 'contribution'] *= (1 + inflation_rate)
            #print('529 contribution:', year, contribution_amount)


    #401k contributions
    # Find the accounts
    if 'Tax-Deferred' in df_accounts['type'].values:
        tdt_index = df_accounts[df_accounts['type'] == 'Tax-Deferred'].index[0]
    else:
        print("No 'Tax-Deferred' account found in df_accounts. Please add into json with 0 amount")
        tdt_index = None

    # Subtract the contribution amount from the cash account and add it to the Tax-Deferred account
    df_accounts.loc[tdt_index, 'amount'] += tdt_contribution
    #cash is already subtracted from net_income because it comes out of tax exempt income

    # Increase the contribution amount by the inflation rate
    tdt_contribution_limit *= (1 + inflation_rate)



    # Pay the bills
    cash_index = df_accounts[df_accounts['type'] == 'Cash'].index[0]
    total_expenditure = 0

    for i in range(len(df_expenditure)):
        # Subtract the annual cost from the cash account for each expenditure except pre-tax expenses which haven't gotten to the final_year yet
        if df_expenditure.loc[i, 'name'] != 'pre-tax expenses' and year <= df_expenditure.loc[i, 'final_year'] and year >= df_expenditure.loc[i, 'start_year']:
            total_expenditure += df_expenditure.loc[i, 'annual_cost']
            new_row = pd.DataFrame({
                'name': [df_expenditure.loc[i, 'name']],
                'annual_cost': [df_expenditure.loc[i, 'annual_cost']],
                'year': [year]
            })
            df_expenditure_history = pd.concat([df_expenditure_history, new_row], ignore_index=True)

    df_accounts.loc[cash_index, 'amount'] -= total_expenditure
    #print('Total Expenditure:', total_expenditure)



    #Pay for college
    # Find the accounts
    account_529_index = df_accounts[df_accounts['type'] == '529'].index[0]
    cash_index = df_accounts[df_accounts['type'] == 'Cash'].index[0]

    # Iterate through each family member
    for _, member in df_family.iterrows():
        age = member['age']

        # Check if the age is between 18 and 21
        if 18 <= age <= 21:
            #print("College age:", age)
            #print(df_accounts.loc[account_529_index, 'amount'])
            # Subtract the cost of college from the 529 account
            if df_accounts.loc[account_529_index, 'amount'] >= cost_of_college:
                df_accounts.loc[account_529_index, 'amount'] -= cost_of_college
            else:
                # If the 529 account doesn't have enough funds, subtract the remaining cost from the cash account
                remaining_cost = cost_of_college - df_accounts.loc[account_529_index, 'amount']
                df_accounts.loc[account_529_index, 'amount'] = 0
                df_accounts.loc[cash_index, 'amount'] -= remaining_cost
            
            df_college_cost_history = pd.concat([df_college_cost_history, pd.DataFrame({'cost_of_college': [cost_of_college], 'year': [year]})], ignore_index=True)




    #If there isn't enough cash, then take money from Investment account, then from Tax-Exempt account, then finally from Tax-Deferred account
    if df_accounts.loc[cash_index, 'amount'] < 0:
        # Find the accounts
        account_investment_indices = df_accounts[df_accounts['type'] == 'Investment'].index
#        for i in range(len(account_investment_indices)):
#            print("i", account_investment_indices[i])
        account_tax_exempt_index = df_accounts[df_accounts['type'] == 'Tax-Exempt'].index[0]
        account_tax_deferred_index = df_accounts[df_accounts['type'] == 'Tax-Deferred'].index[0]

        shortage = 0

        # Take money from the investment account
        if df_accounts.loc[cash_index, 'amount'] < 0:
            shortage = abs(df_accounts.loc[cash_index, 'amount']) #how much are we short
            df_accounts.loc[cash_index, 'amount'] = 0 #set the cash account to 0

            total_investment_amount = 0
            for i in range(len(account_investment_indices)):
                total_investment_amount += df_accounts.loc[account_investment_indices[i], 'amount']

            if shortage >= total_investment_amount: #if there isn't enough in the investment account
                for i in range(len(account_investment_indices)):
                    cap_gains += df_accounts.loc[account_investment_indices[i], 'amount'] - cost_basis[i] #cap gains is then just the amount of the investment account minus the cost basis
                    cost_basis[i] = 0 #cost basis is now 0 cause investment account is zero 
                    df_accounts.loc[account_investment_indices[i], 'amount'] = 0 #empty the investment account
                
                shortage -= total_investment_amount #this is how much we still need

                if shortage > df_accounts.loc[account_tax_deferred_index, 'amount']: #if there isn't enough in the tax-deferred account either
                    df_accounts.loc[account_tax_deferred_index, 'amount'] = 0 #empty the tax-exempt account
                    income_from_retirement_accounts = df_accounts.loc[account_tax_deferred_index, 'amount'] #pay taxes on this

                    shortage -= df_accounts.loc[account_tax_deferred_index, 'amount'] #this is how much we still need
                    if df_family['age'].max() < 59.5: #if the oldest family member is younger than 59.5, then there is a 10% penalty
                        withdraw_penalty = df_accounts.loc[account_tax_deferred_index, 'amount'] * 0.1
                    
                    #account_tax_exempt_index
                    if shortage > df_accounts.loc[account_tax_exempt_index, 'amount']: #if there isn't enough in the tax-exempt account either
                        print("Not enough funds to cover the shortage. You are fucked.")
                        df_accounts.loc[account_tax_exempt_index, 'amount'] -= shortage
                    else:
                        if df_family['age'].max() < 59.5:
                            withdraw_penalty = shortage * 0.1
                        df_accounts.loc[account_tax_exempt_index, 'amount'] -= shortage

                else:
                    #if oldest family member is younger than 59.5, then there is a 10% penalty
                    if df_family['age'].max() < 59.5:
                        withdraw_penalty = shortage * 0.1
                    income_from_retirement_accounts = shortage #pay taxes
                    df_accounts.loc[account_tax_deferred_index, 'amount'] -= shortage

            else: #there is enough in the combined investment account
                for i in range(len(account_investment_indices)):
                    if shortage < df_accounts.loc[account_investment_indices[i], 'amount']: #if there is enough in this account
                        df_accounts.loc[account_investment_indices[i], 'amount'] -= shortage
                        cap_gains += shortage * (1 - cost_basis[i] / df_accounts.loc[account_investment_indices[i], 'amount'])
                        cost_basis[i] *= (1 - shortage / df_accounts.loc[account_investment_indices[i], 'amount'])
                        break
                    else:
                        cap_gains += df_accounts.loc[account_investment_indices[i], 'amount'] - cost_basis[i]
                        cost_basis[i] = 0
                        df_accounts.loc[account_investment_indices[i], 'amount'] = 0
                        shortage -= df_accounts.loc[account_investment_indices[i], 'amount']

                    
    #At the end of the year, sweep all cash over $100k into the 1st investment account
    #This is for the bozos who keep too much cash in their accounts
    if df_accounts.loc[cash_index, 'amount'] > 100000:
        account_investment_indices = df_accounts[df_accounts['type'] == 'Investment'].index
        df_accounts.loc[account_investment_indices[0], 'amount'] += df_accounts.loc[cash_index, 'amount'] - 100000
        df_accounts.loc[cash_index, 'amount'] = 100000
                

    #INFLATION ADJUSTMENTS FOR ALL VALUES
    # Update the accounts
    for i in range(len(df_accounts)):
        if df_accounts.loc[i, 'type'] == 'Cash':
            #pay interest tax
            interest = df_accounts.loc[i, 'amount'] * (df_accounts.loc[i, 'growth_rate']) #for taxes
        df_accounts.loc[i, 'amount'] = df_accounts.loc[i, 'amount'] * (1 + df_accounts.loc[i, 'growth_rate'])

    # Update the income
    for idx, row in df_income.iterrows():
        family_member_age = df_family.loc[df_family['name'] == row['family_member'], 'age'].values[0]
        if ((family_member_age >= row['start_age']) or pd.isnull(row['start_age'])) and ((family_member_age <= row['end_age']) or pd.isnull(row['end_age'])):
            df_income['income'] = df_income['income'].astype('float64')
            df_income.loc[idx, 'income'] = row['income'] * (1 + row['annual_income_growth'])

    # Update the expenditure
    for i in range(len(df_expenditure)):
        df_expenditure['annual_cost'] = df_expenditure['annual_cost'].astype('float64')
        df_expenditure.loc[i, 'annual_cost'] = df_expenditure.loc[i, 'annual_cost'] * (1 + df_expenditure.loc[i, 'inflation_rate'])
    
    # Age all family members
    for i in range(len(df_family)):
        # Update the current age of each family member
        df_family.loc[i, 'age'] += 1

    # inflate the cost of college
    cost_of_college *= (1 + inflation_rate)

    # Store the balance of each account for this year
    df_balance_history = pd.concat([df_balance_history, df_accounts[['name', 'amount']].assign(year=year)], ignore_index=True)

    # Update the year
    year += 1

# Get unique names
names = df_balance_history['name'].unique()

# Create a new figure
plt.figure(figsize=(10, 6))

# Plot the data
for name in names:
    df_name = df_balance_history[df_balance_history['name'] == name]
    plt.plot(df_name['year'], df_name['amount'], label=name)

# Draw vertical lines at retirement years
for year in retirement:
    plt.axvline(x=year, color='r', linestyle='--')
    plt.text(year, plt.gca().get_ylim()[1], 'Retirement', rotation=90, verticalalignment='top')

# Add gridlines
plt.grid(True)

# Add labels and title
plt.xlabel('Year')
plt.ylabel('Amount')
plt.title('Balance History Over Time')

# Set y-axis limit
plt.ylim(-1000000, 5000000) #If we have more than $5,000,000, then we don't have to show it.

# Add a legend
plt.legend()

plt.savefig(json_file + '_plot.png')

# Show the plot
plt.show()

# Set pandas display options
pd.set_option('display.float_format', lambda x: '%.2f' % x)
df_balance_history['amount'] = df_balance_history['amount'].apply(lambda x: '${:,.2f}'.format(x))

df_reformatted = df_balance_history.pivot(index='year', columns='name', values='amount')
#print(df_reformatted)
df_reformatted.to_csv(json_file + '_balance_history.csv')

df_college_cost_history_grouped = df_college_cost_history.groupby('year')['cost_of_college'].sum().reset_index()
df_college_cost_history_grouped.set_index('year', inplace=True)
#print(df_college_cost_history_grouped)

df_expenditure_history = df_expenditure_history.pivot(index='year', columns='name', values='annual_cost')
#print(df_expenditure_history)

# Merge the DataFrames
df_merged = df_expenditure_history.merge(df_college_cost_history_grouped, left_index=True, right_index=True, how='outer')

df_taxes.set_index('year', inplace=True)
df_merged = df_merged.merge(df_taxes, left_index=True, right_index=True, how='outer')

# Print the merged DataFrame
df_merged = df_merged.fillna(0).map(lambda x: '${:,.2f}'.format(x) if x != 0 else '$0.00')
#print(df_merged)
df_merged.to_csv(json_file + '_expense_history.csv')
