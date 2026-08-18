# Evaluation set: each question maps to exactly one "gold" document from
# insurance_data.CLAIM_DOCS, plus a keyword we expect a correct final answer
# to contain (used to catch "right document, wrong answer" failures).

EVAL_QUESTIONS = [
    {
        "question": "I was just in a car crash, how soon do I need to notify my insurer?",
        "gold_id": "auto_claim_filing",
        "expected_keyword": "30 days",
    },
    {
        "question": "My car claim got rejected, what's my window to push back on that decision?",
        "gold_id": "auto_claim_appeal",
        "expected_keyword": "60 days",
    },
    {
        "question": "If the crash was my fault, how much comes out of my pocket before insurance pays?",
        "gold_id": "auto_claim_deductible",
        "expected_keyword": "1000",
    },
    {
        "question": "After seeing a doctor, how much time do I have to send in the paperwork for reimbursement?",
        "gold_id": "health_claim_filing",
        "expected_keyword": "90 days",
    },
    {
        "question": "My medical claim was turned down, how long can I wait before contesting it internally?",
        "gold_id": "health_claim_appeal",
        "expected_keyword": "180 days",
    },
    {
        "question": "Can I just book an elective surgery and expect my plan to cover it automatically?",
        "gold_id": "health_claim_preauth",
        "expected_keyword": "pre-authorization",
    },
    {
        "question": "My house got damaged, how quickly do I have to let my insurer know?",
        "gold_id": "home_claim_filing",
        "expected_keyword": "60 days",
    },
    {
        "question": "If a river overflows into my house, will my regular policy pay for that?",
        "gold_id": "home_claim_flood",
        "expected_keyword": "excluded",
    },
    {
        "question": "After a big storm, is my out-of-pocket cost the same fixed amount as for other damage?",
        "gold_id": "home_claim_deductible",
        "expected_keyword": "percentage",
    },
    {
        "question": "My father passed away, what paperwork do I need to collect on his policy?",
        "gold_id": "life_claim_beneficiary",
        "expected_keyword": "death certificate",
    },
    {
        "question": "How far back can the insurer dig into my application if something happens to me soon after buying the policy?",
        "gold_id": "life_claim_contestability",
        "expected_keyword": "two-year",
    },
    {
        "question": "My friend's payout request got rejected, what are the usual explanations for that?",
        "gold_id": "claim_denial_reasons",
        "expected_keyword": "late filing",
    },
    {
        "question": "After my insurer pays me out, can they go after the other driver to get their money back?",
        "gold_id": "claim_subrogation",
        "expected_keyword": "reimbursement",
    },
    {
        "question": "What happens behind the scenes if an adjuster thinks I'm lying about my loss?",
        "gold_id": "claim_fraud_investigation",
        "expected_keyword": "special investigations",
    },
    {
        "question": "My mechanic says the car isn't worth fixing, how does the insurer decide what to pay me?",
        "gold_id": "auto_claim_total_loss",
        "expected_keyword": "actual cash value",
    },
    {
        "question": "While my car sits in the body shop, will my insurance cover a loaner?",
        "gold_id": "auto_claim_rental",
        "expected_keyword": "rental",
    },
    {
        "question": "A rock cracked my windshield, do I still pay the usual out-of-pocket amount?",
        "gold_id": "auto_claim_glass",
        "expected_keyword": "glass",
    },
    {
        "question": "I saw a specialist who isn't in my plan's network, how much of the bill lands on me?",
        "gold_id": "health_claim_out_of_network",
        "expected_keyword": "balance billing",
    },
    {
        "question": "I just quit my job, can I keep the same health plan for a while and how much would it cost?",
        "gold_id": "health_claim_cobra",
        "expected_keyword": "COBRA",
    },
    {
        "question": "My kitchen fire means we can't live at home right now, does the policy help with a hotel?",
        "gold_id": "home_claim_temp_housing",
        "expected_keyword": "additional living expenses",
    },
    {
        "question": "A delivery driver slipped on my driveway and got hurt, does my home policy cover that?",
        "gold_id": "home_claim_liability",
        "expected_keyword": "liability",
    },
    {
        "question": "If a loved one dies in a car wreck, is there ever an extra payout beyond the normal death benefit?",
        "gold_id": "life_claim_accidental_death",
        "expected_keyword": "accidental death",
    },
]
