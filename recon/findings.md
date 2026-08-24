# Bellhaven Assessment — Recon Findings

Data pulled 2026-08-24 via GET-only requests. Sources: `recon/accounts.json` (121 accounts), `recon/contacts.json` (67 contacts), `recon/website_locations.json` (35 locations parsed from raw HTML in `recon/html/`).

---

## 1. Account totals and breakdowns

**121 accounts total.**

By status:

| Status | Count |
|---|---|
| Active | 112 |
| Inactive | 9 |

By `parent_name`:

| parent_name | Count |
|---|---|
| Juniper Point Healthcare (Parent Account) | 30 |
| Bellhaven Senior Living (Parent Account) | 29 |
| *(blank — no parent_id)* | 26 |
| Stonebridge Eldercare (Parent Account) | 25 |
| Cedar Trail Communities (Parent Account) | 5 |
| Harborview Care Group (Parent Account) | 5 |
| Millstone Health Partners (Parent Account) | 1 |

Of the 26 blank-parent accounts, 6 are the parent accounts themselves (Bellhaven `0015QAPLGS3FVYEEEM`, Juniper Point `001DAAUWV2J3SHQJ34`, Stonebridge `00139TNDS8HNLUZ5A6`, Cedar Trail `001FWSQ30SFW6S7604`, Harborview `001FJZYHR7MLFMNPLL`, Millstone `001YRHHXQ5HJ0TCL2U`), leaving **20 orphan facility accounts** (see §4).

## 2. Parent candidates

There is exactly **one** literal Bellhaven parent: **`0015QAPLGS3FVYEEEM` — Bellhaven Senior Living (Parent Account)**. No second "Bellhaven"-named parent, rebrand shell, or old corporate name exists in the account list.

However, the website's About page (`recon/html/about.html`) states:

> "In 2025 we welcomed the **Harborview Care Group** family of communities, and in 2026 we expanded further with **select communities joining us from Cedar Trail**."

So two other parent accounts represent acquired operators whose facilities now appear on the Bellhaven website:

- **Harborview Care Group (Parent Account) `001FJZYHR7MLFMNPLL`** — 5 children. One (Bellhaven Crossings of Lima `001LGFPBJY4N9MB6KL`) is already Bellhaven-branded and on the website while still parented to Harborview.
- **Cedar Trail Communities (Parent Account) `001FWSQ30SFW6S7604`** — 5 children; three are on the website: Bellhaven of Marietta `001A34WFSUYHCRBLFT`, Bellhaven of Tiffin `001U6RW32TY0WSXZZB`, and Cedar Trail of Zanesville `001H1JMVZWP46D5VUF` (listed on site as "Bellhaven of Zanesville", address match 2680 Maple Ave). "Select communities" implies the other two (Cedar Trail of Monroe, Kettering Senior Campus) may **not** have transferred — both are address collisions with other operators' accounts (§4).

The other operators — **Juniper Point Healthcare** (30 children), **Stonebridge Eldercare** (25), **Millstone Health Partners** (1) — look like unrelated/competitor operators, not Bellhaven predecessors. Caution: Juniper Point owns an **Amberly Manor `0015D74ZLRY810RGY5` in Colorado Springs, CO**, which name-collides with the website's Amberly Manor in Hudson, OH (§4) — a trap for name-only matching.

## 3. Website locations

**35 locations**: 34 listed in the paginated `/communities` directory (3 pages) plus **Bellhaven Meadows of Findlay**, which is linked only from the homepage "New this year" notice and is absent from the directory. This matches the homepage claim of "35 communities."

States: **OH 24, MI 5, PA 4, IN 2**. (No website location outside these four states.)

Each detail page provides name, street address, city/state/zip, care offerings, administrator name, and phone — all captured in `website_locations.json`.

## 4. Data mess

### Exact duplicate account
- **Bellhaven of Owosso × 2**, both Active under the Bellhaven parent, same address spelled two ways: `001QU150PM4Z15UA71` (1120 West Main Street) and `001EGU7BMJ942ZTRE6` (1120 W Main St). Each carries its own contact (Tricia Lindqvist on the former, Gloria Lambert on the latter). The website's administrator for Owosso is **Gloria Lambert**, which corroborates `001EGU7BMJ942ZTRE6` as the "real" record. This is the only exact name duplicate in the CRM.

### Same-address collisions across operators (CHOW-shaped)
| Address | Accounts |
|---|---|
| 1420 Harbor Point Dr, Port Clinton OH | Bellhaven of Port Clinton `001UELXDAKFRKB8932` (Bellhaven) + Harborview Nursing & Rehab of Port Clinton `001JD2MWRA74LTSN24` (Harborview) |
| 4930 W Lake Rd, Erie PA | Bellhaven Shores of Erie `001CVBBCSDM7YHN220` (Bellhaven) + Harborview Shores of Erie `001BLYF02K97SZLZHH` (Harborview) |
| 750 Stewart Rd, Monroe MI — **3-way** | Bellhaven Gardens of Monroe `001U1750VLVJAGG1S5` (Bellhaven) + Cedar Trail of Monroe `0011AB44D05WLA9HTX` (Cedar Trail) + Monroe Gardens Care Center `00159PL81N38KM4FHM` (Harborview) |
| 3313 Wilmington Pike/Pk, Kettering OH — **3-way** | Kettering Care Centre `001WR41PYNWXCAE2X4` (Harborview) + Kettering Nursing & Rehabilitation `0016KTS1UAWBRXS09J` (**no parent**) + Kettering Senior Campus `001B7XZAA3AFALS9GP` (Cedar Trail). Website lists this address as **"Bellhaven of Kettering"** — no Bellhaven-named CRM account exists for it. |
| 2715 Columbus Ave, Sandusky OH | Bellhaven of Sandusky `001SXSF4ELF0Z2LGDM` (Bellhaven, rev $130k / AR $5.2k) + Millstone Care of Sandusky `0017JP8Z1UQ763BVK3` (Millstone). Sandusky is **not on the website** — looks like a facility that left Bellhaven for Millstone (a CHOW in the other direction). Note Bellhaven of Sandusky has rev>0 AND AR>0, so the CHOW rule applies. |

### Facilities with no parent_id (20, excluding the 6 parent records)
`001YQH5RQ9VL8C42GU` Aspen Court Assisted Living (Inactive), `001BR49KRHQDR5HCVS` Aspen Court Nursing & Rehabilitation, `001UKEFGADQ8YCZ4YM` **Bellhaven Meadows of Findlay**, `001YTHGSDPVYZKCEMU` Brookfield Manor, `001635XYQP9EZ7JGCN` Clearbrook Nursing & Rehabilitation, `001WQE9H25YMEWBARU` Golden Gate Gardens, `001X5Q9PV6ZSZH9QVB` Golden Gate Health Campus, `001GHXNGX101RS6W00` Heritage Estates, `001N5WGUBLJA45R30X` Heritage Place, `0016M7QA3RN7P2VQ9J` Ivy Gate Village, `0016KTS1UAWBRXS09J` **Kettering Nursing & Rehabilitation**, `00199LM13DSYJ6EBNG` Northfield Rehabilitation Center (Inactive), `0017B6CMNGFQ8MB8YS` Rosewood Manor, `001KC7UVYEYAZ8M6GN` Rosewood Village, `001SQ3L8LDXR02QLVG` Silver Birch Rehabilitation Center, `001JL9B1K2SX8PLC0G` Willowbrook Assisted Living, `001Q1NFCVW57WXGXZ1` Willowbrook Gardens, `001S2E8GJCGHSWXU8F` Willowbrook Nursing & Rehabilitation (Inactive), `0014RVA32X0EBHFHRN` Winding Creek Estates, `001EXHQSTKFJW1S18Z` Winding Creek Health Campus.

The two that clearly matter for Bellhaven: **Bellhaven Meadows of Findlay** (on the website, homepage-featured new community, rev $22k — needs parenting to Bellhaven) and **Kettering Nursing & Rehabilitation** (part of the Kettering 3-way collision above). Most of the rest share name families with Juniper/Stonebridge facilities in *different* cities (Aspen Court, Golden Gate, Willowbrook, Winding Creek, Rosewood, Heritage, Clearbrook, Silver Birch, Brookfield, Northfield clusters) — similar names but distinct addresses, so they look like sloppy/unlinked records rather than duplicates of each other. Treat with care before merging anything.

### Bellhaven-parent accounts NOT on the website (by name+address reconciliation)
- **Bellhaven of Sandusky `001SXSF4ELF0Z2LGDM`** — see Millstone collision above; rev+AR nonzero.
- **Bellhaven of Coldwater `0016PVXH4B25HWR7QE`** (90 N Michigan Ave, Coldwater MI) — no website page, no address collision.
- **Bellhaven Care Center of Alliance `00116ETS45BL7DTQP7`** (1785 Freshley Ave, Alliance OH) — no website page, no address collision.

Also note three Bellhaven-parent accounts that ARE on the website but under **different names** (address-confirmed):
- Riverbend Manor Care Center `001RJU1X4NBWC1Q0G7` = website "Bellhaven of Chagrin Falls" (150 River St; website admin Dale Mabry is a CRM contact on this account).
- Chesterton Senior Commons `0013NUZQHQUEZ8DXEG` = website "Bellhaven of Chesterton" (website admin Karen Reyes is a CRM contact on this account).
- Sunny Acres Retirement Home `0017MN2JYAJBDS8WQZ` = website "Bellhaven Willow Creek" (8060 Willow Creek Ln, Portage MI).

Minor name variants that still match: "Bellhaven of Sycamore Ridge" (CRM) vs "Bellhaven at Sycamore Ridge" (site), "Bellhaven Health Care Center of Ashland" vs "Bellhaven Healthcare Centre of Ashland", "Bellhaven Rehab and Nursing of Grove City" vs "Bellhaven Rehabilitation & Nursing of Grove City", "Arbors at Bellhaven Dayton" vs "The Arbors at Bellhaven - Dayton".

### Website locations with no plausible CRM account
- **Bellhaven of Batavia** (2000 Hospital Dr, Batavia OH 45103) — no CRM account in Batavia, no street match anywhere.
- **Bellhaven of Carlisle** (640 Walnut Bottom Rd, Carlisle PA 17015) — no CRM account in Carlisle, no street match. (Do not confuse with Bellhaven of *New* Carlisle, OH `001AQGPZ5G5VRES536`, which is a separate, matched location.)
- **Amberly Manor** (4390 Darrow Rd, Hudson OH 44236) — no CRM account in Hudson and no street match. The CRM's "Amberly Manor" `0015D74ZLRY810RGY5` is in **Colorado Springs, CO under Juniper Point** — a name collision, not this facility. (Stonebridge's Amberly Care Center / Amberly Gardens are also unrelated cities.)
- **Ambiguous — Bellhaven at Union Square** (118 Union Square Dr, New Albany OH): CRM has **Union Square Senior Living `001GNU41AVXZRLLJ9P`** (Juniper Point) in the same city but at **240 Market St**. Same-city name overlap with a different street and a different (competitor) parent — plausible but unconfirmed match; needs a decision, not an assumption.

### Care-offering note
Website care offerings use different vocabulary than CRM `care_type` (e.g. website "Short-Term Rehabilitation & Nursing" vs CRM "Skilled Nursing", "Memory Support" vs "Memory Care"), and CRM care_type contradicts the website in places (e.g. Clearbrook Nursing & Rehabilitation has care_type "Assisted Living"). Field-level reconciliation shouldn't assume either side is canonical without a mapping.

## 5. CHOW-rule accounts (lifetime_revenue > 0 AND outstanding_ar > 0)

11 accounts. Any re-parenting of these must follow the CHOW rule.

| account_id | Name | Parent | Rev | AR | Relevance |
|---|---|---|---|---|---|
| `0019Y4J61ZBG4R00CD` | Bellhaven Terrace of Akron | Bellhaven | 101,000 | 9,000 | Already Bellhaven; on website |
| `001R4PXTUD9R6FNN8V` | Bellhaven of Defiance | Bellhaven | 66,000 | 9,500 | Already Bellhaven; on website |
| `001KC1NG7EZDEKKA3T` | Bellhaven of Meadville | Bellhaven | 87,000 | 1,000 | Already Bellhaven; on website |
| `001SXSF4ELF0Z2LGDM` | Bellhaven of Sandusky | Bellhaven | 130,000 | 5,200 | **Not on website; address shared with Millstone Care of Sandusky — if divested, CHOW applies** |
| `001A34WFSUYHCRBLFT` | Bellhaven of Marietta | Cedar Trail | 51,250 | 3,800 | **On website; likely needs re-parent Cedar Trail → Bellhaven → CHOW applies** |
| `001U6RW32TY0WSXZZB` | Bellhaven of Tiffin | Cedar Trail | 84,000 | 12,400 | **Same — CHOW applies on re-parent** |
| `001WC2VPMSRMLGKEFS` | Bristol Manor Gardens | Juniper Point | 47,000 | 4,500 | Not a Bellhaven site; likely untouched |
| `001BP1CWFQELP1V08N` | Clearbrook Senior Living | Juniper Point | 49,000 | 8,000 | Not a Bellhaven site; likely untouched |
| `001FLBJX4DH6BCXLAV` | Harvest Hill Estates | Juniper Point (Inactive) | 6,000 | 4,000 | Not a Bellhaven site |
| `001AUYU58KMWDYXQA6` | Northfield Care Center | Stonebridge | 160,000 | 5,500 | Not a Bellhaven site |
| `001N7WFJCG16TZGL6Y` | Rosewood Nursing & Rehabilitation | Stonebridge | 66,000 | 4,500 | Not a Bellhaven site |

Note: Bellhaven Crossings of Lima `001LGFPBJY4N9MB6KL` (Harborview → presumably Bellhaven) has rev $47,000 but **AR = 0**, so a simple re-parent is allowed there; it does *not* trigger CHOW. Same for the other Harborview children (all AR = 0).

## 6. Contacts

- **67 contacts, all `is_active: true`**, zero orphans (every `account_id` resolves to an existing account), no duplicate contact names, no duplicate contact rows.
- **39 contacts sit on accounts we may touch** (Bellhaven/Harborview/Cedar Trail/Millstone children and parentless facilities) — re-parenting or merging accounts affects these.
- The Owosso duplicate pair **splits its contacts across the two records**: Gloria Lambert (Administrator) on `001EGU7BMJ942ZTRE6`, Tricia Lindqvist (Admissions Director) on `001QU150PM4Z15UA71`. A merge must move the loser's contact.
- **17 contacts have neither email nor phone.**
- One shared email across two different people: `dnovak@bellhavenliving.com` on both Dale Novak (Admissions, Arbors at Bellhaven Dayton `0010KJFP601YNTZVDA`) and Doug Novak (Administrator, Bellhaven Woods of Toledo `0014DHACE6WQU3RMM5`) — likely a data-entry error.
- Website administrator names corroborate account identity in 20 of 35 locations, including the renamed accounts (Dale Mabry → Riverbend Manor = Chagrin Falls; Karen Reyes → Chesterton Senior Commons; Dale Amato → Cedar Trail of Zanesville; Sam Pruitt → Bellhaven Meadows of Findlay; Gloria Lambert → Owosso `001EGU7BMJ942ZTRE6`). The other 15 website admins (incl. Batavia's Elaine Lindqvist, Carlisle's Ken Ashby, Kettering's Priya Ashby, Union Square's Phil Holloway, Amberly Manor's Tom Trent, Willow Creek's Walt Mabry) have **no CRM contact** — if we create/adopt accounts for those sites, contacts are missing too.

## 7. Field quirks

- The account schema includes **`chow_current_account`** and **`duplicate_of_account`**. Both are present on every record and are **empty strings on all 121 accounts** — nothing is pre-linked; any CHOW/duplicate wiring is ours to do.
- `created_by_candidate` is `false` on all 121 accounts and all 67 contacts — a clean way to distinguish our future writes from seed data.
- `updated_at` is identical on every account and contact (`2026-08-24 15:11:49Z`), so timestamps carry **no signal** about which record is older/newer — duplicate-survivor decisions can't lean on recency.
- Bellhaven of Ashtabula `001NXP9X46CWEPSLSV` has a **PO Box** billing street (PO Box 517) while the website shows a street address — address-based matching must tolerate this.
- Street abbreviations are inconsistent throughout ("West Main Street" vs "W Main St", "Wilmington Pike" vs "Wilmington Pk"), which is exactly what hides the Owosso and Kettering collisions from naive equality checks.
