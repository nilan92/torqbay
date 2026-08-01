# Torqbay — Workshop Management App

Planning docs written before development starts. Read in order.

1. [Overview](01-overview.md) — what this is, who it's for, scope
2. [Architecture](02-architecture.md) — tech stack, multi-tenancy, module map
3. [Data Model](03-data-model.md) — entities, tables, relationships
4. [API Design](04-api-design.md) — endpoint map, conventions, auth
5. [Mobile App](05-mobile-app.md) — Expo app structure, screens, navigation
6. [Invoice Template](06-invoice-template.md) — PDF invoice spec
7. [Sri Lanka Localization](07-sri-lanka-localization.md) — currency, tax, payment gateways, SMS/WhatsApp providers
8. [Roadmap](08-roadmap.md) — phased build plan (7 phases)
9. [Business Advisor](09-business-advisor.md) — rule-based growth/pitfall insights (Phase 2)
10. [AI Features](10-ai-features.md) — AI chat, consultant reports, customer chatbot, MCP server (Phase 6)
11. [Repair Guides](11-repair-guides.md) — shared video/text reference library by vehicle model (Phase 3)

## Quick facts

- **Stack**: React Native (Expo) mobile app + Python (FastAPI) backend + MySQL
- **Model**: Multi-tenant SaaS — many workshop businesses, one deployment
- **Domain**: Repair/service workshops (auto, electronics, appliance, etc.)
- **Market**: Sri Lanka first (LKR currency, local tax rules, local payment/SMS providers)
- **Status**: Planning only — no code written yet
