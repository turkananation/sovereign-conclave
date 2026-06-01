# Concepts

Sovereign Conclave is a decision protocol. The seat names are memorable handles
for stances, not claims that a model becomes a historical figure.

## Seat

A seat is a lens. It guarantees that one stance will be argued even if the main
assistant would normally skip it.

Good seat:

- One stance.
- Three or four concrete moves.
- A known bias.
- A boundary: "You are NOT."
- A polarity partner.

Bad seat:

- Claims special expertise from the name.
- Agrees with an existing seat.
- Tries to be balanced.
- Acts as a verifier without being a Justice.

## Danger Lenses

Some seats represent dangerous governance logics such as coercive control or
extractive administration. These seats exist so the Conclave can name the ugly
logic before it hides inside words like efficiency, stability, security, or
order.

They are red-team instruments, not endorsements. They must not propose harm,
plan repression, excuse dispossession, or authorize action. Their job is to
surface the pattern so Marshall and the Justices can constrain, reject, or
repair it.

## Evidence Ledger

The Evidence Ledger is the frozen set of artifacts the verdict may rely on:
files, quoted documents, logs, metrics, screenshots, or sourced claims. Every
load-bearing factual claim gets an `E#` citation.

If there is no evidence, the Conclave can still reason, but the verdict must say
that confidence is low and Marshall must flag unsupported decisive claims.

The full ledger standard is documented in
[EVIDENCE_LEDGER.md](EVIDENCE_LEDGER.md). The short rule: each row must be
atomic, provenance-bearing, and stable after Round 1 starts. New evidence is
appended and marked post-freeze instead of silently changing old rows.

## Marshall

Marshall is always convened. Marshall does not pick the winning option. Marshall
checks whether decisive claims are supported by the Evidence Ledger and whether
the recommendation violates the directives.

## Justice Seats

The other Justice seats are structural checks:

- Lady Hale: proportionality and rights.
- Bhagwati: access, standing, and missing stakeholders.
- Chaskalson: constitutional values and dignity.
- Jackson: emergency authority, institutional role, oversight, and sunset.
- Sachs: repair, memory, remedy, restoration, and transitional legitimacy.

They do not advocate for an option. They enforce boundaries.

## Profiles

Profiles are small convened quorums. The library can grow, but the meeting stays
small: 3-8 seats plus Marshall.

Use profiles when you know the kind of decision:

- `architecture` for technical design.
- `war-game` for adversarial stress tests.
- `esiasa-civic-stress` for county intelligence and civic resilience.
- `pandemic-preparedness` for outbreak planning and public trust.
- `oppression-audit` for coercion, surveillance, emergency drift, and dignity.
- `decolonization` for land, dispossession, self-determination, and repair.
- `emergency-powers` for lawful authority, continuity, oversight, and sunset.

Use `--members` when you need a custom polarity.

## Local Runner

`bin/conclave` is a local scaffold runner. It reads
`configs/conclave-roster.json`, selects profile seats, and writes a verdict file
shell. It does not call models or infer evidence.

That separation is intentional: selection and file generation are deterministic;
reasoning remains grounded in the evidence you supply to the assistant.
