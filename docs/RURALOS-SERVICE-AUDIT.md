# Service depth audit — 28 September 2026

## Reproduced problem

Parent `4c973b3467b2fdb7bf3535d4b95444ab14a887c0`. Live Chrome: Aadhaar → Telangana → “Change mobile number” → confirm displayed a generic UIDAI instruction and three generic checklist items. Code inspection confirms every non-travel task collected `region` and `goal`, but goal did not affect the result. The current travel review only summarised inputs and offered provider links. This validates the user's complaint about shallow post-entry results.

## Changes and exact coverage

All 38 non-travel services now have two explicit purpose choices, two different next actions, four service-specific preparation points, two questions to ask the provider, and a common mistake to avoid. Unknown typed goals are never silently classified; the result asks the user to choose. New/in-progress/blocked/completed state is self-reported, not live status. Checkboxes prioritise the first unchecked item and clear on navigation/restart. English detail has a dedicated en-IN listen action; Hindi/Telugu controls and existing translated basic steps remain available. The new detailed paragraphs and purpose choices remain explicitly English pending translation review.

| Service | The two distinct purposes covered | Missing live or official capability |
|---|---|---|
| Aadhaar | Change contact/address; track an existing update | Account access, update submission, appointments |
| Pensions/family schemes | Find support; resolve a pending case | State-specific automated eligibility and status |
| Certificates | New certificate; correction/renewal | Issuer requirements lookup and submission |
| Land | Pre-purchase checks; registration/record update | Title validation, encumbrance/restriction verification, fee calculation |
| Flats | Pre-purchase checks; registration/handover | Project/title approval verification |
| Ration | Application/household change; denied supply/pending request | Household eligibility and supply records |
| Health cards | Beneficiary check; planned hospital care | Patient coverage, hospital/appointment availability |
| Scholarships | Course-specific discovery; renewal/pending verification | Current scheme-level eligibility and deadlines |
| PM-KISAN | Registration; pending benefit | Official beneficiary/payment data |
| Jobs | Suitable work; offer verification | Live vacancies or employer verification |
| Credit | Understand scheme; compare written terms | Lender quotes, applications and recommendations |
| Stocks | Company research; intermediary/claim checks | Live quotes, recommendations and trading |
| Workers | New e-Shram registration; existing-record check | Official registration and benefit status |
| Fraud | Suspected financial cyberfraud; suspicious message | Reporting and recovery; urgent official channels remain necessary |
| Grievances | Prepare complaint; unresolved follow-up | Filing and official case tracking |
| DigiLocker | Find issued document; retrieval/correction problem | Private locker or issuer access |
| Driving/vehicle | Licence application/renewal; transfer/correction | RTO records, tests, appointments, payment |
| Voter | Enrol/correct; check existing record | Electoral-roll lookup and submissions |
| Passport | Issue/reissue; track existing application | Appointments, police/passport status |
| Birth/death | Obtain certificate; correct/locate record | Registrar jurisdiction/rules and submission |
| Disability | Assessment/UDID preparation; follow-up | Assessment, certification and eligibility |
| Housing | Local selection enquiry; existing case | Selection/payment/construction status |
| LPG | New connection/PMUY; refill/service issue | Provider bookings, deliveries and benefit eligibility |
| Legal | Find legal aid; prepare an existing matter | Case-specific advice and representation |
| Consumer | Purchase complaint; unresolved follow-up | Filing, refunds or adjudication |
| Crop insurance | Crop/season checks; policy issue | Policy/notification data, sale, claims or deadlines |
| Mandis | Compare net proceeds; prepare a visit | Live prices, buyers and trades |
| Skills | Choose course; verify provider | Live course availability and verification |
| Udyam | Register; correct existing record | Official registration or all-sector licence assessment |
| Telemedicine | Prepare consultation; clinician follow-up | Clinical triage, diagnosis, appointment or medical records |
| Water | Supply interruption; quality concern | Local case status, testing or repairs |
| Sanitation | Household support; local service issue | Eligibility, approvals and service dispatch |
| Bus transport | Plan journey; ticket/service issue | Live seats, fares, tracking and booking |
| Women's groups | Locate recognised group; understand membership | Local group verification or financial participation |
| Nutrition | Find Anganwadi service; enrolment/referral follow-up | Local availability, clinical assessment or enrolment |
| Learning | Choose lesson; study routine | Child assessment or teacher integration |
| Farm weather | Plan farm work; seasonal advisory review | Field-specific weather or crop recommendation |
| Job cards | Card/work request; work/wage records | Employment/wage verification and requests |
| Flights | Month planning + total quote comparison | Live month fares, repricing, booking, tracking |
| Rail | Month planning + total quote comparison | Seats, fares, booking, rail status |
| Cabs | Date planning + total quote comparison | Live quotes, dispatch, booking, location |
| Holidays | Month planning + total quote comparison | Package/hotel inventory and reservations |

Sailing remains an additional mode inside travel, with specific pre-sailing questions and the same manual INR cost comparison; no operator is invented. The comparator requires an explicit zero for an absent cost, treats blanks/invalid amounts as unknown, includes extras/transfers, compares group totals with the budget, and only ranks at least two complete quotes after the user confirms comparable assumptions. Editing a quote revokes that confirmation. No entered price is called live or independently verified.

## Evidence and source boundary

The new playbooks are editorial preparation aids and questions, not new government rules. Existing official routes are reused. Readable official pages reviewed for this change: UIDAI https://uidai.gov.in/en ; myScheme https://www.myscheme.gov.in/ ; DoLR https://dolr.gov.in/en/citizen-centric-services/ ; NSP https://scholarships.gov.in/ ; SEBI https://investor.sebi.gov.in/ ; NCS https://ncs.gov.in/ ; DigiLocker https://www.digilocker.gov.in/ . ServicePlus, PM-KISAN, NHA, NALSA and IRCTC retrieval returned errors in the research channel; this does not establish a provider outage, and no refreshed verification date or new rules are claimed for them. Fees, eligibility thresholds, office details, expiry dates and case decisions are deliberately left for the responsible provider.

## Verification scope

- Functional tests cover both purposes for every non-travel service, unknown/hostile goals, missing checklist items and non-execution boundaries.
- Quote tests cover arithmetic, missing and invalid costs, zero, INR decimal precision, Hindi/Telugu digits, ties, invalid group counts, budget limits and comparable-basis requirements.
- React server-render checks cover both purposes for 38 services in all three interface languages; these validate rendering and escaping, not translation accuracy or comprehension.
- Existing route, traversal, method, offline-cache, feed failure and owner-only redirect tests remain required.
- Live browser verification follows deployment. Actual rural-user comprehension, physical microphones, native iOS/Android and live provider journeys are not established by these automated checks.

## Next product work

1. Independently review and translate the detailed playbooks and purpose choices into Hindi/Telugu; test with representative rural households.
2. Replace specific preparation questions with authoritative structured answers only where current regional sources can be verified. Prioritise Aadhaar update subtypes, pension schemes and scholarship verification stages.
3. Obtain authorised provider/model access for real answers and live data; no amount of checklist content supplies missing inventory, eligibility or case records.
4. Add consent-based outcome feedback through the existing authenticated companion. No public household telemetry or model training was introduced.
