import pandas as pd

df = pd.read_csv('data/axa_travel_insurance.csv')
df['Claim_Target'] = df['Claim'].str.strip().str.upper() == 'YES'

print("--- Overall Singapore Claim Rate ---")
sg_df = df[df['Destination'] == 'SINGAPORE']
print(f"Singapore overall claim rate: {sg_df['Claim_Target'].mean():.2%} (N={len(sg_df)})")

print("\n--- Singapore Claim Rate by Agency ---")
sg_agency = sg_df.groupby('Agency')['Claim_Target'].agg(['count', 'mean']).sort_values('count', ascending=False)
print(sg_agency[sg_agency['count'] > 50])

print("\n--- Non-Singapore Claim Rate by Agency (for comparison) ---")
non_sg_df = df[df['Destination'] != 'SINGAPORE']
non_sg_agency = non_sg_df.groupby('Agency')['Claim_Target'].agg(['count', 'mean']).sort_values('count', ascending=False)
print(non_sg_agency.loc[sg_agency[sg_agency['count'] > 50].index, :])

print("\n--- Top Agency (C2B) overall Claim Rate by Destination ---")
c2b_df = df[df['Agency'] == 'C2B']
c2b_dest = c2b_df.groupby('Destination')['Claim_Target'].agg(['count', 'mean']).sort_values('count', ascending=False)
print(c2b_dest.head(5))

