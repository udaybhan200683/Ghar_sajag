# Parivar Sathi v3.4.3 — legacy browser assertion alignment

The legacy engineering-lab browser test expected the older UI phrase:

`No incidents`

The current engineering lab correctly renders:

`No open incidents in this scenario.`

The test now validates the semantic condition ("no incidents are open") using:

`/No (?:open )?incidents/i`

This is a test-only correction. Product behavior, PWA, battery analytics,
backend logic, and the 92 canonical functional scenarios are unchanged.
