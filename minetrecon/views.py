import io
import pandas as pd
from django.http import HttpResponse
from .models import Accounts  # Assuming this is the model for account mapping
from openpyxl import load_workbook
from .forms import MultiFileUploadForm
from django.shortcuts import render

def upload_files(request):
    if request.method == 'POST':
        form = MultiFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file1 = request.FILES['file1']  # Bank Statement Workbook
            file2 = request.FILES['file2']  # General Ledger
            

            try:
                # Step 1: Extract GLID from the General Ledger
                df2 = pd.read_excel(file2)
                
                processed_df2 = df2.copy()
                if len(df2) >= 5:
                    account_number_gl = df2.iloc[4, 0]  # Extract GLID from row 6, column A
                else:
                    return HttpResponse("No account GLID found in the General Ledger.")

                # Step 2: Load the Bank Statement Workbook and search for the bank account number
                wb = load_workbook(file1)
                matched_sheet = None
                account_number_bank = None

                for sheet in wb.sheetnames:
                    ws = wb[sheet]
                    cell_value = ws['B3'].value  # Replace 'B6' with the actual location of the bank account
                    if cell_value:
                        account_number_bank = cell_value
                        # Step 3: Check if GLID and account number are mapped in the database
                        mapping = Accounts.objects.filter(glaccount_number=account_number_gl, bankaccount_number=account_number_bank).first()

                        if mapping:
                            matched_sheet = sheet  # Keep track of the matching sheet
                            break  # Exit after finding the match

                if not matched_sheet:
                    return HttpResponse(f"No sheet found in the Bank Statement with account number {account_number_bank}.")
                
                # Read matched sheet into a DataFrame
                sheet = pd.read_excel(file1, sheet_name=matched_sheet)
                
                processed_df1 = sheet.copy()  # Copy for manipulation bank statement data

                # Extract relevant columns and filter out empty rows
                bank_debits_filtered = sheet.iloc[6:, [0, 1, 3]].dropna().reset_index(drop=True)
                bank_credits_filtered = sheet.iloc[6:, [0, 1, 4]].dropna().reset_index(drop=True)

                bank_debits_filtered.columns = ['Date', 'Transaction details', 'Debit amount']
                bank_credits_filtered.columns = ['Date', 'Transaction details', 'Credit amount']

                # Step 4: Process the General Ledger data
                gl_data = df2.iloc[5:, [1, 2, 9]].copy()
                gl_data.columns = ['Date', 'Narrative', 'Amount']
                gl_data['Amount'] = pd.to_numeric(gl_data['Amount'], errors='coerce')

                gl_debits = gl_data[gl_data['Amount'] > 0].copy()
                gl_credits = gl_data[gl_data['Amount'] < 0].copy()
                gl_credits['Amount'] = gl_credits['Amount'].abs()

                 # Rename 'Amount' to 'Debit amount' or 'Credit amount'
                gl_debits.rename(columns={'Amount': 'Debit amount'}, inplace=True)
                gl_credits.rename(columns={'Amount': 'Credit amount'}, inplace=True)

            # Add additional columns with default values
                 
                for df in [bank_debits_filtered, bank_credits_filtered, gl_debits, gl_credits]:
                    
                    df['Is Reconciled']='' 
                    df['Reconciliation Method']=''  
                    df['Reconciliation Reference'] = ''
                    df['Has duplicate'] = ''



               

            # Function to mark duplicates
                def mark_duplicates(df, amount_column):
                    duplicates = df[amount_column].duplicated(keep=False)
                    df['Has duplicate'] = duplicates.apply(lambda x: 'TRUE' if x else 'FALSE')

            # Mark duplicates for Bank Debits and Bank Credits
                mark_duplicates(bank_debits_filtered, 'Debit amount')
                mark_duplicates(bank_credits_filtered, 'Credit amount')

            # Mark duplicates for GL Debits and GL Credits
                mark_duplicates(gl_debits, 'Debit amount')
                mark_duplicates(gl_credits, 'Credit amount')

                bank_charges = bank_debits_filtered[
                    bank_debits_filtered['Transaction details'].str.contains(
                        'Transaction Charge|Excise Duty|Ledger fee', na=False
                    )
                ].copy()

                bank_charges['Debit amount'] = bank_charges['Debit amount']
                total_bank_charges_debit = bank_charges['Debit amount'].sum()

                
                
                # Step 2: Remove 'Is Reconciled' and 'Reconciliation Method' columns from bank charges
                bank_charges.drop(columns=['Is Reconciled', 'Reconciliation Method'], inplace=True)

                bank_debits_filtered['Reference No'] = ''
                bank_credits_filtered['Reference No'] = ''

                for bank_idx, bank_row in bank_debits_filtered.iterrows():
                    transaction_detail = bank_row['Transaction details']
                    reference_found = False

                    for sheet_idx in range(len(sheet)):
        # Iterate through the sheet to find the matching 'Transaction details'
                        if sheet.iloc[sheet_idx, 1] == transaction_detail:  # Assuming 'Transaction details' are in column 1 (index 1)
            # Transfer the value in the cell below the transaction detail to 'Reference No'
                            if sheet_idx + 1 < len(sheet):
                                bank_debits_filtered.at[bank_idx, 'Reference No'] = sheet.iloc[sheet_idx + 1, 1]  # Cell below
                            else:
                                bank_debits_filtered.at[bank_idx, 'Reference No'] = 'N/A'  # No cell below
                            reference_found = True
                            break  # Exit loop once found
                    if not reference_found:
                        bank_debits_filtered.at[bank_idx, 'Reference No'] = 'N/A'  # If no matching transaction detail found

                for bank_idx, bank_row in bank_credits_filtered.iterrows():
                    transaction_detail = bank_row['Transaction details']
                    reference_found = False
                    for sheet_idx in range(len(sheet)):
        # Iterate through the sheet to find the matching 'Transaction details'
                        if sheet.iloc[sheet_idx, 1] == transaction_detail:  # Assuming 'Transaction details' are in column 1 (index 1)
                            if sheet_idx + 1 < len(sheet):
                                bank_credits_filtered.at[bank_idx, 'Reference No'] = sheet.iloc[sheet_idx + 1, 1]  # Cell below
                            else:
                                bank_credits_filtered.at[bank_idx, 'Reference No'] = 'N/A'  # No cell below
                            reference_found = True
                            break  # Exit loop once found
                    if not reference_found:
                        bank_credits_filtered.at[bank_idx, 'Reference No'] = 'N/A'  # If no matching transaction detail found


                 
                    
            
            #for col in ['']:
                #bank_charges[col] = ''

            # Compare Debit amount in Bank Debits with Credit amount in GL Credits
                for bank_idx, bank_row in bank_debits_filtered.iterrows():
                    reconciled = False
                    for gl_idx, gl_row in gl_credits.iterrows():
                    # Check if both Debit amount and Credit amount are the same
                        if bank_row['Debit amount'] == gl_row['Credit amount']:
                        # Mark as reconciled with "BS Debit and GL Credit"
                            bank_debits_filtered.at[bank_idx, 'Is Reconciled'] = 'TRUE'
                            bank_debits_filtered.at[bank_idx, 'Reconciliation Method'] = 'BS Debit and GL Credit'
                            gl_credits.at[gl_idx, 'Is Reconciled'] = 'TRUE'
                            gl_credits.at[gl_idx, 'Reconciliation Method'] = 'BS Debit and GL Credit'
                            reconciled = True

                        if any(keyword in bank_row['Transaction details'] for keyword in ["Transaction Charge", "Excise Duty", "Ledger fee"]):
            # Only update if the condition hasn't been set before
                            if bank_debits_filtered.at[bank_idx, 'Is Reconciled'] != 'TRUE' or \
                                bank_debits_filtered.at[bank_idx, 'Reconciliation Method'] != 'BS Debit and GL Credit':
                                bank_debits_filtered.at[bank_idx, 'Is Reconciled'] = 'TRUE'
                                bank_debits_filtered.at[bank_idx, 'Reconciliation Method'] = 'NCBA Bank Charges'
                                reconciled = True
                    if not reconciled:
                        bank_debits_filtered.at[bank_idx, 'Is Reconciled'] = 'FALSE'
                        bank_debits_filtered.at[bank_idx, 'Reconciliation Method'] = 'N/A'
                    

            

                for bank_idx, bank_row in bank_credits_filtered.iterrows():
                    reconciled = False
                    for gl_idx, gl_row in gl_debits.iterrows():
                    # Check if both Debit amount and Credit amount are the same
                        if bank_row['Credit amount'] == gl_row['Debit amount']:
                        # Mark as reconciled with "BS Credit and GL Debit"
                            bank_credits_filtered.at[bank_idx, 'Is Reconciled'] = 'TRUE'
                            bank_credits_filtered.at[bank_idx, 'Reconciliation Method'] = 'BS Credit and GL Debit'
                            gl_debits.at[gl_idx, 'Is Reconciled'] = 'TRUE'
                            gl_debits.at[gl_idx, 'Reconciliation Method'] = 'BS Credit and GL Debit'
                            reconciled = True
                    if not reconciled:
                        bank_credits_filtered.at[bank_idx, 'Is Reconciled'] = 'FALSE'
                        bank_credits_filtered.at[bank_idx, 'Reconciliation Method'] = 'N/A'
                    
                for df in [gl_debits, gl_credits]:
                    df['Is Reconciled'] = df['Is Reconciled'].replace('', 'FALSE')
                    df['Reconciliation Method'] = df['Reconciliation Method'].replace('', 'N/A')
                    
                    
                for df in [bank_debits_filtered, bank_credits_filtered, gl_debits, gl_credits]:
                    method_col = 'Reconciliation Method'
                    ref_col = 'Reconciliation Reference'
                    if 'Debit amount' in df.columns:
                        amount_col = 'Debit amount'
                    else:
                        amount_col = 'Credit amount'

                    for idx in df.index:
                        if df.at[idx, method_col] in ['BS Debit and GL Credit', 'BS Credit and GL Debit']:
                            df.at[idx, ref_col] = df.at[idx, amount_col]
                

                # Sum the 'Debit amount' where 'Is Reconciled' is 'FALSE' for Bank Debits and GL Debits
                unreconciled_bank_debits_sum = bank_debits_filtered[bank_debits_filtered['Is Reconciled'] == 'FALSE']['Debit amount'].sum()
                unreconciled_gl_debits_sum = gl_debits[gl_debits['Is Reconciled'] == 'FALSE']['Debit amount'].sum()

                unreconciled_bank_credits_sum = bank_credits_filtered[bank_credits_filtered['Is Reconciled'] == 'FALSE']['Credit amount'].sum()
                unreconciled_gl_credits_sum = gl_credits[gl_credits['Is Reconciled'] == 'FALSE']['Credit amount'].sum()
            
            # Count 'TRUE' and 'FALSE' values in the 'Is Reconciled' column for Bank Debits and GL Debits
                true_bank_debits_count = bank_debits_filtered['Is Reconciled'].value_counts().get('TRUE', 0)
                false_bank_debits_count = bank_debits_filtered['Is Reconciled'].value_counts().get('FALSE', 0)

                true_bank_credits_count = bank_credits_filtered['Is Reconciled'].value_counts().get('TRUE', 0)
                false_bank_credits_count = bank_credits_filtered['Is Reconciled'].value_counts().get('FALSE', 0)

                true_gl_debits_count = gl_debits['Is Reconciled'].value_counts().get('TRUE', 0)
                false_gl_debits_count = gl_debits['Is Reconciled'].value_counts().get('FALSE', 0)

                true_gl_credits_count = gl_credits['Is Reconciled'].value_counts().get('TRUE', 0)
                false_gl_credits_count = gl_credits['Is Reconciled'].value_counts().get('FALSE', 0)


                # Step 7: Output the results for download
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:

                    
                    processed_df1.to_excel(writer, index=False, sheet_name='Bank Statement')
                    processed_df2.to_excel(writer, index=False, sheet_name='General Ledger')
                    bank_debits_filtered.to_excel(writer, sheet_name='Bank Debits', index=False)
                    bank_credits_filtered.to_excel(writer, sheet_name='Bank Credits', index=False)
                    gl_debits.to_excel(writer, sheet_name='GL Debits', index=False)
                    gl_credits.to_excel(writer, sheet_name='GL Credits', index=False)
                    bank_charges.to_excel(writer, index=False, sheet_name='Bank Charges debited')

                    

                    wb = writer.book
                    
                    
                    bank_debits_sheet = wb['Bank Debits']
                    bank_credits_sheet = wb['Bank Credits']
                    gl_debits_sheet = wb['GL Debits']
                    gl_credits_sheet = wb['GL Credits']
                    bank_charges_sheet = wb['Bank Charges debited']

                    bank_debits_row_count = len(bank_debits_filtered) + 3
                    bank_debits_sheet.cell(row=bank_debits_row_count, column=6, value='Sum of unreconciled Debit amounts:')
                    bank_debits_sheet.cell(row=bank_debits_row_count + 1, column=6, value=unreconciled_bank_debits_sum)

                    # Similar process for Bank Credits
                    bank_credits_row_count = len(bank_credits_filtered) + 3
                    bank_credits_sheet.cell(row=bank_credits_row_count, column=6, value='Sum of unreconciled Credit amounts:')
                    bank_credits_sheet.cell(row=bank_credits_row_count + 1, column=6, value=unreconciled_bank_credits_sum)

    # Write the sum 3 rows below for GL Debits
                    gl_debits_row_count = len(gl_debits) + 3
                    gl_debits_sheet.cell(row=gl_debits_row_count, column=6, value='Unreconciled Debit amounts:')
                    gl_debits_sheet.cell(row=gl_debits_row_count + 1, column=6, value=unreconciled_gl_debits_sum)

    # Similar process for GL Credits
                    gl_credits_row_count = len(gl_credits) + 3
                    gl_credits_sheet.cell(row=gl_credits_row_count, column=6, value='Unreconciled Credit amounts:')
                    gl_credits_sheet.cell(row=gl_credits_row_count + 1, column=6, value=unreconciled_gl_credits_sum)

    # Write the total reconciled and unreconciled counts for Bank Debits
                    bank_debits_sheet.cell(row=bank_debits_row_count + 3, column=6, value='Total reconciled Debit entries:')
                    bank_debits_sheet.cell(row=bank_debits_row_count + 4, column=6, value=true_bank_debits_count)

                    bank_debits_sheet.cell(row=bank_debits_row_count + 6, column=6, value='Total unreconciled Debit entries:')
                    bank_debits_sheet.cell(row=bank_debits_row_count + 7, column=6, value=false_bank_debits_count)

    # Similar process for Bank Credits
                    bank_credits_sheet.cell(row=bank_credits_row_count + 3, column=6, value='Total reconciled Credit entries:')
                    bank_credits_sheet.cell(row=bank_credits_row_count + 4, column=6, value=true_bank_credits_count)

                    bank_credits_sheet.cell(row=bank_credits_row_count + 6, column=6, value='Total unreconciled Credit entries:')
                    bank_credits_sheet.cell(row=bank_credits_row_count + 7, column=6, value=false_bank_credits_count)

    # Similar process for GL Debits and Credits
                    gl_debits_sheet.cell(row=gl_debits_row_count + 3, column=6, value='Total reconciled GL Debit entries:')
                    gl_debits_sheet.cell(row=gl_debits_row_count + 4, column=6, value=true_gl_debits_count)

                    gl_debits_sheet.cell(row=gl_debits_row_count + 6, column=6, value='Total unreconciled GL Debit entries:')
                    gl_debits_sheet.cell(row=gl_debits_row_count + 7, column=6, value=false_gl_debits_count)

                    gl_credits_sheet.cell(row=gl_credits_row_count + 3, column=6, value='Total reconciled GL Credit entries:')
                    gl_credits_sheet.cell(row=gl_credits_row_count + 4, column=6, value=true_gl_credits_count)

                    gl_credits_sheet.cell(row=gl_credits_row_count + 6, column=6, value='Total unreconciled GL Credit entries:')
                    gl_credits_sheet.cell(row=gl_credits_row_count + 7, column=6, value=false_gl_credits_count)

                




                # Create recoonciliation summary sheet
                

                def calculate_percentage(true_count, false_count):
                        total_count = true_count + false_count
                        if total_count > 0:
                            percentage = (true_count / total_count) * 100
                        else:
                            percentage = 0
                        return percentage
                
                # Calculate percentages for each sheet
                bank_debits_percentage = calculate_percentage(true_bank_debits_count, false_bank_debits_count)
                bank_credits_percentage = calculate_percentage(true_bank_credits_count, false_bank_credits_count)
                gl_debits_percentage = calculate_percentage(true_gl_debits_count, false_gl_debits_count)
                gl_credits_percentage = calculate_percentage(true_gl_credits_count, false_gl_credits_count)


                # Write percentage reconciled entries to 'Reconciliation Summary' sheet
                output.seek(0)  # Reset the pointer to the start of the BytesIO stream
                
                wb = load_workbook(output)

                summary_sheet = wb.create_sheet(title='Reconciliation Summary')
                  # Ensure the sheet is visible
                summary_sheet.cell(row=1, column=1, value='Sheet Name')
                summary_sheet.cell(row=1, column=2, value='Reconciled Percentage')

                summary_sheet.cell(row=2, column=1, value='Bank Debits')
                summary_sheet.cell(row=2, column=2, value=f'{bank_debits_percentage:.2f}%')

                summary_sheet.cell(row=3, column=1, value='Bank Credits')
                summary_sheet.cell(row=3, column=2, value=f'{bank_credits_percentage:.2f}%')

                summary_sheet.cell(row=4, column=1, value='GL Debits')
                summary_sheet.cell(row=4, column=2, value=f'{gl_debits_percentage:.2f}%')

                summary_sheet.cell(row=5, column=1, value='GL Credits')
                summary_sheet.cell(row=5, column=2, value=f'{gl_credits_percentage:.2f}%')

                summary_sheet.sheet_state = 'visible'  # Ensure the sheet is visible

# Ensure you handle the case where there are no bank charges

# Summary sheet in general
# Writing unreconciled totals from Bank Debits, Bank Credits, GL Debits, GL Credits into Summary Sheet
# This code needs to be inserted within the `with pd.ExcelWriter` block after writing the individual sheets

# Write unreconciled debit and credit totals into the summary sheet
                
                  # Create Summary Sheet
                summary_sheet1 = wb.create_sheet(title='Summary')
                summary_sheet1.sheet_state = 'visible'  # Ensure the sheet is visible
                summary_sheet1.cell(row=3, column=2, value="BANK RECONCILIATION STATEMENT")
                summary_sheet1.cell(row=5, column=2, value="BANK NAME")
                summary_sheet1.cell(row=6, column=2, value="DIVISION NAME")
                summary_sheet1.cell(row=7, column=2, value="ACCOUNT NAME")
                summary_sheet1.cell(row=8, column=2, value="Position is at:")
                summary_sheet1.cell(row=10, column=2, value="BALANCE AS PER BANK STATEMENT")
                summary_sheet1.cell(row=10, column=7, value="")  # G10

# Add Section
                summary_sheet1.cell(row=12, column=2, value="Add:")
                summary_sheet1.cell(row=13, column=3, value="Debits in Bank not in GL")
                summary_sheet1.cell(row=14, column=3, value="Debits in GL not in Bank")
                summary_sheet1.cell(row=15, column=3, value="Bank Charges")
                summary_sheet1.cell(row=16, column=3, value="Bounced Customer Cheques")
                summary_sheet1.cell(row=17, column=3, value="Petty Difference")
                summary_sheet1.cell(row=18, column=3, value="Withholding tax")

# Use the previously calculated unreconciled sums from Bank Debits, Bank Credits, GL Debits, GL Credits
                summary_sheet1.cell(row=13, column=5, value=unreconciled_bank_debits_sum)  # Unreconciled debits from bank
                summary_sheet1.cell(row=14, column=5, value=unreconciled_gl_debits_sum)  # Unreconciled debits from GL
                summary_sheet1.cell(row=15, column=5, value=total_bank_charges_debit)  # Placeholder for Bank Charges
                summary_sheet1.cell(row=16, column=5, value="-")  # Placeholder for bounced cheques
                summary_sheet1.cell(row=17, column=5, value="-")  # Placeholder for petty differences
                summary_sheet1.cell(row=18, column=5, value="-")  # Placeholder for withholding tax
                summary_sheet1.cell(row=19, column=6, value="=SUM(E13:E18)")  # Total sum of unreconciled debits

# Less Section
                summary_sheet1.cell(row=20, column=2, value="Less:")
                summary_sheet1.cell(row=20, column=3, value="Credits in Bank not in GL")
                summary_sheet1.cell(row=21, column=3, value="Credits in GL not in Bank")
                summary_sheet1.cell(row=22, column=3, value="Interest Income")
                summary_sheet1.cell(row=23, column=3, value="Unrepresented Cheques")
                summary_sheet1.cell(row=24, column=3, value="Withholding Tax")

                summary_sheet1.cell(row=20, column=5, value=unreconciled_bank_credits_sum)  # Unreconciled credits from bank
                summary_sheet1.cell(row=21, column=5, value=unreconciled_gl_credits_sum)  # Unreconciled credits from GL
                summary_sheet1.cell(row=22, column=5, value="-")  # Placeholder for interest income
                summary_sheet1.cell(row=23, column=5, value="-")  # Placeholder for unrepresented cheques
                summary_sheet1.cell(row=24, column=5, value="-")  # Placeholder for withholding tax
                summary_sheet1.cell(row=25, column=6, value="=SUM(E20:E24)")  # Total sum of unreconciled credits

# Footer Section
                summary_sheet1.cell(row=28, column=4, value="Computed Balance")
                summary_sheet1.cell(row=28, column=7, value="=G10+F19-F25")  # Formula for computed balance

                summary_sheet1.cell(row=30, column=2, value="Balance as per Company books")
                summary_sheet1.cell(row=30, column=7, value="")  # Placeholder for balance as per company records

                summary_sheet1.cell(row=33, column=4, value="Reconciling Difference")
                summary_sheet1.cell(row=33, column=7, value="=G28-G30")  # Difference between computed and company balance

# Footer with preparer and reviewer
                summary_sheet1.cell(row=37, column=2, value="Prepared by:")
                summary_sheet1.cell(row=39, column=2, value="Reviewed by:")

                summary_sheet1.cell(row=37, column=4, value="Signature:")
                summary_sheet1.cell(row=39, column=4, value="Signature:")

                summary_sheet1.cell(row=37, column=6, value="Date:")
                summary_sheet1.cell(row=39, column=6, value="Date:")
                output = io.BytesIO()  # Reset the BytesIO object
                wb.save(output)
                #wb.save('reconciled_data.xlsx')
                


                #writer.sheets['Bank Charges debited'] = writer.book.add_worksheet('Bank Charges debited')
                
                


            # Set the cursor position to the beginning of the stream
                output.seek(0)
            #request.session['processed_file'] = output.getvalue()

            # Send a response indicating success
            #return render(request, 'index.html', {
                #'form': form,
                #'download_ready': True
            #})

            # Send the file to the user for download
        
                    
                response= HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = 'attachment; filename=reconciled_data.xlsx'
                return response

                
            except Exception as e:
                return HttpResponse(f"An error occurred: {str(e)}")    
        
        
            
    else:
        form = MultiFileUploadForm()
    return render(request, 'index.html', {'form': form})
