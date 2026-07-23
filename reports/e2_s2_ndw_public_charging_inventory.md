# E2.S2 NDW Public-Charging Inventory Packet

Status: proposed evidence packet only. No ElaadNL public Set B profile was
generated, no EV held-out batch was opened, and no integrated net-load,
congestion, adequacy, event, `P(E)`, or manuscript-result analysis was run.

## Why This Exists

EV-008 proposes a public Set B ElaadNL profile library, but the PI has not
approved the public profile unit and `cp_capacity_kw = 22` convention. This
packet checks whether current NDW/DOT-NL public charging infrastructure around
Alkmaar can inform that decision.

## Sources And Retrieval

Primary NDW documentation:
`https://docs.ndw.nu/data-uitwisseling/interface-beschrijvingen/dafne-api/dafne_api_consumer_pull/`.
The docs state that the GeoJSON API accepts bounding boxes in
`minLon,minLat,maxLon,maxLat` order, has a maximum area of `1.0 degree^2`, a
maximum of 1000 features, and a 10 requests/s limit. The same docs state that
the full Netherlands OCPI locations dataset can be retrieved from:
`https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz`.

Open-data portal check:
`https://opendata.ndw.nu/` listed `charging_point_locations_ocpi.json.gz` as a
15M real-time file on 2026-07-21. The NDW copyright page states that, unless
otherwise indicated, CC0 applies to website content. This PR commits only
parser code, metadata, and summary counts; the live raw OCPI and GeoJSON
responses are not committed.

Retrieved evidence recorded in
`data/metadata/ev_adoption/ndw_alkmaar_public_charging_inventory_metadata.json`:

| Source slice | URL / selector | Size | SHA-256 | Count |
|---|---|---:|---|---:|
| Full OCPI gzip | `https://opendata.ndw.nu/charging_point_locations_ocpi.json.gz` | 15,218,242 bytes | `a91ccea2d2bb03400437c9dc73aade71725b04129e0d6c3599cab09d91374047` | 66,473 Netherlands OCPI locations |
| Alkmaar-area GeoJSON bbox | `bbox=4.68,52.59,4.82,52.68` | 394,263 bytes | `3a82997602afe6aaecf63d6cd9d694817cba0429b3e0c09aab1dd48110a4dc89` | 774 GeoJSON features |

The OCPI file exposes `city`, coordinates, `evses`, and connector-level fields
including `standard`, `power_type`, and `max_electric_power`. It does not expose
a CBS municipality code. Therefore this packet reports two reproducible slices:

- `city == Alkmaar`, case-insensitive exact match.
- An Alkmaar-area bbox `4.68,52.59,4.82,52.68`.

These are not official `GM0361` municipality-boundary counts. Exact
municipality counts require a boundary join against a sourced administrative
geometry.

## Alkmaar Counts

| Slice | OCPI locations | EVSEs | Connectors | Notes |
|---|---:|---:|---:|---|
| `city == Alkmaar` | 479 | 1,190 | 1,190 | 479 locations had EVSEs; 22 connectors missing `max_electric_power`. |
| Alkmaar-area bbox | 774 | 1,799 | 1,799 | Includes 475 `city == Alkmaar` locations plus nearby city strings such as Heiloo, Heerhugowaard, Bergen, Oudorp, Koedijk, and Stompetoren. |

In this NDW snapshot, each selected EVSE had one connector, so EVSE and
connector counts are numerically identical for these slices. That is an
observed property of this retrieval, not a general OCPI invariant.

The GeoJSON bbox response is consistent with the OCPI bbox slice at the level
needed here: 774 features and a summed availability `total` of 1,799. The
GeoJSON response is useful as a small reproducible cross-check, but the full
OCPI file is the better unit source because it exposes the EVSE and connector
hierarchy directly.

## Connector Power Evidence

Exact `city == Alkmaar` connector power distribution, selected values:

| Connector max power | Connectors |
|---:|---:|
| 11.00 kW | 183 |
| 11.04 kW | 88 |
| 13.00 kW | 290 |
| 14.00 kW | 42 |
| 15.00 kW | 166 |
| 17.00 kW | 30 |
| 22.00 kW | 158 |
| 22.08 kW | 103 |
| DC >= 30 kW | 42 |
| missing `max_electric_power` | 22 |
| zero-valued `max_electric_power` | 54 |

Diagnostic bins:

| Slice | 10-12.5 kW | 16.5-17.5 kW | 21.5-22.5 kW | DC >= 30 kW |
|---|---:|---:|---:|---:|
| `city == Alkmaar` | 274 | 32 | 261 | 42 |
| Alkmaar-area bbox | 443 | 94 | 369 | 48 |

Interpretation: 22 kW-ish connectors are common, but they are not dominant in
the current Alkmaar slice. The 11 kW-ish bin is slightly larger than the
22 kW-ish bin, and the exact 13 kW group is the largest single current value.
As contextual evidence only, NDW therefore weakens a claim that `cp_capacity_kw = 22` is the unique
representative current Alkmaar public charging capacity.

## Unit Implications For EV-008

NDW supports a charge-point-like interpretation more strongly than a pole
interpretation:

- OCPI `location` is a site/location record and can contain multiple EVSEs.
- OCPI `evse` is the electrically meaningful charging outlet unit exposed by
  NDW for this snapshot.
- OCPI `connector` is the plug/interface under an EVSE; in the selected
  Alkmaar slices, EVSE and connector counts are one-to-one.
- The file does not expose a public pole ID or CBS municipality code.

ElaadNL's profile-generator documentation states that a `cp` profile simulates
one charge point, and for public locations two charge points share one pole
connection. Combining the two sources, the safest alignment is:

```text
one generated ElaadNL public cp member ~= one NDW public EVSE/connector/charge point
two generated public cp members ~= one public pole connection for pole-level accounting
```

This contextual evidence supports treating D-010/EV-007 public totals as charge-point-like counts
only if the Outlook public-count definition is confirmed to mean public charge
points, not poles. NDW itself cannot validate the Outlook unit; it can only
show how a current infrastructure source separates locations, EVSEs, and
connectors.

## Recommendation To PI

Do not approve EV-008 exactly as written yet.

Recommended amendment before public Set B generation:

1. Keep `profile_type = cp`, `location_type = public`, native `["van", "car"]`
   mix, uncontrolled charging, fixed generator year 2030, 100 profiles per
   batch, and the proposed candidate/held-out seed separation.
2. State explicitly that one Set B profile member represents one public
   charge-point/EVSE/connector-like unit, not one pole. If a pole count is ever
   used, convert by the ElaadNL two-charge-points-per-pole convention.
3. Replace the unqualified `cp_capacity_kw = 22` primary convention with either:
   - a PI-signed rationale that 22 kW is a deliberate future AC upper-capacity
     convention rather than a current Alkmaar fleet representative; or
   - a small proposed capacity-stratified public profile design, for example
     separate 11/13/15/22 kW capacity classes or a signed simplification such as
     11 kW primary plus 22 kW sensitivity.

Eco-Movement is not needed for this contextual decision packet. NDW already provides a
free, reproducible OCPI hierarchy with current locations, EVSEs, connectors,
and connector power. Eco-Movement would only be an optional cross-check if a
free, reproducible, acceptable-terms extract becomes available.

## What Remains Blocked

- EV-008 still needs PI approval or amendment before any public Set B ElaadNL
  API call.
- Exact `GM0361` municipality-boundary counts need a sourced boundary join if
  the PI wants current-inventory counts by municipality rather than city/bbox
  slices.
- Public profile generation, EV held-out adequacy, integrated net-load/event
  analysis, `P(E)`, and manuscript results remain out of scope.
## Contextual-Only Boundary

D-012 remains proposed contextual evidence unless a later PI decision explicitly promotes it. It is not an executable adoption-count source, profile library, inventory-to-grid allocation source, congestion input, or manuscript-result dataset. EV-008A used it as a capacity/unit decision aid only; later public profile generation and EV adoption counts remain governed by EV-008A and D-010/EV-007A respectively.
