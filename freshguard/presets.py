"""Demo inputs covering the problem statement's domains: pricing, APIs, regulation, leadership."""
from typing import Any, Dict

DEMO_PRESETS: Dict[str, Dict[str, Any]] = {
    "pricing": {
        "id": "pricing",
        "title": "SaaS & AI pricing",
        "category": "Pricing",
        "description": "Subscription tiers and prices that change often.",
        "prompt": "What are the paid ChatGPT subscription tiers and how much do they cost?",
        "text": "OpenAI's highest paid consumer subscription tier for ChatGPT is ChatGPT Plus at $20 per month, and there is no $200 per month tier.",
    },
    "api_versions": {
        "id": "api_versions",
        "title": "API versions & deprecations",
        "category": "APIs",
        "description": "Recommended endpoints and models that get deprecated.",
        "prompt": "Which OpenAI model and endpoint should I use for a new production app?",
        "text": "OpenAI's recommended flagship model for production API applications is currently text-davinci-003 via the legacy Completions endpoint. Tavily provides a Search API endpoint at https://api.tavily.com/search designed for AI agents.",
    },
    "regulation": {
        "id": "regulation",
        "title": "Regulation status",
        "category": "Regulation",
        "description": "Laws that moved from proposal to enforcement.",
        "prompt": "What is the current status of the EU AI Act?",
        "text": "The European Union AI Act is currently only a proposed draft bill and has not yet entered into force in the European Union.",
    },
    "leadership": {
        "id": "leadership",
        "title": "Leadership changes",
        "category": "Leadership",
        "description": "Executives and office holders.",
        "prompt": "Who are the current CEOs of Microsoft and Apple?",
        "text": "Satya Nadella is the current CEO of Microsoft. Tim Cook is the CEO of Apple.",
    },
}
