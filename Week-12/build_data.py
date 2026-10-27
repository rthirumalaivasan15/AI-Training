"""Build the capstone's data: claims, policy admin records, and the eval cases with
their reference decisions - all from this one file, so every record and every
expected answer can be read in one place.

    python build_data.py

- claims_system/claims.json   the claims platform: claim facts and adjuster notes
                              (notes carry names, addresses and injuries on purpose -
                              the PII line has real work to do)
- policy_admin/policies.json  policy terms: in-force dates, forms WITH editions per
                              term, deductible, per-form deductibles, sub-limits, limits
- evals/cases.jsonl           25 cases, each with the decision the wording gives,
                              written from the wording before any integrated run

The 10 claims from Weeks 7-9 are carried over with their Week 7 expected decisions;
15 new claims cover what the capstone brief turns on: loss dates either side of the
2025 HO-0304 rewrite, policies not in force on the loss date, the three limit numbers,
and wording that is not on file. Assessments, never "covered":
    EXCLUSION_APPEARS_TO_APPLY | NO_EXCLUSION_TRIGGERED | FACTS_NEEDED |
    POLICY_NOT_IN_FORCE | WORDING_NOT_ON_FILE
"""
import os
import json

W9_CLAIMS = os.path.join("..", "Week-9", "claims_system", "claims.json")
W7_EXPECTED = os.path.join("..", "Week-7", "expected.json")

SUB = {"HO-0820": {"water_backup_per_event": 10000},
       "HO-0509": {"business_property_on_premises": 2500, "business_property_away": 500}}
FORM_DED = {"HO-0820": {"water_backup": 1000}}


def term(start, end, forms, deductible, cov_a, extra_sub=None):
    sub, fded = {}, {}
    for f in forms:
        sub.update(SUB.get(f.split()[0], {}))
        fded.update(FORM_DED.get(f.split()[0], {}))
        if f.startswith("HO-0612"):
            sub["ordinance_or_law"] = cov_a * 25 // 100
        if f == "HO-0304 ed. 01-25":
            sub["storm_ingress_per_storm"] = 5000
    sub.update(extra_sub or {})
    return {"term_start": start, "term_end": end, "forms": forms, "deductible": deductible,
            "form_deductibles": fded, "sub_limits": sub,
            "limits": {"coverage_a_dwelling": cov_a, "coverage_c_personal_property": cov_a // 2}}


def claim(cid, policy, dol, first_notice, amount, notes):
    return {"claim_id": cid, "status": "open", "policy_number": policy, "date_of_loss": dol,
            "first_notice": first_notice, "claimed_amount": amount, "adjuster_notes": notes}


def expect(assessment, mode, why, cite=(), in_force="IN_FORCE", editions=None,
           deductible=None, sub_limit=None, policy_limit=None):
    return {"mode": mode, "assessment_in": assessment if isinstance(assessment, list) else [assessment],
            "must_cite_any": list(cite), "in_force": in_force, "editions": editions or {},
            "deductible": deductible, "sub_limit": sub_limit, "policy_limit": policy_limit, "why": why}


def week7():
    with open(W9_CLAIMS, encoding="utf-8") as f:
        old = json.load(f)
    with open(W7_EXPECTED, encoding="utf-8") as f:
        exp = json.load(f)["claims"]
    claims, policies, cases = [], {}, []
    for c in old:
        e = exp[c["claim_id"]]
        claims.append(claim(c["claim_id"], c["policy_number"], c["date_of_loss"], c["first_notice"],
                            c["claimed_amount"], c["adjuster_notes"]))
        line = c["policy_line"]
        policies[c["policy_number"]] = {
            "policy_number": c["policy_number"], "product": "household", "policy_line": line,
            "terms": [term("2024-01-01", "2024-12-31", c["forms_attached"], c["excess"], c["coverage_a_limit"])]}
        pos = e["coverage_position"]
        assessment = {"DENIED": "EXCLUSION_APPEARS_TO_APPLY", "COVERED": "NO_EXCLUSION_TRIGGERED",
                      "UNDETERMINED": "FACTS_NEEDED"}[pos]
        forms = c["forms_attached"]
        sub = {"CLM-2024-10004": 10000, "CLM-2024-10005": 10000, "CLM-2024-10009": 2500}.get(c["claim_id"])
        ded = 1000 if c["claim_id"] in ("CLM-2024-10004", "CLM-2024-10005") else c["excess"]
        limit = c["coverage_a_limit"] // 2 if c["claim_id"] == "CLM-2024-10009" else c["coverage_a_limit"]
        editions = {f.split()[0]: f.split("ed. ")[1] for f in forms}
        cases.append({"id": c["claim_id"], "claim_id": c["claim_id"], **expect(
            assessment, e["class"], "Week 7 reference decision: %s. %s" % (pos, e["why"]),
            cite=e["must_cite"], editions=editions, deductible=ded, sub_limit=sub, policy_limit=limit)})
    return claims, policies, cases


NEW = [
    # --- loss dates either side of the 2025 HO-0304 rewrite (bonus: the date filter) ----------
    ("CLM-2024-30001", "HP-460101", "2024-08-11", "Water in the family room after a storm.", 4800,
     ["2024-08-12 Spoke to insured Mrs. Joan Pell at 14 Larch Road. A thunderstorm on 11 August; the weather "
      "station recorded 62 mm of rain in 24 hours. Water pooled on the patio and ran in under the patio door "
      "into the family room.", "2024-08-14 Carpets and skirting boards soaked. Estimate 4,800."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 320000),
      term("2025-01-01", "2025-12-31", ["HO-0304 ed. 01-25"], 1000, 320000)],
     expect("EXCLUSION_APPEARS_TO_APPLY", "version-straddle",
            "Loss 2024-08-11: HO-0304 ed. 03-24 is in force. Surface water is excluded under E-15 with no "
            "exception. The 2025 Storm Ingress Allowance did not exist yet.",
            cite=["E-15"], editions={"HO-0304": "03-24"}, deductible=1000, policy_limit=320000)),
    ("CLM-2024-30002", "HP-460102", "2024-12-31", "Rain came in through the front door.", 6200,
     ["2024-12-31 Storm overnight, 71 mm of rain in 24 hours at the nearest station. Insured Mr. Felix Grant "
      "says water came in under the front door and across the hall and lounge floors.",
      "2025-01-02 Laminate lifted throughout. Estimate 6,200."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 290000),
      term("2025-01-01", "2025-12-31", ["HO-0304 ed. 01-25"], 1000, 290000)],
     expect("EXCLUSION_APPEARS_TO_APPLY", "version-straddle",
            "Loss 2024-12-31, the last day before the 2025 edition: ed. 03-24 is in force, E-15 excludes "
            "surface water absolutely.", cite=["E-15"], editions={"HO-0304": "03-24"}, deductible=1000,
            policy_limit=290000)),
    ("CLM-2025-30003", "HP-460103", "2025-01-01", "Storm water under the back door.", 7900,
     ["2025-01-01 New Year's Day storm; the weather station recorded 58 mm of rain in 24 hours. Insured "
      "Ms. Hannah Kerr found water coming in under the back door into the kitchen.",
      "2025-01-03 Kitchen units and flooring damaged. Estimate 7,900."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 300000),
      term("2025-01-01", "2025-12-31", ["HO-0304 ed. 01-25"], 1000, 300000)],
     expect("NO_EXCLUSION_TRIGGERED", "version-straddle",
            "Loss 2025-01-01, the first day of ed. 01-25: storm ingress (door, 58 mm) is the E-15 exception, "
            "paid up to the 5,000 Storm Ingress Allowance (Clause 5) less the deductible.",
            cite=["E-15", "HO-0304 Clause 5"], editions={"HO-0304": "01-25"}, deductible=1000, sub_limit=5000,
            policy_limit=300000)),
    ("CLM-2025-30004", "HP-460104", "2025-03-14", "Water through a basement window in heavy rain.", 3900,
     ["2025-03-14 Heavy rain, 66 mm in 24 hours. Water came in through the basement window frame.",
      "2025-03-15 Insured Mr. Daniel Reyes, 9 Kestrel Way, phone (555) 410-2210. Plaster and flooring damaged. "
      "Estimate 3,900."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 750, 260000),
      term("2025-01-01", "2025-12-31", ["HO-0304 ed. 01-25"], 750, 260000)],
     expect("NO_EXCLUSION_TRIGGERED", "version-straddle",
            "Loss 2025-03-14 under ed. 01-25: storm ingress through a window in a 66 mm storm - E-15 exception, "
            "Storm Ingress Allowance 5,000, deductible 750.",
            cite=["E-15", "HO-0304 Clause 5"], editions={"HO-0304": "01-25"}, deductible=750, sub_limit=5000,
            policy_limit=260000)),
    ("CLM-2025-30005", "HP-460105", "2025-02-10", "River flooded the ground floor.", 22000,
     ["2025-02-10 After snowmelt the river burst its banks; 40 cm of river water across the ground floor.",
      "2025-02-12 No rainfall event recorded locally. Estimate 22,000."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 410000),
      term("2025-01-01", "2025-12-31", ["HO-0304 ed. 01-25"], 1000, 410000)],
     expect("EXCLUSION_APPEARS_TO_APPLY", "version-straddle",
            "Loss 2025-02-10 under ed. 01-25: river flood is not storm ingress, so the new exception does not "
            "reach it - E-15 still excludes.", cite=["E-15"], editions={"HO-0304": "01-25"}, deductible=1000,
            policy_limit=410000)),
    # --- policy not in force on the loss date ----------------------------------------------------
    ("CLM-2024-30011", "HP-460111", "2024-10-12", "Burst pipe in the utility room.", 5100,
     ["2024-10-12 Supply line to the washing machine split; found within the hour and shut off.",
      "2024-10-13 Insured says the policy is active. Estimate 5,100."],
     [term("2024-01-01", "2024-09-30", ["HO-0304 ed. 03-24"], 1000, 270000)],
     expect("POLICY_NOT_IN_FORCE", "not-in-force",
            "The only term ended 2024-09-30 (cancelled); the loss on 2024-10-12 falls outside it.",
            in_force="NOT_IN_FORCE")),
    ("CLM-2024-30012", "HP-460112", "2024-10-28", "Ceiling came down after a leak upstairs.", 8700,
     ["2024-10-28 Toilet supply hose burst in the upstairs bathroom; the ceiling below collapsed.",
      "2024-10-29 Insured bought the policy last week. Estimate 8,700."],
     [term("2024-11-01", "2025-10-31", ["HO-0304 ed. 03-24"], 1000, 300000)],
     expect("POLICY_NOT_IN_FORCE", "not-in-force",
            "The policy incepted 2024-11-01, four days after the 2024-10-28 loss.", in_force="NOT_IN_FORCE")),
    ("CLM-2025-30013", "HP-460113", "2025-01-03", "Frozen pipe burst in the loft.", 4300,
     ["2025-01-03 Pipe in the loft froze and split; found the same morning.",
      "2025-01-04 Renewal was paid on 5 January. Estimate 4,300."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 285000),
      term("2025-01-05", "2025-12-31", ["HO-0304 ed. 01-25"], 1000, 285000)],
     expect("POLICY_NOT_IN_FORCE", "not-in-force",
            "Gap between terms: the 2024 term ended 2024-12-31 and the renewal began 2025-01-05; the loss on "
            "2025-01-03 is in neither.", in_force="NOT_IN_FORCE")),
    # --- deductible, sub-limit and policy limit: three different numbers ---------------------------
    ("CLM-2024-30021", "HP-460121", "2024-07-21", "Sewer backup in the basement.", 12600,
     ["2024-07-21 Municipal sewer surcharged in a storm and backed up through the floor drain into the "
      "finished basement.", "2024-07-23 Insured Mr. Omar Haddad's son cut his hand on broken glass while "
      "moving boxes and needed 4 stitches. Estimate for the basement 12,600."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24", "HO-0820 ed. 05-24"], 500, 380000)],
     expect("NO_EXCLUSION_TRIGGERED", "limits",
            "Sewer backup: E-16 is overridden by the HO-0820 Clause 2 grant - sub-limit 10,000 per event with "
            "HO-0820's own 1,000 deductible (not the 500 policy deductible); dwelling limit 380,000.",
            cite=["HO-0820", "E-16"], editions={"HO-0304": "03-24", "HO-0820": "05-24"}, deductible=1000,
            sub_limit=10000, policy_limit=380000)),
    ("CLM-2024-30022", "HP-460122", "2024-09-05", "Work laptop and camera stolen from a car.", 3600,
     ["2024-09-05 Insured runs a graphic design business from home; gross receipts were 41,000 over the "
      "last 12 months. Laptop and camera used for the business were stolen from the car outside a client's "
      "office.", "2024-09-06 Police report filed. Value 3,600."],
     [term("2024-01-01", "2024-12-31", ["HO-0509 ed. 06-24"], 250, 280000)],
     expect("NO_EXCLUSION_TRIGGERED", "limits",
            "Business property away from the residence premises: HO-0509 Clause 2 sub-limit 500; deductible "
            "250; the limit it sits within is Coverage C personal property, 140,000.",
            cite=["HO-0509"], editions={"HO-0509": "06-24"}, deductible=250, sub_limit=500, policy_limit=140000)),
    ("CLM-2024-30023", "HP-460123", "2024-06-30", "Fire; the rebuild must meet current code.", 40000,
     ["2024-06-30 Kitchen fire. The city requires the rebuild, including the undamaged rooms, to meet "
      "current building code; increased cost of construction quoted at 40,000.",
      "2024-07-02 Insured Dr. Samuel Achebe was treated in hospital for smoke inhalation and released."],
     [term("2024-01-01", "2024-12-31", ["HO-0612 ed. 03-24"], 1000, 350000)],
     expect("NO_EXCLUSION_TRIGGERED", "limits",
            "Ordinance or law: HO-0612 raises the limit to 25 percent of Coverage A, so the sub-limit is "
            "87,500 within the 350,000 dwelling limit; deductible 1,000; no pollutant cost is claimed.",
            cite=["HO-0612"], editions={"HO-0612": "03-24"}, deductible=1000, sub_limit=87500,
            policy_limit=350000)),
    # --- the wording that applies is not on file -------------------------------------------------
    ("CLM-2024-30031", "HP-460131", "2024-11-30", "Burst supply line at a rented condo.", 9300,
     ["2024-11-30 The loss is at a condo the insured owns in another city and rents out, not at the insured's "
      "own home. It stood empty 45 days between tenants and the water was left on when a supply line burst.",
      "2024-12-02 Estimate 9,300."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 330000)],
     expect("WORDING_NOT_ON_FILE", "wrong-property",
            "A homeowners policy on the insured's own home does not reach a tenant-occupied condo elsewhere; a "
            "dwelling-fire policy would be needed and none is on file (Week 6 C13, labelled NOT_IN_DOCUMENTS).",
            editions={"HO-0304": "03-24"})),
    ("CLM-2024-30032", "HP-460132", "2024-09-03", "Hail dented the metal roof.", 16800,
     ["2024-09-03 Hail dented the metal roof panels; the roofer finds no leaks and the panels still shed "
      "water.", "2024-09-05 Insured wants the whole roof replaced. Estimate 16,800."],
     [term("2024-01-01", "2024-12-31", ["HO-0415 ed. 05-23"], 2500, 340000)],
     expect("WORDING_NOT_ON_FILE", "wording-not-on-file",
            "The policy carries HO-0415 ed. 05-23, which is not in the wording library; ed. 01-24 must not be "
            "applied in its place (Week 6 C12).", editions={})),
    ("CLM-2024-30033", "HP-460133", "2024-02-10", "Burst pipe behind the dishwasher.", 6400,
     ["2024-02-10 Dishwasher supply hose split; found within two hours and the water shut off.",
      "2024-02-12 Estimate 6,400."],
     [term("2024-01-01", "2024-12-31", ["HO-0304 ed. 03-24"], 1000, 300000)],
     expect("WORDING_NOT_ON_FILE", "wording-not-on-file",
            "HO-0304 ed. 03-24 took effect on 2024-03-01, after this 2024-02-10 loss; the edition in force on the "
            "loss date is not in the library, so ed. 03-24 must not be applied to it.", editions={})),
    ("CLM-2024-30034", "DF-460134", "2024-10-20", "Burst fitting at an empty rental.", 11200,
     ["2024-09-03 Tenant left on 1 September. Landlord, who lives abroad, had a plumber shut the water off "
      "at the main and drain the system on 3 September.", "2024-10-20 No inspection of the unit was done after "
      "the tenant left. Neighbour reported water under the door: a supply line fitting burst. Estimate 11,200."],
     [term("2024-01-01", "2024-12-31", ["DP-0703 ed. 02-24"], 1500, 230000)],
     expect("EXCLUSION_APPEARS_TO_APPLY", "notes-trigger-exclusion",
            "Empty 49 days: E-61 applies; the shut-off-and-drain exception is voided by the Clause 4 duty to "
            "inspect within 7 days, which was not done.", cite=["E-61"], editions={"DP-0703": "02-24"},
            deductible=1500, policy_limit=230000)),
]


def main():
    claims, policies, cases = week7()
    for cid, pol, dol, first, amount, notes, terms, exp in NEW:
        claims.append(claim(cid, pol, dol, first, amount, notes))
        line = "dwelling-fire" if pol.startswith("DF") else "homeowners"
        policies[pol] = {"policy_number": pol, "product": "household", "policy_line": line, "terms": terms}
        cases.append({"id": cid, "claim_id": cid, **exp})
    os.makedirs("claims_system", exist_ok=True)
    os.makedirs("policy_admin", exist_ok=True)
    os.makedirs("evals", exist_ok=True)
    with open(os.path.join("claims_system", "claims.json"), "w", encoding="utf-8") as f:
        json.dump(claims, f, indent=1, ensure_ascii=False)
    with open(os.path.join("policy_admin", "policies.json"), "w", encoding="utf-8") as f:
        json.dump(policies, f, indent=1, ensure_ascii=False)
    with open(os.path.join("evals", "cases.jsonl"), "w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    modes = {}
    for c in cases:
        modes[c["mode"]] = modes.get(c["mode"], 0) + 1
    print("%d claims, %d policies, %d eval cases; by mode: %s" % (len(claims), len(policies), len(cases), modes))


if __name__ == "__main__":
    main()
