"""A week of desk traffic for the claims assistant.

Written the way an adjuster types into a file note - claimant named, claim number
pasted in, form usually half-remembered - and written BEFORE any of it was run,
so the mix is not steered toward questions I already knew would break. There are
no expected answers in this file on purpose. Labelling them here would have
turned the open coding in notes.md into a checking exercise.

Names, claim numbers, policy numbers, phones, emails and addresses are fictional
and are here so the redactor has real work to do on the way into the trace.
"""

TRAFFIC = [
    # --- water damage, HO-0304 -------------------------------------------------
    "Mrs. Eleanor Whitfield, CLM-2024-10021. Pipe burst behind the shower wall, she was away three weeks and found it on return. Does E-17 exclude it?",
    "CLM-2024-10022, insured Daniel Okoro. Leak ran about three weeks before anyone noticed. Is that E-17 or E-18?",
    "Under HO-0304 what counts as sudden and accidental?",
    "CLM-2024-10023. Washing machine hose let go while the family was at dinner, kitchen ceiling down. Covered?",
    "Does the water damage endorsement cover the cost of the failed pipe itself or just the resulting damage?",
    "Insured threw out the split section of pipe before we could look at it. Does that hurt him?",
    "CLM-2024-10024, Priya Raghunathan. Slow drip under the vanity, she says maybe a month. Which exclusion?",
    "River came up over the bank and into the basement. Is that E-15 or E-16?",
    "Does E-16 apply if the policy has the water backup endorsement on it?",
    "What does supply line mean in HO-0304?",
    "CLM-2024-10025. Toilet supply line failed at 2am, insured shut the main within the hour. Any issue with cover?",
    "Is overflow from a sump the same thing as sewer backup under the water damage form?",
    "Which HO-0304 edition are we on and when did it take effect?",
    "Adjuster question - E-17 exception, does the insured have to prove the 14 days or do we?",
    "CLM-2024-10026, Marcus Delacroix. Pinhole leak in copper, drywall soaked, unclear how long. What do I need to establish?",
    "Does HO-0304 change anything about Coverage C or is it Coverage A only?",
    "If this endorsement conflicts with the base HO-3 wording which one wins?",
    "CLM-2024-10027. Insured away for the winter, pipe let go in week two of the trip. Sudden and accidental?",
    "Does E-18 have any exception at all?",
    "Water came in under the patio door in heavy rain. Which code?",

    # --- water backup and sump, HO-0820 ---------------------------------------
    "CLM-2024-10031, Alina Sorescu. Sewer backed up and flooded the basement. What is the most we pay and what comes off for the deductible?",
    "Sump pump battery was never changed, pump died in the storm, basement took water. Does E-51 apply?",
    "CLM-2024-10032. Power was out about 14 hours, sump stopped, water came up. Does the E-51 exclusion still bite?",
    "Is the water backup deductible on top of the policy deductible or instead of it?",
    "What does related equipment cover under HO-0820?",
    "CLM-2024-10033, insured Grace Nwankwo. House had been empty since June, sump failed in September. Any coverage?",
    "How often does the insured have to test the sump pump?",
    "CLM-2024-10034. Loss is 14,000 dollars from a sewer backup, HO-0820 is attached. What do we pay?",
    "Does the water backup endorsement cover the sump pump itself when it burns out?",
    "Insured has no receipts for the battery replacement. Does that void the claim?",
    "CLM-2024-10035. Backup damaged carpet and drywall plus a stored piano. Is contents in or out?",
    "Vacancy under HO-0820 - is it 30 days or 60 days?",
    "Does HO-0820 override E-16 automatically or does it have to be endorsed on?",
    "CLM-2024-10036, Tomas Bergstrom. Two separate backups four days apart. One limit or two?",
    "What is the per loss event limit on the water backup form?",

    # --- rental dwelling, DP-0703 ---------------------------------------------
    "CLM-2024-10041. Tenant moved out in November, place stood empty with the heating off, pipes froze and split.",
    "Landlord never looked at the place after the last tenant left. Does that hurt the burst pipe claim?",
    "CLM-2024-10042, insured Rebecca Lindqvist. Rental empty 45 days between tenants but she drained the system. Covered?",
    "What temperature does the landlord have to keep the rental at over the winter?",
    "How many days does the landlord have to inspect after a tenancy ends?",
    "CLM-2024-10043. Dwelling fire policy, burst pipe, dwelling was tenant occupied throughout. Any exclusion in play?",
    "Does E-61 apply to a dwelling the owner lives in himself?",
    "CLM-2024-10044, Oluwaseun Adebayo. Empty 22 days, pipe burst, heat was on. Do we pay?",
    "Is E-62 subject to any exception?",
    "What is a tenant-occupied period under DP-0703?",
    "CLM-2024-10045. Landlord says he shut the water off but did not drain the lines. Does the E-61 exception still apply?",
    "Which policy line is DP-0703 written for?",
    "CLM-2024-10046, Hannah Vogt. Freeze loss in February, heat was set to 50 degrees. Covered or not?",
    "Does failing to inspect void the whole claim or just the exception?",

    # --- roof cosmetic damage, HO-0415 ----------------------------------------
    "CLM-2024-10051. Hail dented the metal roof but it still sheds water and there are no leaks. Does E-22 apply?",
    "Insured wants the whole roof replaced for hail dings. Anything in the file that lets us limit it?",
    "CLM-2024-10052, Sebastian Kowalczyk. Hail hit in June, water started coming in three weeks later. E-21?",
    "What counts as roof surfacing - does that include the flashing?",
    "How long do we have to inspect a hail roof claim?",
    "CLM-2024-10053. Insured already had the roof replaced before we got out there. Where does that leave us?",
    "Does the cosmetic damage exclusion apply to wind as well as hail?",
    "CLM-2024-10054, Maria Fernanda Ortiz. Asphalt shingles bruised by hail, underlayment intact. Pay or deny?",
    "Is there an exception to E-22 at all?",
    "What is cosmetic damage under HO-0415?",
    "CLM-2024-10055. Storm was in December 2023, endorsement effective January 2024. Does it apply?",
    "Can the insured put a tarp up before our inspection?",

    # --- home business, HO-0509 -----------------------------------------------
    "CLM-2024-10061, insured Yusuf Demirel. Makes candles at home, cleared about 8,000 dollars last year. A customer tripped in the driveway. Are we on cover for the liability?",
    "How much can we pay for work laptops that were taken to a client office and stolen there?",
    "CLM-2024-10062. Insured runs a day care for two children, no fee beyond costs, one child hurt. Is E-31 in play?",
    "What is the sublimit for business property kept at the house?",
    "CLM-2024-10063, Chidinma Eze. Started a home bakery in March, never told us, grease fire in October. Coverage?",
    "Does the home business endorsement affect Coverage A at all?",
    "What makes something a home business under HO-0509 - is there a dollar threshold?",
    "CLM-2024-10064. Insured is an accountant, did a neighbour's return for free, neighbour is now suing over it. Covered?",
    "Is the 2,500 dollar business property limit extra insurance or part of Coverage C?",
    "CLM-2024-10065, Arjun Balasubramanian. Home business grossed 4,200 dollars last year. Does the endorsement apply to him?",
    "How long does the insured have to notify us of a new home business?",
    "CLM-2024-10066. Day care with five children, one injured. Does the exception hold?",
    "Does E-32 have an exception for unpaid professional advice?",

    # --- ordinance or law, HO-0612 --------------------------------------------
    "CLM-2024-10071. Fire took half the house and the city now wants the undamaged wall rebuilt to current code. How much extra can we put up?",
    "Does E-41 stop us paying for the asbestos survey the council is insisting on?",
    "CLM-2024-10072, insured Frederik Lundgren. Coverage A is 400,000, ordinance costs are 120,000 of which 15,000 is asbestos. What is payable?",
    "Was the ordinance or law percentage 10 or 25 under this endorsement?",
    "CLM-2024-10073. Insured says the house is worth less now because of the new setback rule. Do we pay that?",
    "Does the ordinance endorsement pay demolition of the undamaged part?",
    "What is an undamaged portion under HO-0612?",
    "CLM-2024-10074, Beatriz Camargo. Loss was in February 2024, endorsement effective March 2024. Does the increase apply?",
    "Do we pay to upgrade beyond the minimum the code requires if the contractor recommends it?",
    "CLM-2024-10075. Lead paint removal ordered as part of the rebuild. Covered under the ordinance form?",
    "Is the 25 percent on top of Coverage A or inside it?",

    # --- cross form and edition questions -------------------------------------
    "CLM-2024-10081. Policy has both HO-0304 and HO-0820 on it, sewer backed up. Which one controls?",
    "Does E-17 mean the same thing under the dwelling fire form as it does under the homeowners form?",
    "CLM-2024-10082, Nadia Al-Rashid. Tenant occupied rental, sewer backup. Is HO-0820 any help?",
    "What does E-17 say under HO-0304 edition 10-22?",
    "CLM-2024-10083. Homeowners policy, burst pipe in a rental unit the insured owns elsewhere. Which form applies?",
    "Which of our endorsements have a vacancy or unoccupancy condition in them?",
    "CLM-2024-10084. Insured has HO-0415 ed. 05-23 per the dec page. What does E-21 say in that edition?",
    "List every exclusion code that has no exception.",
    "CLM-2024-10085, Grigore Popescu. Home business plus a burst supply line damaging his stock. How do the two endorsements interact?",
    "Does any of our water wording cover mould that grew after the leak?",

    # --- vague, short, or badly typed ------------------------------------------
    "e17?",
    "CLM-2024-10091 - coverage?",
    "is this covered",
    "water damage exclusions please",
    "What is the deductible?",
    "sump pump",
    "Can you summarise the endorsements on this policy",
    "CLM-2024-10092, Ingrid Halvorsen. what do i tell her",
    "denial letter wording for cosmetic hail",
    "quick one - vacancy limits across all forms?",

    # --- genuinely outside the corpus ------------------------------------------
    "What is the reserve-setting threshold for claim CLM-2024-88431?",
    "How many days do I have to acknowledge a first notice of loss in this state?",
    "CLM-2024-10101. What is our subrogation deadline against the plumber?",
    "Who is the adjuster assigned to CLM-2024-10102?",
    "What does the base HO-3 ed. 10-22 say about Coverage B limits?",
    "Is bad faith exposure a risk if we deny this one?",
    "Give me the phone number for the SIU referral desk.",
    "What is our current authority limit for settling without a supervisor?",
    "How do I file this in Guidewire?",
    "Does the state require a certified letter for a partial denial?",
    "What is the statute of limitations on a property claim here?",
    "CLM-2024-10103, Lucas Moreau. Auto claim, rear ended at a light. Whose fault?",
]

# The ten we bring to the monthly review. Not random, and that is the point -
# they are the questions that have always demoed well.
DEMO_SET = [
    "Sewer backed up and flooded the basement. What is the most we pay and what comes off for the deductible?",
    "Does E-41 stop us paying for the asbestos survey the council is insisting on?",
    "Hail dented the metal roof but it still sheds water and there are no leaks. Does E-22 apply?",
    "How much can we pay for work laptops that were taken to a client office and stolen there?",
    "Tenant moved out in November, place stood empty with the heating off, pipes froze and split.",
    "What is the reserve-setting threshold for claim CLM-2024-88431?",
    "Under HO-0304 what counts as sudden and accidental?",
    "Sump pump battery was never changed, pump died in the storm, basement took water. Does E-51 apply?",
    "Landlord never looked at the place after the last tenant left. Does that hurt the burst pipe claim?",
    "What is the per loss event limit on the water backup form?",
]
