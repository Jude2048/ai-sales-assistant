DEFAULT_POLICY = {
    "services": [
        "data analytics",
        "business intelligence",
        "dashboard development",
        "data strategy",
    ],

    "qualification": {
        "minimum_company_size": 10,
        "minimum_budget": 5000,
        "required_need": True,
    },

    "representatives": {
        "alex": {
            "name": "Alex",
            "speciality": [
                "data analytics",
                "business intelligence",
            ],
        },
        "sarah": {
            "name": "Sarah",
            "speciality": [
                "dashboard development",
                "data strategy",
            ],
        },
    },

    "routing": {
        "data analytics": "alex",
        "business intelligence": "alex",
        "dashboard development": "sarah",
        "data strategy": "sarah",
    },

    "timezone": "Europe/London",

    "working_hours": {
        "start": "09:00",
        "end": "17:00",
    },
}


def evaluate_lead(facts: dict, policy: dict = DEFAULT_POLICY):
    evidence = []

    need = facts.get("need")
    company_size = facts.get("company_size")
    budget = facts.get("budget")
    service = facts.get("service")

    # Qualification
    missing = []

    if not need:
        missing.append("business need")

    if company_size is None:
        missing.append("company size")

    if budget is None:
        missing.append("budget")

    if missing:
        return {
            "status": "needs_information",
            "evidence": evidence,
            "missing_information": missing,
            "representative": None,
            "reason": "Required qualification information is missing.",
        }

    if not any(
        service and service.lower() == s.lower()
        for s in policy["services"]
    ):
        return {
            "status": "not_qualified",
            "evidence": [
                f"Requested service '{service}' is not in the supported services."
            ],
            "missing_information": [],
            "representative": None,
            "reason": "Requested service is outside the company's services.",
        }

    if company_size < policy["qualification"]["minimum_company_size"]:
        return {
            "status": "not_qualified",
            "evidence": [
                f"Company size: {company_size}",
                f"Minimum required: {policy['qualification']['minimum_company_size']}",
            ],
            "missing_information": [],
            "representative": None,
            "reason": "Company size is below the qualification threshold.",
        }

    if budget < policy["qualification"]["minimum_budget"]:
        return {
            "status": "not_qualified",
            "evidence": [
                f"Budget: {budget}",
                f"Minimum required: {policy['qualification']['minimum_budget']}",
            ],
            "missing_information": [],
            "representative": None,
            "reason": "Budget is below the qualification threshold.",
        }

    # Qualified
    evidence = [
        f"Business need: {need}",
        f"Company size: {company_size}",
        f"Budget: {budget}",
        f"Requested service: {service}",
    ]

    representative_key = policy["routing"].get(service.lower())

    representative = None

    if representative_key:
        representative = policy["representatives"][
            representative_key
        ]["name"]

    return {
        "status": "qualified",
        "evidence": evidence,
        "missing_information": [],
        "representative": representative,
        "reason": "Lead satisfies all qualification criteria.",
    }