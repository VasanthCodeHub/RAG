# Small synthetic "insurance claims" knowledge base.
# Deliberately includes near-duplicate docs (filing vs appeal vs deductible,
# per line of business) so that a weak retriever can genuinely confuse them.

CLAIM_DOCS = [
    {
        "id": "auto_claim_filing",
        "title": "Filing an Auto Insurance Claim",
        "text": (
            "To file an auto insurance claim after an accident, report the incident "
            "to your insurer within 30 days of the accident date. Provide the police "
            "report, photos of the damage, and the other driver's information. Claims "
            "filed after 30 days may be denied for late reporting."
        ),
    },
    {
        "id": "auto_claim_appeal",
        "title": "Appealing a Denied Auto Insurance Claim",
        "text": (
            "If your auto claim is denied, you may submit a written appeal to the "
            "insurer within 60 days of the denial letter. Include any new evidence, "
            "such as an independent repair estimate or witness statements, to support "
            "your appeal."
        ),
    },
    {
        "id": "auto_claim_deductible",
        "title": "Auto Claim Deductible Amounts",
        "text": (
            "The standard auto insurance deductible is $500 for comprehensive claims. "
            "For at-fault collision claims, the deductible increases to $1000. The "
            "deductible is subtracted from the total payout before the insurer issues "
            "payment."
        ),
    },
    {
        "id": "health_claim_filing",
        "title": "Filing a Health Insurance Claim",
        "text": (
            "Health insurance claims must be submitted within 90 days of receiving "
            "treatment. Attach the itemized bill from the provider and the claim form. "
            "Claims submitted after the 90-day window are not reimbursable."
        ),
    },
    {
        "id": "health_claim_appeal",
        "title": "Appealing a Denied Health Insurance Claim",
        "text": (
            "You have 180 days from the date of denial to file an internal appeal for "
            "a denied health claim. The appeal must include a letter from your "
            "physician explaining medical necessity."
        ),
    },
    {
        "id": "health_claim_preauth",
        "title": "Pre-Authorization Requirements for Health Claims",
        "text": (
            "Certain procedures, such as elective surgery and MRI scans, require "
            "pre-authorization from the insurer before the procedure is performed. "
            "Claims for procedures lacking pre-authorization may be denied even if "
            "the procedure was medically necessary."
        ),
    },
    {
        "id": "home_claim_filing",
        "title": "Filing a Homeowners Insurance Claim",
        "text": (
            "Report property damage to your homeowners insurer within 60 days of "
            "discovering the damage. Take photos before making any temporary repairs "
            "and keep receipts for emergency repair costs."
        ),
    },
    {
        "id": "home_claim_flood",
        "title": "Flood Damage and Homeowners Claims",
        "text": (
            "Flood damage is excluded under a standard homeowners policy. Homeowners "
            "must purchase a separate flood insurance policy, typically through the "
            "National Flood Insurance Program, to be covered for flood-related losses."
        ),
    },
    {
        "id": "home_claim_deductible",
        "title": "Homeowners Claim Deductible Structure",
        "text": (
            "Most homeowners policies use a flat-dollar deductible, but wind and hail "
            "damage claims often use a percentage-based deductible, typically 1-5% of "
            "the home's insured value, which is usually higher than the flat deductible."
        ),
    },
    {
        "id": "life_claim_beneficiary",
        "title": "Filing a Life Insurance Death Benefit Claim",
        "text": (
            "A beneficiary filing a life insurance death benefit claim must submit a "
            "certified copy of the death certificate along with the claim form. "
            "Payout is typically issued within 30 days of the insurer receiving a "
            "complete claim."
        ),
    },
    {
        "id": "life_claim_contestability",
        "title": "Contestability Period for Life Insurance Claims",
        "text": (
            "Life insurance policies have a two-year contestability period from the "
            "policy start date. During this period, the insurer may investigate and "
            "deny a death claim if it finds material misrepresentation on the "
            "application."
        ),
    },
    {
        "id": "claim_denial_reasons",
        "title": "Common Reasons Insurance Claims Are Denied",
        "text": (
            "Claims are commonly denied for late filing, a lapsed or cancelled "
            "policy at the time of loss, a policy exclusion that applies to the "
            "loss, or insufficient documentation supporting the claimed amount."
        ),
    },
    {
        "id": "claim_subrogation",
        "title": "Subrogation in Insurance Claims",
        "text": (
            "Subrogation is the process by which an insurer, after paying a claim, "
            "seeks reimbursement from the at-fault third party or their insurer. This "
            "allows the insurer to recover the payout without the policyholder "
            "pursuing the at-fault party directly. In plain terms: after your insurer "
            "pays you out for the accident, it can go after the other driver (or "
            "their insurer) to get its money back."
        ),
    },
    {
        "id": "claim_fraud_investigation",
        "title": "How Insurers Investigate Suspected Claim Fraud",
        "text": (
            "When fraud is suspected, insurers assign the claim to a special "
            "investigations unit, which may interview the claimant, review financial "
            "records, and cross-check the claim against prior claims databases before "
            "deciding whether to pay, deny, or refer the case for prosecution."
        ),
    },
    # --- Extra distractors below: same lines of business, closely related  ---
    # --- sub-topics, added to make top-3 retrieval genuinely competitive.  ---
    {
        "id": "auto_claim_total_loss",
        "title": "Total Loss Auto Claims",
        "text": (
            "When a vehicle is declared a total loss, the insurer pays the car's "
            "actual cash value at the time of the accident, minus the deductible, "
            "rather than paying for repairs."
        ),
    },
    {
        "id": "auto_claim_rental",
        "title": "Rental Car Reimbursement During an Auto Claim",
        "text": (
            "While a covered vehicle is being repaired, most auto policies "
            "reimburse a rental car for up to 30 days, subject to a daily rate cap "
            "set by the policy."
        ),
    },
    {
        "id": "auto_claim_glass",
        "title": "Windshield and Glass-Only Auto Claims",
        "text": (
            "Windshield and glass-only claims usually carry a separate, lower or "
            "zero deductible compared to a standard comprehensive claim."
        ),
    },
    {
        "id": "health_claim_out_of_network",
        "title": "Out-of-Network Health Claim Reimbursement",
        "text": (
            "Claims for out-of-network providers are reimbursed at a lower rate, "
            "and the patient is responsible for the difference between the "
            "provider's charge and the plan's allowed amount, known as balance "
            "billing."
        ),
    },
    {
        "id": "health_claim_cobra",
        "title": "Continuing Health Coverage After Leaving a Job",
        "text": (
            "After leaving an employer, an employee can continue the same group "
            "health coverage under COBRA for up to 18 months, but must pay the "
            "full premium out of pocket."
        ),
    },
    {
        "id": "home_claim_temp_housing",
        "title": "Additional Living Expenses on a Homeowners Claim",
        "text": (
            "If a covered loss makes a home temporarily uninhabitable, homeowners "
            "policies typically reimburse additional living expenses, including "
            "temporary housing, for a limited period while repairs are made."
        ),
    },
    {
        "id": "home_claim_liability",
        "title": "Homeowners Liability Coverage",
        "text": (
            "Liability coverage on a homeowners policy pays for injuries or "
            "property damage that happen to third parties on the property, "
            "separate from the dwelling coverage that pays for damage to the "
            "home itself."
        ),
    },
    {
        "id": "life_claim_accidental_death",
        "title": "Accidental Death Benefit Rider",
        "text": (
            "An accidental death benefit rider pays an extra lump sum on top of "
            "the base life insurance payout if the insured dies as a result of a "
            "covered accident, generally within 90 days of that accident."
        ),
    },
]
